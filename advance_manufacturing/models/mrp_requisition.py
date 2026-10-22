from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class MrpProduction(models.Model):
    """Manufacturing order: detect missing raw materials, block work until they arrive, raise a requisition."""
    _inherit = 'mrp.production'

    has_low_raw_materials = fields.Boolean(compute='_compute_has_low_raw_materials')
    material_requisition_count = fields.Integer(compute='_compute_material_requisition_count')

    def _compute_has_low_raw_materials(self):
        """True when some component is short at the floor (real free stock with a lot is not enough)."""
        switch = self.env['advmfg.switch']
        for mo in self:
            mo.has_low_raw_materials = bool(switch.is_active(mo.company_id) and mo.state not in ('done', 'cancel')
                                            and mo._advmfg_shortages())

    def _compute_material_requisition_count(self):
        """How many requisitions were raised for this order."""
        data = self.env['material.requisition']._read_group([('mrp_production_id', 'in', self.ids)], ['mrp_production_id'], ['__count'])
        counts = {mo.id: c for mo, c in data}
        for mo in self:
            mo.material_requisition_count = counts.get(mo.id, 0)

    def _advmfg_free_real_qty(self, product, location):
        """Free stock of a product at a location, counting only stock that has a lot (phantom balances ignored)."""
        quants = self.env['stock.quant'].search([('product_id', '=', product.id), ('location_id', 'child_of', location.id),
                                                 ('lot_id', '!=', False)])
        if product.tracking == 'none':
            quants = self.env['stock.quant'].search([('product_id', '=', product.id), ('location_id', 'child_of', location.id)])
        return sum(max(q.quantity - q.reserved_quantity, 0.0) for q in quants)

    def _advmfg_shortages(self):
        """List of (move, required, available, shortage) for every component not fully at the floor."""
        self.ensure_one()
        result = []
        loc = self.location_src_id
        for move in self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id and m.product_uom_qty > 0):
            # Stock this very order has already reserved counts as available to it.
            # For lot-tracked parts only reservations that carry a real lot count: a line with no lot is Odoo's
            # force-reservation of stock that isn't really there (a phantom), so it must not hide the shortage.
            own = sum(ml.quantity for ml in move.move_line_ids if ml.lot_id or move.product_id.tracking == 'none')
            avail = self._advmfg_free_real_qty(move.product_id, move.location_id or loc) + own
            short = move.product_uom_qty - avail
            if float_compare(short, 0, precision_rounding=move.product_uom.rounding) > 0:
                result.append((move, move.product_uom_qty, avail, short))
        return result

    def _advmfg_low_stock_moves(self):
        """Components that are really short: the same rule that shows the Material Requisition button.

        Stock this order has already reserved counts as available, and only real lots are counted, so a
        stray negative balance can no longer block Book Serial / Plan when the button says "nothing short".
        """
        self.ensure_one()
        moves = self.env['stock.move']
        for move, _required, _avail, _short in self._advmfg_shortages():
            moves |= move
        return moves

    def _advmfg_check_raw_materials(self, text):
        """Stop an action when components are insufficient (only in Advance Manufacturing mode)."""
        for mo in self:
            if self.env['advmfg.switch'].is_active(mo.company_id):
                low = mo._advmfg_low_stock_moves()
                if low:
                    raise UserError(_('%s because raw materials are insufficient: %s',
                                      text, ', '.join(low.mapped('product_id.display_name'))))

    def button_plan(self):
        """Plan is refused while raw materials are insufficient."""
        self._advmfg_check_raw_materials(_('Cannot plan this Manufacturing Order'))
        return super().button_plan()

    def action_advmfg_book_serials(self):
        """Booking serials is refused while raw materials are insufficient."""
        self._advmfg_check_raw_materials(_('Cannot generate serial numbers'))
        return super().action_advmfg_book_serials()

    def write(self, vals):
        """Changing the floor, locations or components re-checks stock reservation of running orders."""
        res = super().write(vals)
        if {'advmfg_floor_id', 'location_src_id', 'location_dest_id', 'move_raw_ids'} & set(vals) \
                and not self.env.context.get('skip_auto_assign'):
            for mo in self.filtered(lambda m: m.state in ('confirmed', 'progress')):
                mo.with_context(skip_auto_assign=True).action_assign()
        return res

    def action_view_material_requisitions(self):
        """Smart button: none closes the window, one opens it, several open a list."""
        self.ensure_one()
        reqs = self.env['material.requisition'].search([('mrp_production_id', '=', self.id)])
        if not reqs:
            return {'type': 'ir.actions.act_window_close'}
        if len(reqs) == 1:
            return {'type': 'ir.actions.act_window', 'res_model': 'material.requisition', 'res_id': reqs.id, 'view_mode': 'form'}
        return {'type': 'ir.actions.act_window', 'name': _('Material Requisitions'), 'res_model': 'material.requisition',
                'view_mode': 'list,form', 'domain': [('id', 'in', reqs.ids)]}

    def action_create_material_requisition(self):
        """Material Requisition button: ask the store for exactly the missing components."""
        self.ensure_one()
        shortages = self._advmfg_shortages()
        if not shortages:
            raise UserError(_('No raw material shortage found on the destination location for this Manufacturing Order.'))
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            raise UserError(_('No employee is linked to the current user.'))
        source = self.env['stock.location'].search([('is_mr_source_location', '=', True),
                                                    ('company_id', 'in', [self.company_id.id, False])], limit=1) or self.location_src_id
        if not source or not self.location_src_id:
            raise UserError(_('Source and destination locations must be set on the Manufacturing Order.'))
        user_type = self.env.user.mr_approval_type_id
        if user_type and user_type.company_id != self.company_id:
            raise UserError(_('Selected user approval type belongs to another company. '
                              'Please choose an approval type for this company.'))
        master = user_type or self.env['material.requisition']._role_master(employee)
        if not master:
            raise UserError(_("Configuration Error: No 'Material Request Approver Master' found for this setup. Please configure one."))
        req = self.env['material.requisition'].create({
            'request_raised_by': employee.id, 'purpose': _('Raw material for %s', self.name),
            'source_location_id': source.id, 'destination_location_id': self.location_src_id.id,
            'required_date': max(self.date_start or fields.Datetime.now(), fields.Datetime.now()),
            'approval_type_id': master.id, 'company_id': self.company_id.id, 'mrp_production_id': self.id,
            'material_requisition_line_ids': [(0, 0, {'product_id': m.product_id.id, 'product_uom_qty': short})
                                              for m, req_qty, avail, short in shortages]})
        return {'type': 'ir.actions.act_window', 'res_model': 'material.requisition', 'res_id': req.id, 'view_mode': 'form'}


class MrpWorkorder(models.Model):
    """A work order cannot start while components are insufficient."""
    _inherit = 'mrp.workorder'

    def button_start(self):
        """Start is refused while raw materials are insufficient."""
        for wo in self:
            wo.production_id._advmfg_check_raw_materials(_('Cannot start this Work Order'))
        return super().button_start()


class MaterialRequisitionLotWizard(models.TransientModel):
    """'Select Lots to Use': pick which lots the store should send before the requisition is forwarded."""
    _name = 'material.requisition.lot.wizard'
    _description = 'Pick lots to use before forwarding a Material Requisition'

    requisition_id = fields.Many2one('material.requisition', required=True, readonly=True)
    line_ids = fields.One2many('material.requisition.lot.wizard.line', 'wizard_id')

    def action_confirm(self):
        """Confirm & Forward: check every line, remember the lots, then forward the requisition."""
        self.ensure_one()
        for line in self.line_ids:
            if not line.lot_ids:
                raise UserError(_("Please select at least one lot for '%s' before forwarding.", line.product_id.display_name))
            if float_compare(line.selected_qty, line.required_qty, precision_rounding=line.product_uom.rounding) < 0:
                raise UserError(_("The lot(s) you picked for '%(p)s' only cover %(c)s %(u)s, but %(n)s %(u)s is needed. "
                                  "Please select additional lot(s).", p=line.product_id.display_name, c=line.selected_qty,
                                  u=line.product_uom.name, n=line.required_qty))
        for line in self.line_ids:
            line.requisition_line_id.selected_lot_ids = [(6, 0, line.lot_ids.ids)]
        self.requisition_id.with_context(skip_lot_selection_wizard=True).action_recommend_and_forward()
        return {'type': 'ir.actions.act_window_close'}


class MaterialRequisitionLotWizardLine(models.TransientModel):
    """One product of the lot-selection window."""
    _name = 'material.requisition.lot.wizard.line'
    _description = 'Lot selection line'

    wizard_id = fields.Many2one('material.requisition.lot.wizard', required=True, ondelete='cascade')
    requisition_line_id = fields.Many2one('material.requisition.line', required=True, readonly=True)
    product_id = fields.Many2one(related='requisition_line_id.product_id', readonly=True)
    product_uom = fields.Many2one(related='requisition_line_id.product_uom', readonly=True)
    required_qty = fields.Float(related='requisition_line_id.qty_to_transfer', string='Qty Needed', readonly=True)
    source_location_id = fields.Many2one(related='wizard_id.requisition_id.source_location_id', readonly=True)
    candidate_lot_ids = fields.Many2many('stock.lot', compute='_compute_candidates')
    available_lots_info = fields.Text(compute='_compute_candidates', string='Available Lots')
    lot_ids = fields.Many2many('stock.lot', 'mr_lot_wiz_line_rel', 'line_id', 'lot_id', string='Lots to Use')
    selected_qty = fields.Float(compute='_compute_selected_qty', string='Qty Covered by Selection')

    def _free_by_lot(self):
        """{lot: free quantity} at the source location."""
        quants = self.env['stock.quant'].search([('product_id', '=', self.product_id.id),
                                                 ('location_id', 'child_of', self.source_location_id.id), ('lot_id', '!=', False)])
        free = {}
        for q in quants:
            free[q.lot_id] = free.get(q.lot_id, 0.0) + (q.quantity - q.reserved_quantity)
        return {lot: qty for lot, qty in free.items() if qty > 0}

    @api.depends('product_id', 'source_location_id')
    def _compute_candidates(self):
        """Lots with free stock, and a text listing them."""
        for line in self:
            free = line._free_by_lot()
            line.candidate_lot_ids = [(6, 0, [l.id for l in free])]
            line.available_lots_info = '\n'.join('%s: %s %s free' % (l.name, qty, line.product_uom.name) for l, qty in free.items()) \
                or _('No lot currently has free stock for this product at %s.', line.source_location_id.display_name)

    @api.depends('lot_ids')
    def _compute_selected_qty(self):
        """Free quantity covered by the chosen lots."""
        for line in self:
            free = line._free_by_lot()
            line.selected_qty = sum(free.get(l, 0.0) for l in line.lot_ids)
