from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MrpProduction(models.Model):
    """Adds the unit-by-unit tools to the standard manufacturing order.

    Every special rule below first checks the master switch. If it is OFF for the
    company or the user, the standard Odoo behaviour runs untouched.
    """
    _inherit = 'mrp.production'

    # True when the special mode is on for this order's company and the current user.
    advmfg_active = fields.Boolean(compute='_compute_advmfg_active')
    # The factory floor where this order is built (a manufacturing operation type).
    advmfg_floor_id = fields.Many2one(
        'stock.picking.type', string='Floor', domain="[('code', '=', 'mrp_operation')]",
        copy=False)
    advmfg_unit_ids = fields.One2many('advmfg.unit', 'production_id', string='Units')
    advmfg_serial_ids = fields.One2many('advmfg.serial', 'production_id', string='Serial Pool')
    advmfg_pallet_ids = fields.One2many('advmfg.pallet', 'production_id', string='Pallets')
    # When a unit is scrapped (grade C), a 1-unit "replacement" order is created and linked here.
    advmfg_parent_mo_id = fields.Many2one('mrp.production', string='Parent Order', copy=False)
    advmfg_child_mo_count = fields.Integer(compute='_compute_advmfg_child_mo_count')
    advmfg_pallet_count = fields.Integer(compute='_compute_advmfg_pallet_count')
    # The sale order and customer this order is being built for.
    sale_order_id = fields.Many2one('sale.order', related='procurement_group_id.sale_id', string='Sale Order',
                                    store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', related='sale_order_id.partner_id', string='Customer',
                                 store=True, readonly=True)
    # How many units this order must produce in total.
    total_manufacturing_quantity = fields.Float(string='Total Manufacturing Quantity', compute='_compute_total_quantity', store=True,
                                                help='Total quantity this order has to produce.')
    # Units that have started but are not finished or cancelled.
    uncompleted_lines_count = fields.Integer(string='Uncompleted Serial Count', compute='_compute_uncompleted_lines_count')
    scrap_count_units = fields.Integer(string='Scrap Orders', compute='_compute_scrap_count_units')
    # True for a Quality-only user (cannot plan, cannot see the Units tab unless given tab access).
    is_quality_user_only = fields.Boolean(compute='_compute_is_quality_user_only')
    date_finished = fields.Datetime(readonly=False)
    advmfg_unit_count = fields.Integer(compute='_compute_advmfg_counts')
    advmfg_done_unit_count = fields.Integer(compute='_compute_advmfg_counts')

    # ------------------------------------------------------------------ computes
    @api.depends('company_id')
    @api.depends_context('uid', 'company')
    def _compute_advmfg_active(self):
        """Fill the 'is the special mode on here?' flag used to show/hide screens."""
        switch = self.env['advmfg.switch']
        for mo in self:
            mo.advmfg_active = switch.is_active(mo.company_id or self.env.company)

    @api.depends('advmfg_pallet_ids')
    def _compute_advmfg_pallet_count(self):
        """How many pallets this order has (shown on the Print Pallet button)."""
        for mo in self:
            mo.advmfg_pallet_count = len(mo.advmfg_pallet_ids)

    def action_advmfg_print_all_pallets(self):
        """Print Pallet button: one PDF with every pallet of this order (one pallet per page)."""
        self.ensure_one()
        if not self.advmfg_pallet_ids:
            raise UserError(_('No pallets have been made for this Manufacturing Order yet.'))
        return self.env.ref('advance_manufacturing.action_report_advmfg_mo_pallets').report_action(self)

    def _compute_advmfg_child_mo_count(self):
        """How many replacement orders were created from this one."""
        for mo in self:
            mo.advmfg_child_mo_count = self.search_count([('advmfg_parent_mo_id', '=', mo.id)])

    @api.depends('advmfg_unit_ids.state')
    def _compute_advmfg_counts(self):
        """Total live units and finished units, shown on the order."""
        for mo in self:
            live = mo.advmfg_unit_ids.filtered(lambda u: u.state != 'cancel')
            mo.advmfg_unit_count = len(live)
            mo.advmfg_done_unit_count = len(live.filtered(lambda u: u.state == 'completed'))

    @api.constrains('product_id')
    def _check_finished_good(self):
        """In Advance Manufacturing mode only products ticked 'Is Finished Good' can be manufactured."""
        for mo in self:
            if self.env['advmfg.switch'].is_active(mo.company_id) and not mo.product_id.product_tmpl_id.is_finished_good:
                raise ValidationError(_('Only products marked "Is Finished Good" can be manufactured.'))

    @api.depends('product_qty')
    def _compute_total_quantity(self):
        """Total quantity follows the order quantity."""
        for mo in self:
            mo.total_manufacturing_quantity = mo.product_qty

    @api.constrains('total_manufacturing_quantity')
    def _check_total_quantity(self):
        """An order must produce more than zero."""
        for mo in self:
            if self.env['advmfg.switch'].is_active(mo.company_id) and mo.total_manufacturing_quantity <= 0:
                raise ValidationError(_('Total Quantity must be greater than 0.'))

    @api.depends('advmfg_unit_ids.state')
    def _compute_uncompleted_lines_count(self):
        """Count units that are actually being worked on."""
        for mo in self:
            mo.uncompleted_lines_count = len(mo.advmfg_unit_ids.filtered(lambda u: u.state == 'in_progress'))

    @api.onchange('advmfg_unit_ids')
    def _onchange_units_qty_producing(self):
        """Producing quantity follows the number of units being worked on (at least 1)."""
        for mo in self:
            mo.qty_producing = mo.uncompleted_lines_count or 1

    @api.depends('advmfg_unit_ids.scrap_ids')
    def _compute_scrap_count_units(self):
        """Number of scrap records created for the units of this order."""
        for mo in self:
            mo.scrap_count_units = len(mo.advmfg_unit_ids.mapped('scrap_ids'))

    def _compute_is_quality_user_only(self):
        """True when the user only has the Quality role (no admin role, no Units-tab access)."""
        user = self.env.user
        only = (user.has_group('advance_manufacturing.group_advmfg_quality_user')
                and not user.has_group('advance_manufacturing.group_advmfg_manager')
                and not user.has_group('advance_manufacturing.group_advmfg_tab_access'))
        for mo in self:
            mo.is_quality_user_only = only

    def action_view_unit_scraps(self):
        """Scrap smart button: open the scrap records of this order's units."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Scrap Orders'), 'res_model': 'stock.scrap',
                'view_mode': 'list,form', 'domain': [('id', 'in', self.advmfg_unit_ids.scrap_ids.ids)]}

    def action_advmfg_bulk_attachments(self):
        """Update Bulk Attachments button: opens the upload-many window."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Update Bulk Attachments'),
                'res_model': 'advmfg.attachment.bulk.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'active_id': self.id}}

    def action_advmfg_print_labels(self):
        """Print barcode labels for every live unit of this order."""
        self.ensure_one()
        return self.advmfg_unit_ids.filtered(lambda u: u.state != 'cancel').action_print_labels()

    # ------------------------------------------------------------------ backorders
    def _split_productions(self, amounts=False, cancel_remaining_qty=False, set_consumed_qty=False):
        """When an order is partly produced, the units not yet started move to the backorder."""
        result = super()._split_productions(amounts=amounts, cancel_remaining_qty=cancel_remaining_qty,
                                            set_consumed_qty=set_consumed_qty)
        switch = self.env['advmfg.switch']
        for backorder in result.filtered(lambda p: p not in self):
            original = result.filtered(lambda p: p in self and p.procurement_group_id == backorder.procurement_group_id)[:1]
            if not original or not switch.is_active(original.company_id):
                continue
            waiting = original.advmfg_unit_ids.filtered(lambda u: u.state == 'yet_to_start')
            waiting[:int(backorder.product_qty)].write({'production_id': backorder.id})
        return result

    # ------------------------------------------------------------------ delivery quantity
    def update_delivery_quantity(self, picking):
        """Once every order of a sale order (and its replacement orders) is done, set the delivery quantity to what was made."""
        order = picking.sale_id
        if not order:
            return
        parents = self.search([('sale_order_id', '=', order.id), ('advmfg_parent_mo_id', '=', False)])
        if not parents or any(mo.state != 'done' for mo in parents):
            return
        quantities = {}
        for mo in parents:
            children = self.search([('advmfg_parent_mo_id', '=', mo.id)])
            if any(child.state != 'done' for child in children):
                return
            quantities[mo.product_id.id] = quantities.get(mo.product_id.id, 0.0) + mo.product_qty + sum(children.mapped('product_qty'))
        for move in picking.move_ids_without_package:
            if move.product_id.id in quantities:
                move.quantity = min(move.product_uom_qty, quantities[move.product_id.id])

    # ------------------------------------------------------------------ floor
    @api.onchange('advmfg_floor_id')
    def _onchange_advmfg_floor_id(self):
        """Choosing a floor sets the order's operation type, so its stock locations follow."""
        if self.advmfg_floor_id and self.advmfg_active:
            self.picking_type_id = self.advmfg_floor_id

    def button_plan(self):
        """Plan button: in special mode a floor must be chosen first."""
        switch = self.env['advmfg.switch']
        for mo in self:
            if switch.is_active(mo.company_id):
                if mo.is_quality_user_only:
                    raise UserError(_('Only Quality Administrators can use the Plan button.'))
                if not mo.advmfg_floor_id:
                    raise ValidationError(_('Floor is required before planning the manufacturing order.'))
        return super().button_plan()

    # ------------------------------------------------------------------ serial numbers
    def action_advmfg_book_serials(self):
        """Book Serial Number: reserve one serial per unit still to be made (the 'serial pool')."""
        self.ensure_one()
        config = self.env['advmfg.serial.prefix'].search([('company_id', '=', self.company_id.id)], limit=1)
        prefix = config.prefix or self.company_id.advmfg_serial_prefix
        if not prefix:
            raise UserError(_('Serial Number Prefix not configured, please configure it first.'))
        missing = int(self.product_qty) - len(self.advmfg_serial_ids)
        if missing <= 0:
            return True  # already booked: nothing to do
        seq = self.env['ir.sequence']
        self.env['advmfg.serial'].create([{
            'name': '%s%s' % (prefix, seq.next_by_code('advmfg.serial')),
            'production_id': self.id,
        } for _i in range(missing)])
        return True

    def action_advmfg_allocate_serials(self):
        """Allocate Serials: turn available pool serials into unit rows (one row per unit to make)."""
        self.ensure_one()
        live_units = self.advmfg_unit_ids.filtered(lambda u: u.state != 'cancel')
        needed = int(self.product_qty) - len(live_units)
        if needed <= 0:
            raise UserError(_('Serials already allocated for this order.'))
        available = self.advmfg_serial_ids.filtered(lambda s: s.state == 'available')[:needed]
        if not available:
            raise UserError(_('Not enough serials available in the Serial Pool. Book serials first.'))
        if not self.env['advmfg.stage'].search_count([('company_id', '=', self.company_id.id)]):
            raise UserError(_('Please create Process Stages first (Manufacturing > Configuration).'))
        self.env['advmfg.unit'].create([{'name': s.name, 'production_id': self.id} for s in available])
        available.write({'state': 'allocated'})
        return True

    # ------------------------------------------------------------------ pallets
    def action_advmfg_new_pallet(self):
        """New Pallet button: create an empty pallet and open it to start adding serials."""
        self.ensure_one()
        pallet = self.env['advmfg.pallet'].create({'production_id': self.id})
        return {
            'type': 'ir.actions.act_window', 'res_model': 'advmfg.pallet',
            'res_id': pallet.id, 'view_mode': 'form',
        }

    def action_advmfg_confirm_packs(self):
        """Confirm Packs: lock every pallet of this order (each needs at least one unit)."""
        self.ensure_one()
        if not self.advmfg_pallet_ids:
            raise UserError(_('Please add at least one pallet before confirming.'))
        self.advmfg_pallet_ids.filtered(lambda p: p.state == 'draft').action_confirm()
        return True

    # ------------------------------------------------------------------ finishing
    def button_mark_done(self):
        """Produce / Mark Done: in special mode every unit must be finished and packed on confirmed pallets.

        We also set the produced quantity to the number of finished units, and (if a packed
        location is configured) send the finished goods straight to that packed area.
        """
        switch = self.env['advmfg.switch']
        for mo in self:
            if not switch.is_active(mo.company_id):
                continue
            live = mo.advmfg_unit_ids.filtered(lambda u: u.state != 'cancel')
            if not live:
                raise ValidationError(_('Manufacturing order %s has no units. Book and allocate serials first.', mo.name))
            unfinished = live.filtered(lambda u: u.state != 'completed')
            if unfinished:
                raise ValidationError(_('These units are not completed yet:\n%s', ', '.join(unfinished.mapped('name'))))
            if not mo.advmfg_pallet_ids:
                raise ValidationError(_(
                    "Manufacturing order '%s' has no pallets. Create pallets and assign serial numbers before producing.",
                    mo.name))
            empty = mo.advmfg_pallet_ids.filtered(lambda p: not p.unit_ids)
            if empty:
                raise ValidationError(_('These pallets have no serial numbers:\n%s', ', '.join(empty.mapped('name'))))
            unpacked = live.filtered(lambda u: not u.pallet_id)
            if unpacked:
                raise ValidationError(_('These units are not on any pallet:\n%s', ', '.join(unpacked.mapped('name'))))
            if mo.advmfg_pallet_ids.filtered(lambda p: p.state != 'confirmed'):
                raise ValidationError(_('Please confirm all pallets (Confirm Packs) before producing.'))
            # Produced quantity = finished units.
            if mo.qty_producing != len(live):
                mo.qty_producing = len(live)
            # Finished goods go to the packed area, if one is configured.
            packed = mo.company_id.advmfg_packed_location_id
            if packed:
                mo.move_finished_ids.filtered(
                    lambda m: m.product_id == mo.product_id and m.state not in ('done', 'cancel')
                ).write({'location_dest_id': packed.id})
        return super().button_mark_done()

    # ------------------------------------------------------------------ scrapped unit -> replacement order
    def _advmfg_split_scrapped_unit(self, unit):
        """After a unit is scrapped (Grade C): shrink this order by 1 and make a 1-unit replacement order.

        The replacement order carries a fresh row with the same serial number, starting again from the first stage.
        If this order only has one unit left, nothing is split.
        """
        self.ensure_one()
        if self.product_qty <= 1:
            return False
        child = self.copy({'product_qty': 1, 'advmfg_parent_mo_id': self.id, 'origin': self.origin or self.name})
        # Use Odoo's own "change quantity" tool so the component lines shrink with the order.
        self.env['change.production.qty'].sudo().with_context(skip_activity=True).create({
            'mo_id': self.id, 'product_qty': self.product_qty - 1}).change_prod_qty()
        self.env['advmfg.unit'].create({'name': unit.name, 'production_id': child.id, 'line_no': '1'})
        return child

    def action_advmfg_view_child_mos(self):
        """Smart button: open the replacement orders made from this order."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Replacement Orders'),
            'res_model': 'mrp.production', 'view_mode': 'list,form',
            'domain': [('advmfg_parent_mo_id', '=', self.id)],
        }
