from odoo import fields, models

MATERIAL_TYPES = [
    ('scrap_battery', 'Scrap Battery'),
    ('intermediate', 'Intermediate'),
    ('recovered_material', 'Recovered Material'),
    ('scrap_byproduct', 'Scrap By-product'),
    ('chemical', 'Chemical'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Battery Chemistry', index=True)
    ug_material_type = fields.Selection(MATERIAL_TYPES, string='Material Type', index=True,
        help="Recycling classification: scrap batteries are the raw input, intermediates are cells "
             "and black mass, recovered materials are sold metal salts, scrap by-products are "
             "casing/plastic/foils and chemicals are process consumables.")
