from odoo import fields, models


class UgAssayTemplate(models.Model):
    _name = 'ug.assay.template'
    _description = 'Assay Template'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Battery Chemistry')
    element_ids = fields.Many2many('ug.assay.element', string='Elements',
        help="Elements measured by the lab; assay lines are created in element sequence.")
    company_id = fields.Many2one('res.company', string='Company', index=True)
    active = fields.Boolean(default=True)
