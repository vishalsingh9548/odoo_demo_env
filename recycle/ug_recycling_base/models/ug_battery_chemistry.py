from odoo import fields, models


class UgBatteryChemistry(models.Model):
    _name = 'ug.battery.chemistry'
    _description = 'Battery Chemistry'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)

    _sql_constraints = [(
        'code_company_uniq', 'unique(code, company_id)',
        'The chemistry code must be unique per company.',
    )]
