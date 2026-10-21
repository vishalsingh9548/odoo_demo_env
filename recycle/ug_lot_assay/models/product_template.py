from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ug_requires_assay = fields.Boolean('Requires Assay',
        help="Lots of this product need an approved lab assay (composition or purity). "
             "A draft assay is created automatically when a manufacturing order produces a lot.")
    ug_assay_template_id = fields.Many2one('ug.assay.template', string='Assay Template')
