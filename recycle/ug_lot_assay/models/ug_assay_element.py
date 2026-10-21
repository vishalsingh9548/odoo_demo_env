from odoo import api, fields, models


class UgAssayElement(models.Model):
    _name = 'ug.assay.element'
    _description = 'Assay Element'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Chemical symbol, e.g. Ni")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'The element code must be unique.')]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for element in self:
            element.display_name = f"{element.code} – {element.name}" if element.code else element.name
