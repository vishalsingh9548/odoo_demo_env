from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    battery_chemistry_id = fields.Many2one(related='product_id.battery_chemistry_id', store=True, index=True)
    ug_material_type = fields.Selection(related='product_id.ug_material_type', store=True, index=True)
