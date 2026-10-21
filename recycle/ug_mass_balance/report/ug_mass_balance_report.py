from odoo import fields, models, tools
from odoo.tools import SQL

from odoo.addons.ug_recycling_base.models.mrp_bom import STAGES
from odoo.addons.ug_recycling_base.models.product_template import MATERIAL_TYPES


class UgMassBalanceReport(models.Model):
    _name = 'ug.mass.balance.report'
    _description = 'Recycling Mass Balance'
    _auto = False
    _order = 'date_finished desc'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', readonly=True)
    date_finished = fields.Datetime('Date', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    stage = fields.Selection(STAGES, readonly=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Chemistry', readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='BoM', readonly=True)
    product_id = fields.Many2one('product.product', string='Main Product', readonly=True)
    input_kg = fields.Float('Input (kg)', readonly=True)
    output_kg = fields.Float('Output (kg)', readonly=True)
    loss_kg = fields.Float('Loss (kg)', readonly=True)
    loss_pct = fields.Float('Loss (%)', readonly=True, aggregator='avg')
    loss_exceeded = fields.Boolean(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT p.id AS id,
                       p.id AS production_id,
                       p.date_finished,
                       p.company_id,
                       p.ug_stage AS stage,
                       p.battery_chemistry_id,
                       p.bom_id,
                       p.product_id,
                       p.ug_input_weight_kg AS input_kg,
                       p.ug_output_weight_kg AS output_kg,
                       p.ug_loss_kg AS loss_kg,
                       p.ug_loss_pct AS loss_pct,
                       p.ug_loss_exceeded AS loss_exceeded
                  FROM mrp_production p
                 WHERE p.state = 'done' AND p.ug_is_recycling
            )""", SQL.identifier(self._table)))


class UgElementBalanceReport(models.Model):
    _name = 'ug.element.balance.report'
    _description = 'Element Recovery'
    _auto = False
    _order = 'date_finished desc'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', readonly=True)
    date_finished = fields.Datetime('Date', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    element_id = fields.Many2one('ug.assay.element', string='Element', readonly=True)
    output_product_id = fields.Many2one('product.product', string='Output Product', readonly=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Chemistry', readonly=True)
    contained_kg = fields.Float('Contained Metal (kg)', readonly=True)
    expected_qty_kg = fields.Float('Expected Output (kg)', readonly=True)
    actual_qty_kg = fields.Float('Actual Output (kg)', readonly=True)
    actual_metal_kg = fields.Float('Actual Metal (kg)', readonly=True)
    efficiency_pct = fields.Float('Efficiency (%)', readonly=True, aggregator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT r.id AS id,
                       r.production_id,
                       p.date_finished,
                       p.company_id,
                       r.element_id,
                       r.output_product_id,
                       p.battery_chemistry_id,
                       r.contained_kg,
                       r.expected_qty_kg,
                       r.actual_qty_kg,
                       r.actual_metal_kg,
                       r.efficiency_pct
                  FROM ug_production_recovery_line r
                  JOIN mrp_production p ON p.id = r.production_id
                 WHERE p.state = 'done'
            )""", SQL.identifier(self._table)))


class UgMaterialOutputReport(models.Model):
    _name = 'ug.material.output.report'
    _description = 'Recycling Material Output & Cost'
    _auto = False
    _order = 'date_finished desc'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', readonly=True)
    date_finished = fields.Datetime('Date', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    stage = fields.Selection(STAGES, readonly=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Chemistry', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    ug_material_type = fields.Selection(MATERIAL_TYPES, string='Material Type', readonly=True)
    is_byproduct = fields.Boolean('By-product', readonly=True)
    qty_kg = fields.Float('Quantity (kg)', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    value = fields.Monetary(readonly=True)
    cost_per_kg = fields.Monetary('Cost per kg', readonly=True, aggregator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        kg = self.env.ref('uom.product_uom_kgm')
        # quantities in kg: only units sharing the kg reference unit are converted, others count 0
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH kg AS (
                    SELECT factor, category_id FROM uom_uom WHERE id = %(kg_id)s
                ), moves AS (
                    SELECT m.id,
                           m.production_id,
                           p.date_finished,
                           p.company_id,
                           p.ug_stage AS stage,
                           p.battery_chemistry_id,
                           m.product_id,
                           pt.ug_material_type,
                           m.byproduct_id IS NOT NULL AS is_byproduct,
                           CASE WHEN u.category_id = kg.category_id AND u.factor > 0
                                THEN m.quantity * kg.factor / u.factor ELSE 0 END AS qty_kg,
                           c.currency_id,
                           COALESCE((SELECT SUM(svl.value) FROM stock_valuation_layer svl
                                      WHERE svl.stock_move_id = m.id), 0) AS value
                      FROM stock_move m
                      JOIN mrp_production p ON p.id = m.production_id
                      JOIN product_product pp ON pp.id = m.product_id
                      JOIN product_template pt ON pt.id = pp.product_tmpl_id
                      JOIN uom_uom u ON u.id = m.product_uom
                      JOIN res_company c ON c.id = p.company_id
                      CROSS JOIN kg
                     WHERE m.state = 'done' AND p.state = 'done' AND p.ug_is_recycling
                )
                SELECT moves.*,
                       CASE WHEN qty_kg <> 0 THEN value / qty_kg ELSE 0 END AS cost_per_kg
                  FROM moves
            )""", table=SQL.identifier(self._table), kg_id=kg.id))
