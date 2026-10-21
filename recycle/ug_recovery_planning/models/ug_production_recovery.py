from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UgProductionInputLot(models.Model):
    _name = 'ug.production.input.lot'
    _description = 'Recover MO Input Lot'
    _order = 'production_id, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    product_id = fields.Many2one('product.product', compute='_compute_product_id', string='Primary Input')
    lot_id = fields.Many2one('stock.lot', string='Lot', required=True,
        domain="[('product_id', '=', product_id), ('ug_assay_state', '!=', 'pending')]",
        help="Recover-stage orders need lots with an approved assay.")
    qty_kg = fields.Float('Quantity (kg)', digits='Product Unit of Measure', required=True)
    available_kg = fields.Float('On Hand (kg)', compute='_compute_available_kg', digits='Product Unit of Measure')
    assay_id = fields.Many2one(related='lot_id.ug_current_assay_id', string='Assay')
    source_production_id = fields.Many2one('mrp.production', compute='_compute_source_production_id',
        string='Source MO', help="Order that produced this lot.")

    @api.depends('lot_id')
    def _compute_source_production_id(self):
        Production = self.env['mrp.production']
        for line in self:
            lot = line.lot_id._origin
            line.source_production_id = Production._ug_producers_of(lot).sorted('id')[:1] if lot else Production

    @api.depends('production_id.bom_id')
    def _compute_product_id(self):
        for line in self:
            primary = line.production_id.bom_id.bom_line_ids.filtered('ug_is_primary_input')[:1]
            line.product_id = primary.product_id

    @api.depends('lot_id')
    def _compute_available_kg(self):
        for line in self:
            line.available_kg = line.lot_id and line.lot_id._ug_qty_kg() or 0.0

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id and not self.qty_kg:
            self.qty_kg = self.lot_id._ug_qty_kg()

    @api.constrains('qty_kg', 'lot_id')
    def _check_line(self):
        for line in self:
            if line.qty_kg <= 0:
                raise ValidationError(_("The input quantity of lot %s must be positive.", line.lot_id.name))
            primary = line.production_id.bom_id.bom_line_ids.filtered('ug_is_primary_input')[:1]
            if primary and line.lot_id.product_id != primary.product_id:
                raise ValidationError(_(
                    "Lot %(lot)s is not a lot of the primary input %(product)s.",
                    lot=line.lot_id.name, product=primary.product_id.display_name))


class UgProductionRecoveryLine(models.Model):
    _name = 'ug.production.recovery.line'
    _description = 'Recover MO Expected vs Actual Output'
    _order = 'production_id, sequence, id'

    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    element_id = fields.Many2one('ug.assay.element', string='Element', required=True, index=True)
    output_product_id = fields.Many2one('product.product', string='Output Product', required=True)
    contained_kg = fields.Float('Contained Metal (kg)', digits='Product Unit of Measure')
    recovery_pct = fields.Float('Recovery (%)', digits=(5, 2))
    metal_content_pct = fields.Float('Metal Content (%)', digits=(6, 3))
    expected_metal_kg = fields.Float('Expected Metal (kg)', digits='Product Unit of Measure')
    expected_qty_kg = fields.Float('Expected Output (kg)', digits='Product Unit of Measure')
    actual_qty_kg = fields.Float('Actual Output (kg)', compute='_compute_actual', store=True, digits='Product Unit of Measure')
    actual_metal_kg = fields.Float('Actual Metal (kg)', compute='_compute_actual', store=True, digits='Product Unit of Measure')
    efficiency_pct = fields.Float('Efficiency (%)', compute='_compute_actual', store=True, digits=(16, 2),
        aggregator='avg', help="Actual metal recovered / metal contained in the input lots.")

    @api.depends('output_product_id', 'metal_content_pct', 'contained_kg',
                 'production_id.move_finished_ids.state', 'production_id.move_finished_ids.quantity')
    def _compute_actual(self):
        for line in self:
            moves = line.production_id.move_finished_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == line.output_product_id)
            qty = self.env['mrp.production']._ug_moves_kg(moves)
            metal = qty * line.metal_content_pct / 100.0
            line.actual_qty_kg = qty
            line.actual_metal_kg = metal
            line.efficiency_pct = line.contained_kg and metal / line.contained_kg * 100.0 or 0.0
