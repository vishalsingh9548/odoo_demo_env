from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AdvmfgStatusWizard(models.TransientModel):
    """The 'Update Status' window where the operator grades a unit A, B or C.

    A = fine, go to the next stage.
    B = needs rework: scrap some components and send the unit back to an earlier stage.
    C = lost: scrap components, cancel the unit and make a 1-unit replacement order.
    """
    _name = 'advmfg.status.wizard'
    _description = 'Update Unit Status'
    _inherit = ['advmfg.validation.mixin']

    unit_id = fields.Many2one('advmfg.unit', required=True)
    stage_id = fields.Many2one(related='unit_id.stage_id', string='Current Process')
    show_grade = fields.Boolean(related='unit_id.show_grade')
    grade = fields.Selection([
        ('A', 'Grade A (Quality Pass)'),
        ('B', 'Grade B (Under Maintenance)'),
        ('C', 'Grade C (Scrap)'),
    ])
    # For grade B only: the earlier stage the unit goes back to (the current stage or any before it).
    previous_stage_id = fields.Many2one('advmfg.stage', string='Previous Process')
    previous_stage_domain_ids = fields.Many2many('advmfg.stage', compute='_compute_previous_stage_domain')
    # Sub-stages that hang under the current stage (shown for information).
    linked_child_stage_names = fields.Text(compute='_compute_linked_child_stage_names', string='Linked Stages')
    # Where the components are scrapped from, and where they go.
    location_id = fields.Many2one('stock.location', string='Source Location', domain="[('usage', '=', 'internal')]")
    scrap_location_id = fields.Many2one('stock.location', string='Scrap Location', domain="[('scrap_location', '=', True)]")
    scrap_reason_ids = fields.Many2many('stock.scrap.reason.tag', string='Scrap Reason')
    origin = fields.Char(string='Source Document')
    # The components to scrap for grade B / C (pre-filled from the order's Bill of Materials, one unit's worth).
    line_ids = fields.One2many('advmfg.status.wizard.line', 'wizard_id', string='Components to Scrap')

    @api.depends('stage_id')
    def _compute_previous_stage_domain(self):
        """Stages the unit may be sent back to: top-level stages up to and including the current one."""
        for wiz in self:
            wiz.previous_stage_domain_ids = self.env['advmfg.stage'].search([
                ('company_id', '=', wiz.unit_id.company_id.id), ('parent_id', '=', False),
                ('sequence', '<=', wiz.stage_id.sequence or 0)])

    @api.depends('stage_id')
    def _compute_linked_child_stage_names(self):
        """List the sub-stages under the current stage, in order."""
        for wiz in self:
            children = wiz.stage_id._descendants().sorted(lambda s: (s.sequence, s.id))
            wiz.linked_child_stage_names = '\n'.join(children.mapped('name'))

    @api.onchange('grade', 'unit_id')
    def _onchange_origin(self):
        """Fill the 'source document' text: serial and sale order, or the stage name."""
        for wiz in self:
            unit = wiz.unit_id
            if unit.sale_order_id:
                wiz.origin = '%s - %s' % (unit.name, unit.sale_order_id.name)
            else:
                wiz.origin = '%s - %s' % (unit.name, unit.stage_id.name or '')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill locations and the components list (one unit's worth from the Bill of Materials)."""
        res = super().default_get(fields_list)
        unit = self.env['advmfg.unit'].browse(res.get('unit_id') or self.env.context.get('default_unit_id'))
        if not unit:
            return res
        production = unit.production_id
        res['location_id'] = production.location_src_id.id
        res['scrap_location_id'] = self.env['stock.location'].search([
            ('scrap_location', '=', True), ('company_id', 'in', [production.company_id.id, False])], limit=1).id
        res['origin'] = '%s - %s' % (unit.name, unit.sale_order_id.name or unit.stage_id.name or '')
        bom = production.bom_id
        if bom:
            res['line_ids'] = [(0, 0, {
                'product_id': l.product_id.id,
                'quantity': l.product_qty / (bom.product_qty or 1.0),
            }) for l in bom.bom_line_ids]
        if not unit.show_grade:
            res['grade'] = 'A'  # this stage does not ask for a grade: it is always A
        return res

    def _check_quality_gate(self):
        """Grade must match the quality result: pass -> only A, fail -> only B or C, not done yet -> do it first."""
        unit = self.unit_id
        if not unit.stage_id.qc_required:
            return
        state = unit.qc_id.state
        if state == 'todo' or not state:
            raise UserError(_('Pass or fail the quality check for this stage first.'))
        if state == 'pass' and self.grade != 'A':
            raise UserError(_('The quality check passed. Only Grade A is allowed.'))
        if state == 'fail' and self.grade == 'A':
            raise UserError(_('The quality check failed. Only Grade B or Grade C is allowed.'))

    def _pick_lot(self, product, production):
        """For lot/serial-tracked components with no lot chosen: use a lot that has stock at the order's source location."""
        if product.tracking == 'none':
            return self.env['stock.lot']
        quant = self.env['stock.quant'].search([
            ('product_id', '=', product.id), ('location_id', 'child_of', (self.location_id or production.location_src_id).id),
            ('lot_id', '!=', False), ('quantity', '>', 0)], limit=1)
        if not quant:
            raise UserError(_('Please choose a lot for %s (no lot with stock was found).', product.display_name))
        return quant.lot_id

    def _scrap_components(self):
        """Create and validate a scrap record for each chosen component line; remember them on the unit."""
        unit = self.unit_id
        production = unit.production_id
        scraps = self.env['stock.scrap']
        for line in self.line_ids.filtered(lambda l: l.quantity > 0):
            lot = line.lot_id or self._pick_lot(line.product_id, production)
            vals = {
                'product_id': line.product_id.id,
                'lot_id': lot.id,
                'scrap_qty': line.quantity,
                'product_uom_id': line.product_id.uom_id.id,
                'production_id': production.id,
                'origin': self.origin or unit.name,
                'company_id': production.company_id.id,
                'scrap_reason_tag_ids': [(6, 0, self.scrap_reason_ids.ids)],
            }
            if self.location_id:
                vals['location_id'] = self.location_id.id
            if self.scrap_location_id:
                vals['scrap_location_id'] = self.scrap_location_id.id
            scrap = self.env['stock.scrap'].create(vals)
            result = scrap.action_validate()
            if isinstance(result, dict):
                # Not enough stock recorded: scrap anyway (stock goes negative) and leave a note.
                scrap.do_scrap()
                production.message_post(body=_(
                    'Scrapped %(q)s %(p)s for unit %(u)s although recorded stock was lower.',
                    q=line.quantity, p=line.product_id.display_name, u=unit.name))
            scraps |= scrap
        unit.scrap_ids = [(4, s.id) for s in scraps]

    def action_confirm(self):
        """Apply the chosen grade to the unit."""
        self.ensure_one()
        unit = self.unit_id
        if not self.grade:
            raise UserError(_('Please choose a grade.'))
        if not unit.production_id.bom_id:
            raise UserError(_('No Bill of Materials found for the Manufacturing Order.'))
        if not self.env.context.get('advmfg_scan'):
            self._check_previous_line_status(unit)
        if unit.state == 'yet_to_start':
            unit.state = 'in_progress'
        self._check_quality_gate()

        if self.grade == 'A':
            if not self.env.context.get('advmfg_scan'):
                self._check_attachment_count(unit)
            # Passing a top-level stage also counts all its sub-stages.
            if not unit.stage_id.parent_id:
                mapping = self.env['advmfg.stage']._cumulative_count_map(unit.company_id)
                unit.passed_stage_count = mapping.get(unit.stage_id.id, unit.passed_stage_count)
            unit.action_next_stage()
        elif self.grade == 'B':
            if not self.previous_stage_id:
                raise UserError(_('Please choose the earlier stage to send the unit back to.'))
            prev = self.previous_stage_id
            if prev.parent_id or prev.company_id != unit.company_id or prev.sequence > unit.stage_id.sequence:
                raise UserError(_('Choose an earlier top-level stage to send the unit back to.'))
            self._scrap_components()
            unit._enter_stage(prev)
            unit.grade = 'B'
            unit.state = 'in_progress'
        else:  # Grade C
            self._scrap_components()
            unit.write({'grade': 'C', 'state': 'cancel'})
            unit.production_id._advmfg_split_scrapped_unit(unit)
        return {'type': 'ir.actions.act_window_close'}


class AdvmfgStatusWizardLine(models.TransientModel):
    """One component to scrap: which product and how many."""
    _name = 'advmfg.status.wizard.line'
    _description = 'Update Status Component Line'

    wizard_id = fields.Many2one('advmfg.status.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    quantity = fields.Float(default=1.0)
    tracking = fields.Selection(related='product_id.tracking')
    # Only needed for lot/serial-tracked components; if left empty a lot with stock is picked automatically.
    lot_id = fields.Many2one('stock.lot', string='Lot', domain="[('product_id', '=', product_id)]")
