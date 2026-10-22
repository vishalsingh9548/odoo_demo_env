from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductTemplateMachine(models.Model):
    """Mark a product as a machine that gets maintained, with its next due date."""
    _inherit = 'product.template'

    is_machine_product = fields.Boolean(string='Machine Product')
    maintenance_due_on = fields.Date(string='Maintenance Due On')
    last_maintenance_mail_sent_on = fields.Date(string='Last Maintenance Reminder', readonly=True)


class StockLocationMaintenance(models.Model):
    """Which stock places are the maintenance workshop and the spare-parts store."""
    _inherit = 'stock.location'

    is_maintenance_location = fields.Boolean(string='Maintenance Location')
    is_maintenance_source_location = fields.Boolean(string='Maintenance Source Location')

    @api.constrains('is_maintenance_location', 'is_maintenance_source_location')
    def _check_single_maintenance_location(self):
        """Only one maintenance location and one source location per company."""
        for loc in self:
            for flag, label in (('is_maintenance_location', 'Maintenance Location'),
                                ('is_maintenance_source_location', 'Maintenance source location')):
                if loc[flag]:
                    other = self.search([(flag, '=', True), ('id', '!=', loc.id), ('company_id', '=', loc.company_id.id)], limit=1)
                    if other:
                        raise ValidationError(_('Only one location can be marked as "%s". "%s" is already set.',
                                                label, other.display_name))


class ResUsersMaintenance(models.Model):
    """Who approves maintenance, who handles the store, who is told when the transfer is validated."""
    _inherit = 'res.users'

    is_maintenance_manager = fields.Boolean(string='Maintenance Manager')
    is_maintenance_store_person = fields.Boolean(string='Maintenance Store Person')
    notify_on_maintenance_transfer_validated = fields.Boolean(string='Notify on Maintenance Transfer Validated')


class MaintenanceComponentLine(models.Model):
    """A spare part chosen for a maintenance request."""
    _name = 'maintenance.request.component.line'
    _description = 'Maintenance Component'

    request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    product_qty = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit')


class MaintenanceReasonLine(models.Model):
    """Why a component needs attention (text + photo)."""
    _name = 'maintenance.request.reason.line'
    _description = 'Maintenance Reason'

    request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Component', required=True)
    reason = fields.Text(required=True)
    image = fields.Binary(attachment=True)
    image_filename = fields.Char()


class MaintenanceRequest(models.Model):
    """Machine maintenance: pick components, get approval, move parts, repair, consume."""
    _inherit = 'maintenance.request'

    machine_product_id = fields.Many2one('product.product', string='Machine Product',
                                         domain="[('is_machine_product', '=', True)]")
    bom_id = fields.Many2one('mrp.bom', compute='_compute_bom_id', string='Bill of Materials')
    component_line_ids = fields.One2many('maintenance.request.component.line', 'request_id', string='Equipments')
    reason_line_ids = fields.One2many('maintenance.request.reason.line', 'request_id', string='Maintenance Reasons')
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True, copy=False)
    picking_count = fields.Integer(compute='_compute_picking_count')
    repairing_move_ids = fields.Many2many('stock.move', 'maint_request_repair_move_rel', 'request_id', 'move_id',
                                          copy=False)
    stage_name = fields.Char(related='stage_id.name', string='Stage Name')

    @api.depends('machine_product_id')
    def _compute_bom_id(self):
        """The first bill of materials of the machine product."""
        for req in self:
            req.bom_id = self.env['mrp.bom'].search(
                [('product_tmpl_id', '=', req.machine_product_id.product_tmpl_id.id)], limit=1) if req.machine_product_id else False

    @api.depends('picking_id')
    def _compute_picking_count(self):
        """0 or 1: is there an internal transfer?"""
        for req in self:
            req.picking_count = 1 if req.picking_id else 0

    # ------------------------------------------------------------------ helpers
    def _set_stage_by_name(self, name):
        """Move the request to the stage with this name (it must exist)."""
        stage = self.env['maintenance.stage'].search([('name', '=', name)], limit=1)
        if not stage:
            raise UserError(_('Stage "%s" was not found. Please create it first.', name))
        self.write({'stage_id': stage.id})

    def _maint_locations(self):
        """Return (source, maintenance) locations for this request's company."""
        self.ensure_one()
        Loc = self.env['stock.location']
        dom = [('company_id', 'in', [self.company_id.id, False])]
        source = Loc.search(dom + [('is_maintenance_source_location', '=', True)], limit=1)
        dest = Loc.search(dom + [('is_maintenance_location', '=', True)], limit=1)
        if not source:
            raise UserError(_('No maintenance source location is set. Tick "Maintenance Source Location" on a location.'))
        if not dest:
            raise UserError(_('No maintenance location is set. Tick "Maintenance Location" on a location.'))
        return source, dest

    # ------------------------------------------------------------------ component wizards
    def action_select_components(self):
        """Select Components: open the picker showing the machine's BoM lines."""
        self.ensure_one()
        if not self.machine_product_id:
            raise UserError(_('Please select a Machine Product first.'))
        if not self.bom_id or not self.bom_id.bom_line_ids:
            raise UserError(_("No Bill of Materials (or no components) found for '%s'. Cannot select maintenance components.",
                              self.machine_product_id.display_name))
        wiz = self.env['maintenance.component.wizard'].create({
            'request_id': self.id,
            'line_ids': [(0, 0, {'product_id': l.product_id.id, 'bom_qty': l.product_qty,
                                 'qty_needed': l.product_qty, 'uom_id': l.product_uom_id.id})
                         for l in self.bom_id.bom_line_ids],
        })
        return {'type': 'ir.actions.act_window', 'name': _('Select Components'), 'res_model': 'maintenance.component.wizard',
                'res_id': wiz.id, 'view_mode': 'form', 'target': 'new'}

    def action_describe_reasons(self):
        """Maintenance Reason: open one row per chosen component to describe the problem."""
        self.ensure_one()
        if not self.component_line_ids:
            raise UserError(_('No components to describe.'))
        wiz = self.env['maintenance.reason.wizard'].create({
            'request_id': self.id,
            'line_ids': [(0, 0, {'product_id': l.product_id.id}) for l in self.component_line_ids],
        })
        return {'type': 'ir.actions.act_window', 'name': _('Maintenance Reasons'), 'res_model': 'maintenance.reason.wizard',
                'res_id': wiz.id, 'view_mode': 'form', 'target': 'new'}

    # ------------------------------------------------------------------ workflow
    def action_send_for_approval(self):
        """Send for Approval: only from New Request; needs a flagged maintenance manager."""
        for req in self:
            if req.stage_id.name != 'New Request':
                raise UserError(_('Only a new request can be sent for approval.'))
            if not self.env['res.users'].sudo().search_count([('is_maintenance_manager', '=', True)]):
                raise UserError(_('No user is flagged as "Maintenance Manager". Please check that box on at least one user.'))
            if not req.component_line_ids:
                raise UserError(_('Please select at least one component for this maintenance request.'))
            req._set_stage_by_name('Approval Send')
            for manager in self.env['res.users'].sudo().search([('is_maintenance_manager', '=', True)], limit=3):
                req.sudo().activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                             note=_('Maintenance request %s needs your approval.', req.name))
        return True

    def action_approve(self):
        """Approve: Maintenance Manager only; then the internal transfer of parts is created."""
        for req in self:
            if not self.env.user.is_maintenance_manager:
                raise UserError(_('Only a Maintenance Manager can approve this request.'))
            req._set_stage_by_name('Approved')
            req._create_maintenance_transfer()
        return True

    def _create_maintenance_transfer(self):
        """Draft internal transfer: parts from the store to the maintenance location."""
        self.ensure_one()
        source, dest = self._maint_locations()
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': wh.int_type_id.id, 'location_id': source.id, 'location_dest_id': dest.id,
            'origin': self.name, 'company_id': self.company_id.id,
            'move_ids': [(0, 0, {
                'name': l.product_id.display_name, 'product_id': l.product_id.id, 'product_uom_qty': l.product_qty,
                'product_uom': (l.uom_id or l.product_id.uom_id).id, 'location_id': source.id,
                'location_dest_id': dest.id}) for l in self.component_line_ids],
        })
        self.picking_id = picking.id

    def action_start_progress(self):
        """Start Progress: Approved -> In Progress."""
        for req in self:
            if req.stage_id.name != 'Approved':
                raise UserError(_('Only an approved request can be started.'))
            req._set_stage_by_name('In Progress')
        return True

    def action_mark_done(self):
        """Mark to Done: the parts transfer must be validated; the delivered parts are then consumed."""
        for req in self:
            if req.stage_id.name != 'In Progress':
                raise UserError(_('Only a request in progress can be marked done.'))
            if not req.picking_id or req.picking_id.state != 'done':
                raise UserError(_('The internal transfer moving the components to the maintenance location has not been validated yet.'))
            req._consume_components()
            req._set_stage_by_name('Done')
        return True

    def _consume_components(self):
        """Consume: move each delivered part from the maintenance location to Production (by lot)."""
        self.ensure_one()
        _source, dest = self._maint_locations()
        prod = self.env['stock.location'].search([('usage', '=', 'production'), ('company_id', 'in', [self.company_id.id, False])], limit=1)
        if not prod:
            raise UserError(_('No Production location found.'))
        for ml in self.picking_id.move_line_ids.filtered(lambda m: m.quantity > 0):
            move = self.env['stock.move'].create({
                'name': _('Maintenance consumption %s', self.name), 'product_id': ml.product_id.id,
                'product_uom_qty': ml.quantity, 'product_uom': ml.product_uom_id.id,
                'location_id': dest.id, 'location_dest_id': prod.id, 'origin': self.name,
                'company_id': self.company_id.id,
                'move_line_ids': [(0, 0, {'product_id': ml.product_id.id, 'quantity': ml.quantity,
                                          'product_uom_id': ml.product_uom_id.id, 'lot_id': ml.lot_id.id,
                                          'location_id': dest.id, 'location_dest_id': prod.id})],
            })
            move._action_confirm()
            move.picked = True
            move._action_done()

    def action_repairing_state(self):
        """Repairing State: instantly move the parts from the store into the maintenance location."""
        for req in self:
            if req.stage_id.name not in ('Approved', 'In Progress'):
                raise UserError(_('Repairing can only start from an approved or in-progress request.'))
            if not req.component_line_ids:
                raise UserError(_('No components selected.'))
            source, dest = req._maint_locations()
            moves = self.env['stock.move']
            for line in req.component_line_ids:
                avail = self.env['stock.quant']._get_available_quantity(line.product_id, source)
                if avail < line.product_qty:
                    raise UserError(_('Not enough "%s" at "%s" to start repairing.', line.product_id.display_name, source.display_name))
                move = self.env['stock.move'].create({
                    'name': _('Repairing %s', req.name), 'product_id': line.product_id.id,
                    'product_uom_qty': line.product_qty, 'product_uom': (line.uom_id or line.product_id.uom_id).id,
                    'location_id': source.id, 'location_dest_id': dest.id, 'origin': req.name, 'company_id': req.company_id.id})
                move._action_confirm()
                move._action_assign()
                move.picked = True
                move._action_done()
                moves |= move
            req.repairing_move_ids = [(6, 0, moves.ids)]
            req._set_stage_by_name('Repairing')
        return True

    def action_repairing_done(self):
        """Repairing Done: send the parts back from the maintenance location to the store."""
        for req in self:
            if req.stage_id.name != 'Repairing':
                raise UserError(_('Only a request in the Repairing stage can be completed.'))
            if not req.repairing_move_ids:
                raise UserError(_('No repairing movement found to reverse.'))
            source, dest = req._maint_locations()
            for mv in req.repairing_move_ids.filtered(lambda m: m.state == 'done'):
                avail = self.env['stock.quant']._get_available_quantity(mv.product_id, dest)
                if avail < mv.quantity:
                    raise UserError(_('Not enough "%s" at "%s" to complete repairing.', mv.product_id.display_name, dest.display_name))
                back = self.env['stock.move'].create({
                    'name': _('Repairing done %s', req.name), 'product_id': mv.product_id.id,
                    'product_uom_qty': mv.quantity, 'product_uom': mv.product_uom.id,
                    'location_id': dest.id, 'location_dest_id': source.id, 'origin': req.name,
                    'company_id': req.company_id.id})
                back._action_confirm()
                back._action_assign()
                back.picked = True
                back._action_done()
            req._set_stage_by_name('Done')
        return True

    def action_scrap_machine(self):
        """Scrap: a finished request can be moved to the Scrap stage."""
        for req in self:
            if req.stage_id.name != 'Done':
                raise UserError(_('Only a done request can be scrapped.'))
            req._set_stage_by_name('Scrap')
        return True

    def action_view_maintenance_picking(self):
        """Smart button: open the internal transfer."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': self.picking_id.id,
                'view_mode': 'form'}


class MaintenanceComponentWizard(models.TransientModel):
    """Pick which BoM components this maintenance needs, and how many."""
    _name = 'maintenance.component.wizard'
    _description = 'Select Maintenance Components'

    request_id = fields.Many2one('maintenance.request', required=True)
    line_ids = fields.One2many('maintenance.component.wizard.line', 'wizard_id')

    def action_confirm(self):
        """Add the ticked components to the request after checking quantities."""
        self.ensure_one()
        chosen = self.line_ids.filtered('selected')
        if not chosen:
            raise UserError(_('Please select at least one component for this maintenance request.'))
        for l in chosen:
            if l.qty_needed <= 0:
                raise UserError(_("Quantity must be greater than zero for '%s'.", l.product_id.display_name))
            if l.qty_needed > l.bom_qty:
                raise UserError(_("Quantity needed for '%s' (%s) cannot be more than the Bill of Materials requirement (%s).",
                                  l.product_id.display_name, l.qty_needed, l.bom_qty))
        self.request_id.component_line_ids.unlink()
        self.env['maintenance.request.component.line'].create([{
            'request_id': self.request_id.id, 'product_id': l.product_id.id, 'product_qty': l.qty_needed,
            'uom_id': l.uom_id.id} for l in chosen])
        return {'type': 'ir.actions.act_window_close'}


class MaintenanceComponentWizardLine(models.TransientModel):
    """One BoM component row in the picker."""
    _name = 'maintenance.component.wizard.line'
    _description = 'Select Maintenance Components Line'

    wizard_id = fields.Many2one('maintenance.component.wizard', ondelete='cascade')
    product_id = fields.Many2one('product.product', readonly=True)
    bom_qty = fields.Float(string='BoM Quantity', readonly=True)
    qty_needed = fields.Float(string='Quantity Needed')
    uom_id = fields.Many2one('uom.uom', string='Unit', readonly=True)
    selected = fields.Boolean(string='Select')


class MaintenanceReasonWizard(models.TransientModel):
    """Describe, with a photo, why each chosen component needs maintenance."""
    _name = 'maintenance.reason.wizard'
    _description = 'Maintenance Reasons'

    request_id = fields.Many2one('maintenance.request', required=True)
    line_ids = fields.One2many('maintenance.reason.wizard.line', 'wizard_id')

    def action_confirm(self):
        """Save the reasons onto the request; every row needs text and a picture."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No components to describe.'))
        for l in self.line_ids:
            if not l.reason:
                raise UserError(_("Please enter a description for '%s'.", l.product_id.display_name))
            if not l.image:
                raise UserError(_("Please upload an image for '%s'.", l.product_id.display_name))
        self.env['maintenance.request.reason.line'].create([{
            'request_id': self.request_id.id, 'product_id': l.product_id.id, 'reason': l.reason,
            'image': l.image, 'image_filename': l.image_filename} for l in self.line_ids])
        return {'type': 'ir.actions.act_window_close'}


class MaintenanceReasonWizardLine(models.TransientModel):
    """One component row in the reason pop-up."""
    _name = 'maintenance.reason.wizard.line'
    _description = 'Maintenance Reasons Line'

    wizard_id = fields.Many2one('maintenance.reason.wizard', ondelete='cascade')
    product_id = fields.Many2one('product.product', readonly=True)
    reason = fields.Text()
    image = fields.Binary()
    image_filename = fields.Char()
