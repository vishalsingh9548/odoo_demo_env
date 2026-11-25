from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    drone_quote_terms = fields.Html(
        string="Drone Terms",
        translate=True,
        help="Printed in a 'Drone terms' section at the end of the quotation / order PDF.",
    )
