from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class UgRecordWeights(models.TransientModel):
    """ Weighing-station screen: actual input and outputs of a recycling order,
    with the live mass balance, then finish the order. """
    _name = 'ug.record.weights'
    _description = 'Record Actual Weights'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade')
    stage = fields.Selection(related='production_id.ug_stage')
    product_id = fields.Many2one(related='production_id.product_id', string='Main Product')
    input_line_ids = fields.One2many('ug.record.weights.input', 'wizard_id', string='Input')
    main_qty_kg = fields.Float('Main Product (kg)', digits='Product Unit of Measure')
    main_expected_kg = fields.Float('Planned (kg)', digits='Product Unit of Measure', readonly=True)
    byproduct_line_ids = fields.One2many('ug.record.weights.byproduct', 'wizard_id', string='By-products')
    override_weights = fields.Boolean('Confirm weights anyway',
        help="Recycling Manager only: finish the order although the output is more than the input.")

    input_kg = fields.Float('Input (kg)', compute='_compute_balance', digits='Product Unit of Measure')
    output_kg = fields.Float('Output (kg)', compute='_compute_balance', digits='Product Unit of Measure')
    loss_kg = fields.Float('Loss (kg)', compute='_compute_balance', digits='Product Unit of Measure')
    loss_pct = fields.Float('Loss (%)', compute='_compute_balance', digits=(16, 2))
    max_loss_pct = fields.Float(related='production_id.bom_id.ug_max_loss_pct')
    yield_pct = fields.Float('Yield (%)', compute='_compute_balance', digits=(16, 2))
    standard_yield_pct = fields.Float(related='production_id.bom_id.ug_standard_yield_pct')
    yield_min_pct = fields.Float(related='production_id.bom_id.ug_yield_min_pct')
    yield_max_pct = fields.Float(related='production_id.bom_id.ug_yield_max_pct')
    status = fields.Selection([('ok', 'OK'), ('warning', 'Warning'), ('blocked', 'Blocked')],
        compute='_compute_balance')
    status_message = fields.Char(compute='_compute_balance')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        production = self.env['mrp.production'].browse(res.get('production_id'))
        if not production:
            return res
        if not production.bom_id.ug_is_recycling or production.state not in ('confirmed', 'progress', 'to_close'):
            raise UserError(_("Weights can only be recorded on confirmed recycling orders."))
        primary = production.move_raw_ids.filtered(
            lambda m: m.bom_line_id.ug_is_primary_input and m.state not in ('done', 'cancel'))
        if not primary.move_line_ids:
            raise UserError(_("Reserve the input lots of %s first (Check availability).", production.name))
        planned_kg = production.product_uom_id._ug_to_kg(production.product_qty - production.qty_produced)
        res.update({
            'input_line_ids': [Command.create({
                'move_line_id': ml.id,
                'lot_id': ml.lot_id.id,
                'product_id': ml.product_id.id,
                'qty_kg': ml.product_uom_id._ug_to_kg(ml.quantity),
            }) for ml in primary.move_line_ids],
            'main_expected_kg': planned_kg,
            'main_qty_kg': production.product_uom_id._ug_to_kg(production.qty_producing) or planned_kg,
            'byproduct_line_ids': [Command.create({
                'move_id': move.id,
                'product_id': move.product_id.id,
                'expected_kg': move.product_uom._ug_to_kg(move.product_uom_qty),
                'qty_kg': move.product_uom._ug_to_kg(move.quantity if move.picked else move.product_uom_qty),
            }) for move in production.move_byproduct_ids.filtered(lambda m: m.state not in ('done', 'cancel'))],
        })
        return res

    @api.depends('input_line_ids.qty_kg', 'main_qty_kg', 'byproduct_line_ids.qty_kg', 'override_weights')
    def _compute_balance(self):
        for wizard in self:
            bom = wizard.production_id.bom_id
            input_kg = sum(wizard.input_line_ids.mapped('qty_kg'))
            output_kg = wizard.main_qty_kg + sum(wizard.byproduct_line_ids.mapped('qty_kg'))
            loss = input_kg - output_kg
            loss_pct = input_kg and loss / input_kg * 100 or 0.0
            yield_pct = input_kg and wizard.main_qty_kg / input_kg * 100 or 0.0
            weight_stage = wizard.production_id.ug_stage in ('dismantle', 'shred')
            messages, status = [], 'ok'
            if weight_stage and input_kg and output_kg > input_kg + 0.01:
                status = 'blocked'
                messages.append(_("Output is more than the input: check the scale."))
            if loss_pct > bom.ug_max_loss_pct and status != 'blocked':
                status = 'warning'
                messages.append(_("Loss above the %(max).1f %% allowed.", max=bom.ug_max_loss_pct))
            if bom._ug_check_yield() and input_kg and not (bom.ug_yield_min_pct <= yield_pct <= bom.ug_yield_max_pct):
                status = 'warning' if status == 'ok' else status
                messages.append(_("Yield outside %(min).1f – %(max).1f %%.",
                                  min=bom.ug_yield_min_pct, max=bom.ug_yield_max_pct))
            wizard.update({
                'input_kg': input_kg,
                'output_kg': output_kg,
                'loss_kg': loss,
                'loss_pct': loss_pct,
                'yield_pct': yield_pct,
                'status': status,
                'status_message': " ".join(messages) or _("Weights within the expected range."),
            })

    def action_confirm(self):
        self.ensure_one()
        production = self.production_id
        weights = self.input_line_ids.mapped('qty_kg') + self.byproduct_line_ids.mapped('qty_kg')
        if self.main_qty_kg < 0 or any(qty < 0 for qty in weights):
            raise UserError(_("Weights cannot be negative."))
        if production.product_uom_id._ug_is_zero(production.product_uom_id._ug_from_kg(self.main_qty_kg)):
            raise UserError(_("Enter the weight of %s produced.", production.product_id.display_name))
        if self.override_weights and not self.env.user.has_group('ug_recycling_base.group_ug_manager'):
            raise UserError(_("Only a Recycling Manager can confirm weights where the output exceeds the input."))

        production.qty_producing = production.product_uom_id._ug_from_kg(self.main_qty_kg) + production.qty_produced
        production._set_qty_producing()
        for line in self.input_line_ids:
            line.move_line_id.quantity = line.move_line_id.product_uom_id._ug_from_kg(line.qty_kg)
        primary = self.input_line_ids.move_line_id.move_id
        primary.picked = True
        for line in self.byproduct_line_ids:
            line.move_id._set_quantity_done(line.move_id.product_uom._ug_from_kg(line.qty_kg))
            line.move_id.picked = True
        production.message_post(body=_(
            "Weights recorded: input %(inp).2f kg, output %(out).2f kg (loss %(loss).2f %%, yield %(yld).2f %%).",
            inp=self.input_kg, out=self.output_kg, loss=self.loss_pct, yld=self.yield_pct))
        return production.with_context(ug_weights_override=self.override_weights).button_mark_done()


class UgRecordWeightsInput(models.TransientModel):
    _name = 'ug.record.weights.input'
    _description = 'Record Weights – Input Lot'

    wizard_id = fields.Many2one('ug.record.weights', required=True, ondelete='cascade')
    move_line_id = fields.Many2one('stock.move.line', required=True)
    lot_id = fields.Many2one('stock.lot', string='Lot', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    qty_kg = fields.Float('Consumed (kg)', digits='Product Unit of Measure')


class UgRecordWeightsByproduct(models.TransientModel):
    _name = 'ug.record.weights.byproduct'
    _description = 'Record Weights – By-product'

    wizard_id = fields.Many2one('ug.record.weights', required=True, ondelete='cascade')
    move_id = fields.Many2one('stock.move', required=True)
    product_id = fields.Many2one('product.product', readonly=True)
    expected_kg = fields.Float('Planned (kg)', digits='Product Unit of Measure', readonly=True)
    qty_kg = fields.Float('Actual (kg)', digits='Product Unit of Measure')
