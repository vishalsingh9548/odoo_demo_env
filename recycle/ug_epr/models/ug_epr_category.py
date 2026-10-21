from odoo import fields, models


class UgEprCategory(models.Model):
    _name = 'ug.epr.category'
    _description = 'EPR Battery Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'The EPR category code must be unique.')]
