from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ug_block_unassayed_lots = fields.Boolean('Block Unassayed Lots',
        help="Prevent consuming in a recover-stage MO, or delivering to a customer, a lot whose assay is pending.")
