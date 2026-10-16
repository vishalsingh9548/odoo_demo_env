from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ug_metal_element_id = fields.Many2one('ug.assay.element', string='Metal Element',
        help="Element carried by this recovered material, e.g. Nickel for nickel sulphate.")
    ug_metal_content_pct = fields.Float('Metal Content (%)', digits=(6, 3),
        help="Mass fraction of the metal in the product, e.g. 22.3 for NiSO4·6H2O.")

    @api.constrains('ug_metal_content_pct')
    def _check_ug_metal_content_pct(self):
        for template in self:
            if not 0 <= template.ug_metal_content_pct <= 100:
                raise ValidationError(_("The metal content must be between 0 and 100%."))
