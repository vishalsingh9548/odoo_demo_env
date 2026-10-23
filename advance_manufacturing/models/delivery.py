from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AdvmfgDeliveryPack(models.Model):
    """A pack on a delivery: one or more finished pallets that travel together on the truck.

    Draft = still being put together. Confirmed = locked; the delivery cannot be validated until
    every pack is confirmed.
    """
    _name = 'advmfg.delivery.pack'
    _description = 'Delivery Pack'
    _order = 'id'

    name = fields.Char(string='Pack Reference', default='New', copy=False, readonly=True)
    picking_id = fields.Many2one('stock.picking', required=True, ondelete='cascade')
    sale_order_id = fields.Many2one(related='picking_id.sale_id', store=True)
    company_id = fields.Many2one(related='picking_id.company_id', store=True)
    pallet_ids = fields.Many2many('advmfg.pallet', string='Pallets')
    unit_count = fields.Integer(compute='_compute_units')
    serial_text = fields.Text(string='Serial Numbers', compute='_compute_units')
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')], default='draft', required=True)

    @api.depends('pallet_ids.unit_ids')
    def _compute_units(self):
        """Count the units and list the serial numbers carried by this pack."""
        for pack in self:
            units = pack.pallet_ids.unit_ids
            pack.unit_count = len(units)
            pack.serial_text = ', '.join(units.mapped('name'))

    @api.model_create_multi
    def create(self, vals_list):
        """Number each new pack (PACK0001...)."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('advmfg.delivery.pack') or 'New'
        return super().create(vals_list)

    @api.constrains('pallet_ids')
    def _check_pallets(self):
        """Only confirmed pallets of this sale order's orders, and a pallet may sit in one pack only."""
        for pack in self:
            so = pack.sale_order_id
            for pallet in pack.pallet_ids:
                if pallet.state != 'confirmed':
                    raise ValidationError(_('Pallet %s is not confirmed yet.', pallet.name))
                if so and pallet.production_id.sale_order_id != so and pallet.production_id.origin != so.name:
                    raise ValidationError(_('Pallet %s does not belong to Sale Order %s.', pallet.name, so.name))
                other = self.search([('id', '!=', pack.id), ('pallet_ids', 'in', pallet.id)], limit=1)
                if other:
                    raise ValidationError(_('Pallet %s is already in pack %s.', pallet.name, other.name))

    def write(self, vals):
        """A confirmed pack is locked."""
        if any(p.state == 'confirmed' for p in self) and set(vals) - {'state'}:
            raise UserError(_('A confirmed pack cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        """A confirmed pack cannot be deleted."""
        if any(p.state == 'confirmed' for p in self):
            raise UserError(_('A confirmed pack cannot be deleted.'))
        return super().unlink()

    def action_confirm(self):
        """Confirm the pack (needs at least one pallet)."""
        for pack in self:
            if not pack.pallet_ids:
                raise UserError(_('Add at least one pallet to pack %s first.', pack.name))
            pack.state = 'confirmed'
        return True

    def action_draft(self):
        """Re-open a confirmed pack (only while the delivery is not done)."""
        for pack in self:
            if pack.picking_id.state == 'done':
                raise UserError(_('The delivery is already done.'))
            pack.state = 'draft'
        return True


class StockPicking(models.Model):
    """Delivery extras: vehicle and driver details, packs, dispatch checks, serial hand-over."""
    _inherit = 'stock.picking'

    advmfg_active = fields.Boolean(compute='_compute_advmfg_active')
    advmfg_vehicle_name = fields.Char(string='Vehicle Name')
    advmfg_vehicle_number = fields.Char(string='Vehicle Number')
    advmfg_driver_name = fields.Char(string='Driver Name')
    advmfg_driver_contact = fields.Char(string='Driver Contact No')
    advmfg_estimated_arrival = fields.Datetime(string='Estimated Arrival Time')
    advmfg_dispatch_time = fields.Datetime(string='Dispatch Time', copy=False, readonly=True)
    advmfg_received_by = fields.Char(string='Received By', copy=False)
    advmfg_delivered_on = fields.Datetime(string='Delivered On', copy=False)
    advmfg_ship_to = fields.Text(string='Delivered To', compute='_compute_advmfg_ship_to')
    advmfg_pack_ids = fields.One2many('advmfg.delivery.pack', 'picking_id', string='Generated Packs')
    advmfg_pack_status = fields.Selection(
        [('none', 'No Packs'), ('waiting', 'Waiting for Pack Confirmation'), ('ready', 'Packs Confirmed')],
        compute='_compute_advmfg_pack_status', string='Pack Status')

    @api.depends('company_id', 'picking_type_id')
    @api.depends_context('uid', 'company')
    def _compute_advmfg_active(self):
        """Is the special behaviour on for this delivery? (outgoing, non-return, company and user switched on)"""
        switch = self.env['advmfg.switch']
        for picking in self:
            picking.advmfg_active = (
                switch.is_active(picking.company_id or self.env.company)
                and picking.picking_type_code == 'outgoing'
                and not picking.return_id)

    @api.depends('partner_id')
    def _compute_advmfg_ship_to(self):
        """The customer's name and address, shown as the place the goods are delivered to."""
        for picking in self:
            partner = picking.partner_id
            picking.advmfg_ship_to = (partner.display_name + ', ' + (partner._display_address(without_company=True) or '').replace('\n', ', ')).strip(', ') if partner else False

    @api.depends('advmfg_pack_ids.state')
    def _compute_advmfg_pack_status(self):
        """Packs all confirmed -> ready; any draft pack -> waiting; none -> none."""
        for picking in self:
            packs = picking.advmfg_pack_ids
            if not packs:
                picking.advmfg_pack_status = 'none'
            elif all(p.state == 'confirmed' for p in packs):
                picking.advmfg_pack_status = 'ready'
            else:
                picking.advmfg_pack_status = 'waiting'

    def action_advmfg_generate_packs(self):
        """Generate Packs: one draft pack per confirmed pallet of this sale order not packed yet."""
        for picking in self:
            if not picking.sale_id:
                raise UserError(_('No Sales Order linked to this Delivery.'))
            so = picking.sale_id
            pallets = self.env['advmfg.pallet'].search([
                ('state', '=', 'confirmed'),
                '|', ('production_id.sale_order_id', '=', so.id), ('production_id.origin', '=', so.name)])
            used = self.env['advmfg.delivery.pack'].search([]).pallet_ids
            free = pallets - used
            if not free:
                raise UserError(_('No confirmed pallets are waiting to be packed for %s.', so.name))
            for pallet in free:
                self.env['advmfg.delivery.pack'].create({'picking_id': picking.id, 'pallet_ids': [(6, 0, pallet.ids)]})
        return True

    def action_advmfg_print_packs(self):
        """Print the pack list of this delivery."""
        self.ensure_one()
        if not self.advmfg_pack_ids:
            raise UserError(_('No packs have been generated for this delivery.'))
        return self.env.ref('advance_manufacturing.action_report_advmfg_delivery_packs').report_action(self)

    def button_validate(self):
        """Delivery checks before validating: vehicle/driver details and confirmed packs."""
        for picking in self.filtered('advmfg_active'):
            missing = [label for label, val in (
                (_('Driver Name'), picking.advmfg_driver_name),
                (_('Vehicle Number'), picking.advmfg_vehicle_number),
                (_('Estimated Arrival Time'), picking.advmfg_estimated_arrival)) if not val]
            if missing:
                raise UserError(_('Please fill in the dispatch details before validating: %s.', ', '.join(missing)))
            if any(p.state != 'confirmed' for p in picking.advmfg_pack_ids):
                raise UserError(_('You cannot validate this delivery until all generated packs are confirmed.'))
        res = super().button_validate()
        if res is True:
            for picking in self.filtered(lambda p: p.advmfg_active and p.state == 'done'):
                picking.advmfg_dispatch_time = picking.advmfg_dispatch_time or fields.Datetime.now()
                picking.advmfg_delivered_on = picking.advmfg_delivered_on or picking.date_done or fields.Datetime.now()
                picking._advmfg_mark_serials_delivered()
        return res

    def _advmfg_mark_serials_delivered(self):
        """After delivery: mark as many of the order's serial numbers 'delivered' as were shipped."""
        self.ensure_one()
        for move in self.move_ids.filtered(lambda m: m.state == 'done' and m.sale_line_id):
            qty = int(move.quantity)
            serials = self.env['advmfg.so.serial'].search([
                ('line_id', '=', move.sale_line_id.id), ('state', '=', 'assigned')], limit=qty)
            serials.write({'state': 'delivered'})
