from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    drone_quote_terms = fields.Html(
        related="company_id.drone_quote_terms", readonly=False
    )
