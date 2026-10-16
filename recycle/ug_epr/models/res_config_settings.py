from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ug_epr_basis = fields.Selection(related='company_id.ug_epr_basis', readonly=False)
    ug_epr_product_id = fields.Many2one(related='company_id.ug_epr_product_id', readonly=False)
