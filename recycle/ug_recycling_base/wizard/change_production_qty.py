from odoo import api, fields, models


class ChangeProductionQty(models.TransientModel):
    _inherit = 'change.production.qty'

    ug_is_recycling = fields.Boolean(related='mo_id.ug_is_recycling')
    ug_input_qty = fields.Float('Input Weight (kg)', digits='Product Unit of Measure',
        help="Primary input weight to process; the quantity to produce is computed from the BoM ratio.")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'ug_input_qty' in fields and res.get('mo_id'):
            production = self.env['mrp.production'].browse(res['mo_id'])
            if production.ug_is_recycling:
                res['ug_input_qty'] = production._ug_input_from_product_qty(
                    res.get('product_qty') or production.product_qty)
        return res

    @api.onchange('ug_input_qty')
    def _onchange_ug_input_qty(self):
        if self.mo_id.ug_is_recycling and self.ug_input_qty:
            self.product_qty = self.mo_id._ug_product_qty_from_input(self.ug_input_qty)
