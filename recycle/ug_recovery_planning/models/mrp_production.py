from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ug_input_lot_line_ids = fields.One2many('ug.production.input.lot', 'production_id', string='Input Lots',
        copy=False)
    ug_recovery_line_ids = fields.One2many('ug.production.recovery.line', 'production_id', string='Recovery',
        copy=False)
    ug_input_lots_kg = fields.Float('Input Lots (kg)', compute='_compute_ug_input_lots_kg', digits='Product Unit of Measure')

    @api.depends('ug_input_lot_line_ids.qty_kg')
    def _compute_ug_input_lots_kg(self):
        for production in self:
            production.ug_input_lots_kg = sum(production.ug_input_lot_line_ids.mapped('qty_kg'))

    def write(self, vals):
        res = super().write(vals)
        if 'ug_input_lot_line_ids' in vals and 'ug_recovery_line_ids' not in vals:
            # the snapshot no longer matches the input lots: compute again
            stale = self.filtered(lambda p: p.state == 'draft' and p.ug_recovery_line_ids)
            stale.ug_recovery_line_ids = [Command.clear()]
            # dismantle / shred: the input weight follows the selected lots
            for production in self.filtered(lambda p: p.state == 'draft' and p.ug_is_recycling
                                            and p.ug_stage != 'recover' and p.ug_input_lot_line_ids):
                if production.product_uom_id._ug_compare(production.ug_input_qty, production.ug_input_lots_kg) != 0:
                    production.ug_input_qty = production.ug_input_lots_kg
        return res

    # ------------------------------------------------------------------
    # Expected outputs from assay
    # ------------------------------------------------------------------
    def _ug_recovery_values(self):
        """ One dict per BoM recovery line, from the current assay of each input lot. """
        self.ensure_one()
        values = []
        for rate in self.bom_id.ug_recovery_line_ids:
            contained = 0.0
            for input_line in self.ug_input_lot_line_ids:
                assay_line = input_line.lot_id.ug_current_assay_id.line_ids.filtered(
                    lambda l: l.element_id == rate.element_id)
                contained += input_line.qty_kg * sum(assay_line.mapped('percentage')) / 100.0
            content = rate.output_product_id.ug_metal_content_pct
            if not content:
                raise UserError(_("Set the metal content of %s before computing expected outputs.",
                                  rate.output_product_id.display_name))
            expected_metal = contained * rate.recovery_pct / 100.0
            values.append({
                'sequence': rate.sequence,
                'element_id': rate.element_id.id,
                'output_product_id': rate.output_product_id.id,
                'contained_kg': contained,
                'recovery_pct': rate.recovery_pct,
                'metal_content_pct': content,
                'expected_metal_kg': expected_metal,
                'expected_qty_kg': expected_metal / (content / 100.0),
            })
        return values

    def action_ug_compute_expected(self):
        for production in self:
            if production.state != 'draft':
                raise UserError(_("Expected outputs can only be computed on draft manufacturing orders."))
            if production.ug_stage != 'recover':
                raise UserError(_("Expected outputs from assay are only available on recover-stage orders."))
            if not production.ug_input_lot_line_ids:
                raise UserError(_("Add the input lots of black mass first."))
            if not production.bom_id.ug_recovery_line_ids:
                raise UserError(_("Define recovery rates on BoM %s.", production.bom_id.display_name))
            not_approved = production.ug_input_lot_line_ids.lot_id.filtered(lambda l: l.ug_assay_state != 'approved')
            if not_approved:
                raise UserError(_("These lots have no approved assay: %s", ", ".join(not_approved.mapped('name'))))

            values = production._ug_recovery_values()
            production.ug_recovery_line_ids = [Command.clear()] + [Command.create(v) for v in values]

            # 1. main product first: standard Odoo recomputes components and by-products
            main = production.ug_recovery_line_ids.filtered(lambda l: l.output_product_id == production.product_id)[:1]
            if main and production.product_uom_id._ug_is_zero(production.product_uom_id._ug_from_kg(main.expected_qty_kg)):
                zero_lots = production.ug_input_lot_line_ids.lot_id.filtered(lambda lot: not any(
                    lot.ug_current_assay_id.line_ids.filtered(lambda l: l.element_id == main.element_id).mapped('percentage')))
                raise UserError(_(
                    "The expected quantity of %(product)s is 0: the approved assay of lot(s) %(lots)s shows 0 %% %(element)s. "
                    "Create and approve a corrected assay for the lot, then try again.",
                    product=main.output_product_id.display_name,
                    lots=", ".join(zero_lots.mapped('name')) or "-",
                    element=main.element_id.display_name))
            if main:
                production.product_qty = production.product_uom_id._ug_from_kg(main.expected_qty_kg)
            # 2. then force input / by-product demands; the move-value hooks below keep
            #    them when the draft moves are recomputed again later (e.g. date change)
            production._ug_apply_expected_quantities()
        return True

    def _ug_input_factor(self):
        """ Ratio between the selected input lots and the BoM primary input quantity. """
        self.ensure_one()
        primary = self._ug_primary_line()
        if not primary or not primary.product_qty:
            return 0.0
        return primary.product_uom_id._ug_from_kg(self.ug_input_lots_kg) / primary.product_qty

    def _ug_use_expected(self):
        self.ensure_one()
        return self.ug_stage == 'recover' and bool(self.ug_recovery_line_ids) and bool(self.ug_input_lot_line_ids)

    def _ug_expected_byproduct_qty(self, product, uom):
        line = self.ug_recovery_line_ids.filtered(lambda l: l.output_product_id == product)[:1]
        return line and uom._ug_from_kg(line.expected_qty_kg)

    def _ug_apply_expected_quantities(self):
        for production in self.filtered(lambda p: p.state == 'draft' and p._ug_use_expected()):
            factor = production._ug_input_factor()
            for move in production.move_raw_ids.filtered('bom_line_id'):
                move.product_uom_qty = move.bom_line_id.product_qty * factor
            outputs = production.ug_recovery_line_ids.output_product_id
            for move in production.move_byproduct_ids.filtered(lambda m: m.product_id in outputs):
                move.product_uom_qty = production._ug_expected_byproduct_qty(move.product_id, move.product_uom) or 0.0

    def _get_moves_raw_values(self):
        moves = super()._get_moves_raw_values()
        productions = {p.id: p for p in self}
        for vals in moves:
            production = productions.get(vals.get('raw_material_production_id'))
            if not production or not production._ug_use_expected():
                continue
            bom_line = self.env['mrp.bom.line'].browse(vals.get('bom_line_id'))
            if bom_line:
                vals['product_uom_qty'] = bom_line.product_qty * production._ug_input_factor()
        return moves

    def _get_moves_finished_values(self):
        moves = super()._get_moves_finished_values()
        productions = {p.id: p for p in self}
        for vals in moves:
            if not vals.get('byproduct_id'):
                continue
            production = productions.get(vals.get('production_id'))
            if not production or not production._ug_use_expected():
                continue
            product = self.env['product.product'].browse(vals['product_id'])
            if product in production.ug_recovery_line_ids.output_product_id:
                uom = self.env['uom.uom'].browse(vals['product_uom'])
                vals['product_uom_qty'] = production._ug_expected_byproduct_qty(product, uom) or 0.0
        return moves

    # ------------------------------------------------------------------
    # Confirmation: reserve the chosen input lots
    # ------------------------------------------------------------------
    def action_confirm(self):
        res = super().action_confirm()
        self.filtered(lambda p: p.ug_is_recycling and p.ug_input_lot_line_ids
                      and p.state not in ('draft', 'cancel', 'done'))._ug_reserve_input_lots()
        return res

    def _ug_reserve_input_lots(self):
        """ Pre-fill the lots of the primary input move with the selected input lots. """
        for production in self:
            move = production.move_raw_ids.filtered(
                lambda m: m.bom_line_id.ug_is_primary_input and m.state not in ('done', 'cancel'))[:1]
            if not move or not move.product_id.is_storable:
                continue
            move._do_unreserve()
            for input_line in production.ug_input_lot_line_ids:
                need = move.product_id.uom_id._ug_from_kg(input_line.qty_kg)
                taken = move._update_reserved_quantity(need, move.location_id, lot_id=input_line.lot_id, strict=False)
                if move.product_id.uom_id._ug_compare(taken, need) < 0:
                    production.message_post(body=_(
                        "Only %(taken)s of %(need)s kg could be reserved from lot %(lot)s.",
                        taken=taken, need=need, lot=input_line.lot_id.name))
            move._recompute_state()

    # ------------------------------------------------------------------
    # Recycling chain: draft orders link through their selected input lots
    # ------------------------------------------------------------------
    def _ug_consumed_lots(self):
        return super()._ug_consumed_lots() | self.ug_input_lot_line_ids.lot_id

    @api.model
    def _ug_consumers_of(self, lots):
        consumers = super()._ug_consumers_of(lots)
        if lots:
            consumers |= self.env['ug.production.input.lot'].search([
                ('lot_id', 'in', lots.ids), ('production_id.state', '!=', 'cancel')]).production_id
        return consumers

    # ------------------------------------------------------------------
    # Next stage, from the order itself
    # ------------------------------------------------------------------
    ug_next_queue_ids = fields.Many2many('ug.process.queue', compute='_compute_ug_next_queue',
        string='Next Stage', help="Lots produced by this order that are waiting for their next recycling stage.")
    ug_next_ready = fields.Boolean(compute='_compute_ug_next_queue')
    ug_next_waiting_lab = fields.Boolean(compute='_compute_ug_next_queue')

    @api.depends('state', 'lot_producing_id', 'move_finished_ids.move_line_ids.lot_id')
    def _compute_ug_next_queue(self):
        Queue = self.env['ug.process.queue']
        self.env.flush_all()  # the queue is an SQL view on quants and draft input lots
        for production in self:
            rows = Queue
            if production._origin and production.state == 'done' and production.ug_is_recycling:
                lots = production._origin._ug_produced_lots()
                rows = Queue.search([('lot_id', 'in', lots.ids)]) if lots else Queue
            production.ug_next_queue_ids = rows
            production.ug_next_ready = any(rows.mapped('ready'))
            production.ug_next_waiting_lab = bool(rows) and not all(rows.mapped('ready'))

    def action_ug_create_next_mo(self):
        self.ensure_one()
        rows = self.ug_next_queue_ids
        if not rows:
            raise UserError(_("The lots produced by %s have already been planned or consumed.", self.name))
        waiting = rows.filtered(lambda r: not r.ready)
        if waiting:
            raise UserError(_(
                "Lot(s) %s are waiting for the lab: approve the assay (Assays button) before creating the next order.",
                ", ".join(waiting.lot_id.mapped('name'))))
        return rows.action_create_production()
