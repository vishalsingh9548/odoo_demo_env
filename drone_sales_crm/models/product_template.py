from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_stringing_km = fields.Boolean(
        string="Billed per Certified km",
        help="The delivered quantity of this product on a sales order is driven only by "
             "confirmed client certifications. It cannot be edited by hand.",
    )

    @api.constrains("is_stringing_km", "type", "invoice_policy")
    def _check_stringing_km_setup(self):
        for product in self.filtered("is_stringing_km"):
            if product.type != "service" or product.invoice_policy != "delivery":
                raise ValidationError(_(
                    "'%s' is billed per certified km, so it must be a Service invoiced on "
                    "delivered quantities.", product.display_name))
