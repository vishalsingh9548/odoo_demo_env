from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    battery_chemistry_id = fields.Many2one(related='bom_id.battery_chemistry_id', store=True, index=True)
    ug_is_recycling = fields.Boolean(related='bom_id.ug_is_recycling', store=True, index=True, string='Recycling MO')
    ug_stage = fields.Selection(related='bom_id.ug_stage', store=True, index=True, string='Recycling Stage')

    # 1.4 plan by input weight
    ug_input_qty = fields.Float('Input Weight (kg)', digits='Product Unit of Measure',
        compute='_compute_ug_input_qty', inverse='_inverse_ug_input_qty', store=True, readonly=False,
        help="Weight of primary input to process. Changing it rescales the quantity to produce "
             "(and so every component and by-product) from the BoM ratio.")

    # 1.5 mass balance (filled once the MO is done)
    ug_input_weight_kg = fields.Float('Input Weight Consumed (kg)', compute='_compute_ug_mass_balance', store=True, digits='Product Unit of Measure')
    ug_output_weight_kg = fields.Float('Output Weight Produced (kg)', compute='_compute_ug_mass_balance', store=True, digits='Product Unit of Measure')
    ug_loss_kg = fields.Float('Process Loss (kg)', compute='_compute_ug_mass_balance', store=True, digits='Product Unit of Measure')
    ug_loss_pct = fields.Float('Process Loss (%)', compute='_compute_ug_mass_balance', store=True, digits=(16, 2), aggregator='avg')
    ug_loss_exceeded = fields.Boolean('Loss Exceeded', compute='_compute_ug_mass_balance', store=True, index=True)
    ug_max_loss_pct = fields.Float(related='bom_id.ug_max_loss_pct', string='Max Loss (%)')
    ug_yield_pct = fields.Float('Yield (%)', compute='_compute_ug_mass_balance', store=True, digits=(16, 2),
        aggregator='avg', help="Main product kg per 100 kg of primary input consumed.")
    ug_yield_out_of_band = fields.Boolean('Yield Out of Range', compute='_compute_ug_mass_balance', store=True,
        index=True, help="Dismantle / shred orders whose yield is outside the BoM yield range.")
    ug_standard_yield_pct = fields.Float(related='bom_id.ug_standard_yield_pct', string='Standard Yield (%)')
    ug_yield_min_pct = fields.Float(related='bom_id.ug_yield_min_pct', string='Min Yield (%)')
    ug_yield_max_pct = fields.Float(related='bom_id.ug_yield_max_pct', string='Max Yield (%)')

    # ------------------------------------------------------------------
    # Input weight <-> quantity to produce
    # ------------------------------------------------------------------
    def _ug_primary_line(self):
        self.ensure_one()
        return self.bom_id.ug_is_recycling and self.bom_id.bom_line_ids.filtered('ug_is_primary_input')[:1]

    def _ug_product_qty_from_input(self, input_kg):
        """ Quantity to produce (in the MO unit) for `input_kg` of primary input. """
        self.ensure_one()
        line = self._ug_primary_line()
        if not line or not line.product_qty:
            return self.product_qty
        input_line_uom = line.product_uom_id._ug_from_kg(input_kg)
        qty_bom_uom = input_line_uom * self.bom_id.product_qty / line.product_qty
        return self.bom_id.product_uom_id._compute_quantity(qty_bom_uom, self.product_uom_id or self.bom_id.product_uom_id, round=False)

    def _ug_input_from_product_qty(self, product_qty):
        self.ensure_one()
        line = self._ug_primary_line()
        if not line or not self.bom_id.product_qty:
            return 0.0
        qty_bom_uom = (self.product_uom_id or self.bom_id.product_uom_id)._compute_quantity(product_qty, self.bom_id.product_uom_id, round=False)
        line_qty = qty_bom_uom * line.product_qty / self.bom_id.product_qty
        return line.product_uom_id._ug_to_kg(line_qty, warn_label=line.product_id.display_name)

    @api.depends('product_qty', 'product_uom_id', 'bom_id', 'bom_id.ug_is_recycling')
    def _compute_ug_input_qty(self):
        for production in self:
            if production.bom_id.ug_is_recycling:
                production.ug_input_qty = production._ug_input_from_product_qty(production.product_qty)
            else:
                production.ug_input_qty = 0.0

    def _inverse_ug_input_qty(self):
        for production in self:
            if production.state != 'draft' or not production.bom_id.ug_is_recycling or not production.ug_input_qty:
                continue
            new_qty = production._ug_product_qty_from_input(production.ug_input_qty)
            if production.product_uom_id._ug_compare(new_qty, production.product_qty) != 0:
                production.product_qty = new_qty

    @api.onchange('ug_input_qty')
    def _onchange_ug_input_qty(self):
        if self.state == 'draft' and self.bom_id.ug_is_recycling and self.ug_input_qty:
            new_qty = self._ug_product_qty_from_input(self.ug_input_qty)
            if self.product_uom_id._ug_compare(new_qty, self.product_qty) != 0:
                self.product_qty = new_qty

    def action_ug_change_input_qty(self):
        """ Confirmed MOs: open the standard 'change quantity' wizard, which can
        be driven by input weight (see change.production.qty extension). """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mrp.action_change_production_qty')
        action['context'] = {
            'default_mo_id': self.id,
            'default_product_qty': self.product_qty,
        }
        return action

    # ------------------------------------------------------------------
    # Mass balance
    # ------------------------------------------------------------------
    @api.depends('state', 'bom_id.ug_max_loss_pct', 'bom_id.ug_yield_tolerance_pct',
                 'move_raw_ids.state', 'move_raw_ids.quantity',
                 'move_finished_ids.state', 'move_finished_ids.quantity')
    def _compute_ug_mass_balance(self):
        for production in self:
            vals = {
                'ug_input_weight_kg': 0.0, 'ug_output_weight_kg': 0.0,
                'ug_loss_kg': 0.0, 'ug_loss_pct': 0.0, 'ug_loss_exceeded': False,
                'ug_yield_pct': 0.0, 'ug_yield_out_of_band': False,
            }
            if production.state == 'done' and production.bom_id.ug_is_recycling:
                input_moves = production.move_raw_ids.filtered(
                    lambda m: m.state == 'done' and m.bom_line_id.ug_is_primary_input)
                output_moves = production.move_finished_ids.filtered(lambda m: m.state == 'done')
                input_kg = production._ug_moves_kg(input_moves)
                output_kg = production._ug_moves_kg(output_moves)
                loss = input_kg - output_kg
                loss_pct = input_kg and loss / input_kg * 100 or 0.0
                main_kg = production._ug_moves_kg(output_moves.filtered(lambda m: m.product_id == production.product_id))
                yield_pct = input_kg and main_kg / input_kg * 100 or 0.0
                bom = production.bom_id
                vals.update({
                    'ug_yield_pct': yield_pct,
                    'ug_yield_out_of_band': bool(input_kg) and bom._ug_check_yield() and not (
                        bom.ug_yield_min_pct <= yield_pct <= bom.ug_yield_max_pct),
                    'ug_input_weight_kg': input_kg,
                    'ug_output_weight_kg': output_kg,
                    'ug_loss_kg': loss,
                    'ug_loss_pct': loss_pct,
                    'ug_loss_exceeded': bool(input_kg) and loss_pct > production.bom_id.ug_max_loss_pct,
                })
            production.update(vals)

    @api.model
    def _ug_moves_kg(self, moves):
        return sum(
            move.product_uom._ug_to_kg(move.quantity, warn_label=f"{move.reference} / {move.product_id.display_name}")
            for move in moves
        )

    # ------------------------------------------------------------------
    # Done hooks
    # ------------------------------------------------------------------
    # Actual weights: input stays fixed, no backorder / consumption pop-ups
    # ------------------------------------------------------------------
    def _set_qty_producing(self, pick_manual_consumption_moves=True):
        """ Standard Odoo rescales every component and by-product to the quantity
        produced. In recycling the input is what was weighed in (1,000 kg of packs
        stay 1,000 kg even when only 300 kg of cells come out), and by-products
        depend on the input, not on the main output: keep them at their planned
        quantity unless the operator already entered an actual one (picked). """
        if not self.bom_id.ug_is_recycling:
            return super()._set_qty_producing(pick_manual_consumption_moves)
        moves = (self.move_raw_ids | self.move_byproduct_ids).filtered(lambda m: m.state not in ('done', 'cancel'))
        # Odoo 18 also rescales picked moves: remember what the operator entered
        entered = {
            move: {ml: ml.quantity for ml in move.move_line_ids} or {False: move.quantity}
            for move in moves.filtered('picked')}
        keep = moves.filtered(lambda m: not m.picked)
        res = super()._set_qty_producing(pick_manual_consumption_moves)
        for move, quantities in entered.items():
            for ml, qty in quantities.items():
                if ml and ml.exists():
                    if move.product_uom._ug_compare(ml.quantity, qty) != 0:
                        ml.quantity = qty
                elif not ml and move.product_uom._ug_compare(move.quantity, qty) != 0:
                    move._set_quantity_done(qty)
            move.picked = True
        for move in keep:
            if move.product_uom._ug_compare(move.quantity, move.product_uom_qty) != 0:
                move._set_quantity_done(move.product_uom_qty)
            if pick_manual_consumption_moves and move.raw_material_production_id and move.quantity:
                move.picked = True
        return res

    def _get_consumption_issues(self):
        # unequal input and output is normal in recycling: no consumption warning
        return super(MrpProduction, self.filtered(lambda p: not p.bom_id.ug_is_recycling))._get_consumption_issues()

    def _get_quantity_produced_issues(self):
        # the input is processed in one go: producing less than planned never leaves a backorder
        return super(MrpProduction, self.filtered(lambda p: not p.bom_id.ug_is_recycling))._get_quantity_produced_issues()

    def _ug_pending_weights_kg(self):
        """ (input kg, output kg) about to be posted, for checks before done. """
        self.ensure_one()
        primary = self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel') and m.bom_line_id.ug_is_primary_input)
        outputs = self.move_finished_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        main = outputs.filtered(lambda m: m.product_id == self.product_id)
        main_kg = self.product_uom_id._ug_to_kg(self.qty_producing - self.qty_produced) if main else 0.0
        return self._ug_moves_kg(primary), main_kg + self._ug_moves_kg(outputs - main)

    def _ug_check_weights(self):
        """ Dismantling and shredding cannot create mass: more output than input is a weighing error. """
        override = self.env.context.get('ug_weights_override') and \
            self.env.user.has_group('ug_recycling_base.group_ug_user')
        for production in self.filtered(lambda p: p.bom_id.ug_is_recycling and p.ug_stage in ('dismantle', 'shred')):
            input_kg, output_kg = production._ug_pending_weights_kg()
            if input_kg and output_kg > input_kg + 0.01 and not override:
                raise UserError(_(
                    "%(mo)s: the output (%(out).2f kg) is more than the input (%(inp).2f kg). Dismantling and "
                    "shredding cannot add weight; check the scale and the quantities entered. A Recycling "
                    "Manager can confirm the weights anyway from Record Weights.",
                    mo=production.name, out=output_kg, inp=input_kg))

    # ------------------------------------------------------------------
    # Done hooks
    # ------------------------------------------------------------------
    def pre_button_mark_done(self):
        self._ug_assign_byproduct_lots()
        res = super().pre_button_mark_done()
        if res is True:
            self._ug_check_weights()
        return res

    def action_ug_record_weights(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Record Weights – %s", self.name),
            'res_model': 'ug.record.weights',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_id': self.id},
        }

    def _ug_assign_byproduct_lots(self):
        """ Recycling MOs produce a lot-tracked main product and many lot-tracked
        by-products: create the main lot, then one lot per
        by-product move when the operator did not set one, so marking done is
        not blocked. Lot name: <MO>-<product reference>. """
        for production in self.filtered(lambda p: p.bom_id.ug_is_recycling):
            if production.product_id.tracking == 'lot' and not production.lot_producing_id:
                # Odoo 18 does not generate the lot of the main product by itself
                code = production.product_id.default_code or 'LOT'
                production.lot_producing_id = self.env['stock.lot'].create({
                    'name': f"{code}-{production.name.split('/')[-1]}",
                    'product_id': production.product_id.id,
                    'company_id': production.company_id.id,
                })
            for move in production.move_byproduct_ids.filtered(
                    lambda m: m.state not in ('done', 'cancel') and m.has_tracking == 'lot'):
                lines = move.move_line_ids.filtered(lambda ml: not ml.lot_id and not ml.lot_name)
                if not lines:
                    continue
                code = move.product_id.default_code or str(move.product_id.id)
                lot = self.env['stock.lot'].create({
                    'name': f"{production.name}-{code}",
                    'product_id': move.product_id.id,
                    'company_id': production.company_id.id,
                })
                lines.lot_id = lot

    def button_mark_done(self):
        not_done = self.filtered(lambda p: p.state != 'done')
        res = super().button_mark_done()
        newly_done = not_done.filtered(lambda p: p.state == 'done')
        if newly_done:
            newly_done._ug_on_done()
        return res

    def _ug_on_done(self):
        """ Hook called once for MOs that just became done. """
        self._ug_alert_loss_exceeded()
        self._ug_alert_yield()

    def _ug_alert_yield(self):
        managers = self.env['res.users'].search([('groups_id', 'in', self.env.ref('ug_recycling_base.group_ug_user').ids)]).filtered(
            lambda u: not u.share and u.active)
        for production in self.filtered('ug_yield_out_of_band'):
            message = _(
                "Yield %(actual).2f%% is outside the expected range %(min).2f%% – %(max).2f%% "
                "(standard %(std).2f%%) of BoM %(bom)s.",
                actual=production.ug_yield_pct, min=production.ug_yield_min_pct, max=production.ug_yield_max_pct,
                std=production.ug_standard_yield_pct, bom=production.bom_id.display_name)
            production.message_post(body=message)
            for user in managers.filtered(lambda u: production.company_id in u.company_ids):
                production.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Yield out of range"),
                    note=message,
                    user_id=user.id,
                )

    def _ug_alert_loss_exceeded(self):
        managers = self.env['res.users'].search([('groups_id', 'in', self.env.ref('ug_recycling_base.group_ug_user').ids)]).filtered(
            lambda u: not u.share and u.active)
        for production in self.filtered('ug_loss_exceeded'):
            message = _(
                "Process loss %(loss).2f%% (%(kg).2f kg) exceeds the maximum of %(max).2f%% set on BoM %(bom)s.",
                loss=production.ug_loss_pct, kg=production.ug_loss_kg,
                max=production.bom_id.ug_max_loss_pct, bom=production.bom_id.display_name)
            production.message_post(body=message)
            for user in managers.filtered(lambda u: production.company_id in u.company_ids):
                production.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Process loss exceeded"),
                    note=message,
                    user_id=user.id,
                )
