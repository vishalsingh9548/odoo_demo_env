from odoo import fields, models

EPR_BASIS = [
    ('input_battery_weight', 'Battery weight processed (dismantle input)'),
    ('recovered_material_weight', 'Recovered material weight (recover output)'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    ug_epr_basis = fields.Selection(EPR_BASIS, string='EPR Basis', default='input_battery_weight', required=True,
        help="Quantity on which EPR certificates are generated. To be confirmed with CPCB rules / the client.")
    ug_epr_product_id = fields.Many2one('product.product', string='EPR Service Product',
        domain="[('type', '=', 'service')]", help="Product used on quotations and invoices of EPR certificates.")

    def _ug_get_epr_product(self):
        self.ensure_one()
        return self.ug_epr_product_id or self.env.ref('ug_epr.product_epr_certificate', raise_if_not_found=False)
