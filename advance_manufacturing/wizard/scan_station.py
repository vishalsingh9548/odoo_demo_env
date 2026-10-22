from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AdvmfgScanWizard(models.TransientModel):
    """The scan box of the Serial Scan station: scan or type a serial and its details window opens."""
    _name = 'advmfg.scan.wizard'
    _description = 'Scan Serial'

    serial_number = fields.Char(string='Serial Number')

    @api.model
    def lookup_serial(self, serial):
        """Check a scanned serial and say what to do next.

        Returns {status, message[, wizard_id]}: 'completed' / 'cancel' / 'missing' / 'ok'.
        """
        serial = (serial or '').strip()
        unit = self.env['advmfg.unit'].search([('name', '=', serial)], order='create_date desc, id desc', limit=1)
        if not unit:
            pooled = self.env['advmfg.serial'].search([('name', '=', serial)], limit=1)
            if pooled:
                return {'status': 'info', 'message': _("Serial '%s' is booked on %s but not allocated to a unit yet.",
                                                       serial, pooled.production_id.name)}
            return {'status': 'missing', 'message': _("Serial number '%s' does not exist. Please check.", serial)}
        if unit.state == 'completed':
            return {'status': 'completed', 'message': _("This serial number '%s' is already completed.", serial)}
        if unit.state == 'cancel':
            return {'status': 'cancel', 'message': _("This serial number '%s' has been cancelled.", serial)}
        wizard_id = self.create_and_return_lookup_wizard(serial)
        if not wizard_id:
            return {'status': 'failed', 'message': _('Failed to get details for serial: %s. No wizard created.', serial)}
        return {'status': 'ok', 'wizard_id': wizard_id, 'title': _('Serial Details: %s', serial)}

    @api.model
    def create_and_return_lookup_wizard(self, serial):
        """Create the details window for the LATEST unit with this serial and return its id."""
        unit = self.env['advmfg.unit'].search([('name', '=', serial)], order='create_date desc, id desc', limit=1)
        if not unit:
            return False
        return self.env['advmfg.serial.lookup.wizard'].create({'unit_id': unit.id}).id


class AdvmfgTrackWizard(models.TransientModel):
    """The scan box of the Serial Track app: type or scan a serial to see its full live lifecycle."""
    _name = 'advmfg.track.wizard'
    _description = 'Serial Track'

    serial_number = fields.Char(string='Serial Number')

    @api.model
    def lookup_serial(self, serial):
        """Find the serial (completed or not) and return the live Serial Journey screen for it."""
        serial = (serial or '').strip()
        unit = self.env['advmfg.unit'].search([('name', '=', serial)], order='create_date desc, id desc', limit=1)
        if not unit:
            pooled = self.env['advmfg.serial'].search([('name', '=', serial)], limit=1)
            if pooled:
                return {'status': 'info', 'message': _("Serial '%s' is booked on %s but not allocated to a unit yet.",
                                                       serial, pooled.production_id.name)}
            return {'status': 'missing', 'message': _("Serial number '%s' does not exist. Please check.", serial)}
        journey = self.env['advmfg.serial.journey'].create({'unit_id': unit.id})
        return {'status': 'ok', 'wizard_id': journey.id, 'title': _('Serial Journey: %s', serial),
                'res_model': 'advmfg.serial.journey'}


class AdvmfgSerialLookupWizard(models.TransientModel):
    """The details window of one scanned unit: stage, grade, attachments, related documents, Update Status."""
    _name = 'advmfg.serial.lookup.wizard'
    _description = 'Serial Number Lookup'
    _inherit = ['advmfg.validation.mixin']

    unit_id = fields.Many2one('advmfg.unit', required=True)
    serial_no = fields.Char(related='unit_id.name')
    current_mo_id = fields.Many2one('mrp.production', string='Manufacturing Order', compute='_compute_related', readonly=False)
    current_sale_order_id = fields.Many2one('sale.order', string='Sale Order', compute='_compute_related', readonly=False)
    current_stage_id = fields.Many2one(related='unit_id.stage_id', string='Current Process')
    next_stage_id = fields.Many2one('advmfg.stage', compute='_compute_stages', string='Next Process')
    previous_stage_id = fields.Many2one('advmfg.stage', string='Previous Process')
    previous_stage_domain_ids = fields.Many2many('advmfg.stage', compute='_compute_stages')
    linked_child_stage_names = fields.Text(compute='_compute_stages', string='Linked Stages')
    show_grade = fields.Boolean(related='unit_id.show_grade')
    quality_status = fields.Selection([('A', 'Grade A (Quality Pass)'), ('B', 'Grade B (Under Maintenance)'),
                                       ('C', 'Grade C (Scrap)')], string='Quality Status')
    qc_applicable = fields.Boolean(related='unit_id.qc_required')
    qc_state = fields.Selection(related='unit_id.qc_state')
    attachment_applicable = fields.Boolean(related='unit_id.attachment_required')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    comment = fields.Text()
    scrap_reason_ids = fields.Many2many('stock.scrap.reason.tag', string='Scrap Reason')
    history_ids = fields.Many2many('advmfg.unit', compute='_compute_history', string='Journey')

    @api.depends('unit_id')
    def _compute_related(self):
        """Find the order and sale order of the unit, falling back to the serial pool and the order's origin."""
        for wiz in self:
            unit = wiz.unit_id
            mo = unit.production_id
            so = unit.sale_order_id
            if not so and mo.origin:
                so = self.env['sale.order'].search([('name', '=', mo.origin)], limit=1)
            if not mo:
                pool = self.env['advmfg.serial'].search([('name', '=', unit.name)], order='id desc', limit=1)
                mo = pool.production_id
            wiz.current_mo_id = mo
            wiz.current_sale_order_id = so

    @api.depends('unit_id')
    def _compute_stages(self):
        """Next stage, the stages the unit may be sent back to, and the sub-stages of the current stage."""
        for wiz in self:
            unit = wiz.unit_id
            wiz.next_stage_id = unit._get_next_unpassed_stage()
            wiz.previous_stage_domain_ids = self.env['advmfg.stage'].search([
                ('company_id', '=', unit.company_id.id), ('parent_id', '=', False),
                ('sequence', '<=', unit.stage_id.sequence or 0)])
            wiz.linked_child_stage_names = ', '.join(
                unit.stage_id._descendants().sorted(lambda s: (s.sequence, s.id)).mapped('name'))

    @api.depends('unit_id')
    def _compute_history(self):
        """Every unit row ever made with this serial (the serial's journey)."""
        for wiz in self:
            wiz.history_ids = self.env['advmfg.unit'].search([('name', '=', wiz.unit_id.name)], order='create_date')

    def _reopen(self):
        """Show this window again after a button."""
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Serial Details: %s', self.unit_id.name)}

    # ---- quality buttons
    def quality_scan_pass(self):
        """Pass the current quality check and show the window again."""
        self.ensure_one()
        self.unit_id.action_pass_qc()
        return self._reopen()

    def quality_scan_fail(self):
        """Fail the current quality check (asks for the reason first)."""
        self.ensure_one()
        if not self.unit_id.qc_id:
            raise UserError(_('There is no quality check to fail for unit %s.', self.unit_id.name))
        return self.unit_id.qc_id.action_fail()

    def create_quality_check_wiz(self):
        """Create the quality check for the unit's current stage if it is missing."""
        self.ensure_one()
        unit = self.unit_id
        if not unit.stage_id.qc_required:
            raise UserError(_('This stage does not need a quality check.'))
        if not unit.qc_id:
            unit._create_stage_qc()
        return self._reopen()

    # ---- related documents
    def action_open_sale_order(self):
        """Open the unit's sale order."""
        self.ensure_one()
        if not self.current_sale_order_id:
            raise UserError(_('No Sale Order is linked to this serial number.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'sale.order', 'res_id': self.current_sale_order_id.id,
                'view_mode': 'form', 'target': 'current'}

    def action_open_manufacturing_order(self):
        """Open the unit's manufacturing order."""
        self.ensure_one()
        if not self.current_mo_id:
            raise UserError(_('No Manufacturing Order is linked to this serial number.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'mrp.production', 'res_id': self.current_mo_id.id,
                'view_mode': 'form', 'target': 'current'}

    # ---- Update Status
    def _save_attachments_and_comment(self):
        """Add the uploaded files to the unit (keeping old ones) and copy the comment."""
        unit = self.unit_id
        if self.attachment_ids:
            self.attachment_ids.sudo().write({'res_model': 'advmfg.unit', 'res_id': unit.id})
            unit.attachment_ids = [(4, a.id) for a in self.attachment_ids]
        if self.comment:
            unit.comment = self.comment

    def _status_wizard(self, grade, lines):
        """Build the shared Update Status window logic for this unit and run it (scan mode skips sequence/attachment checks)."""
        unit = self.unit_id
        wiz = self.env['advmfg.status.wizard'].with_context(advmfg_scan=True, default_unit_id=unit.id).create({
            'unit_id': unit.id, 'grade': grade, 'previous_stage_id': self.previous_stage_id.id,
            'scrap_reason_ids': [(6, 0, self.scrap_reason_ids.ids)],
            'line_ids': [(5, 0, 0)] + [(0, 0, l) for l in lines]})
        return wiz.action_confirm()

    def _all_component_lines(self):
        """One unit's worth of every active raw component of the order."""
        mo = self.unit_id.production_id
        qty = mo.product_qty or 1.0
        return [{'product_id': m.product_id.id, 'quantity': m.product_uom_qty / qty}
                for m in mo.move_raw_ids if m.state != 'cancel' and m.product_uom_qty > 0]

    def action_update_status(self):
        """Update Status: apply the chosen grade (A next stage, B scrap all + back, C choose components first)."""
        self.ensure_one()
        unit = self.unit_id
        grade = self.quality_status if self.show_grade else 'A'
        if not grade:
            raise UserError(_('Please choose a grade.'))
        if self.attachment_applicable and not (self.attachment_ids or unit.attachment_ids):
            raise UserError(_('Please attach the required document(s) before moving to the next stage.'))
        self._save_attachments_and_comment()
        unit.grade = grade
        if grade == 'A':
            self._status_wizard('A', [])
            return {'type': 'ir.actions.act_window', 'res_model': 'advmfg.scan.wizard', 'view_mode': 'form',
                    'target': 'new', 'name': _('Scan Serial'),
                    'context': {'advmfg_scan_message': _('Successful. You can now proceed with the next step.')}}
        if grade == 'B':
            if not self.previous_stage_id:
                raise UserError(_('Please choose the earlier stage to send the unit back to.'))
            self._status_wizard('B', self._all_component_lines())
            return {'type': 'ir.actions.act_window_close'}
        if not unit.production_id:
            raise UserError(_('No Manufacturing Order found for this serial assignment.'))
        return {'type': 'ir.actions.act_window', 'name': _('Select Components to Scrap'),
                'res_model': 'advmfg.scrap.component.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_lookup_id': self.id,
                            'default_line_ids': [(0, 0, dict(l, scrap=True)) for l in self._all_component_lines()]}}


class AdvmfgScrapComponentWizard(models.TransientModel):
    """Grade C helper: choose which components to scrap (all ticked by default)."""
    _name = 'advmfg.scrap.component.wizard'
    _description = 'Select Components to Scrap'

    lookup_id = fields.Many2one('advmfg.serial.lookup.wizard', required=True)
    line_ids = fields.One2many('advmfg.scrap.component.line', 'wizard_id', string='Components')

    def action_confirm_scrap(self):
        """Confirm Scrap: scrap the ticked components, cancel the unit and make the replacement order."""
        self.ensure_one()
        lookup = self.lookup_id
        chosen = [{'product_id': l.product_id.id, 'quantity': l.quantity} for l in self.line_ids if l.scrap]
        lookup._status_wizard('C', chosen)
        return {'type': 'ir.actions.act_window_close'}


class AdvmfgScrapComponentLine(models.TransientModel):
    """One component in the scrap-selection list."""
    _name = 'advmfg.scrap.component.line'
    _description = 'Scrap Component Line'

    wizard_id = fields.Many2one('advmfg.scrap.component.wizard', ondelete='cascade')
    scrap = fields.Boolean(default=True)
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float()
