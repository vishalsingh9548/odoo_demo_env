from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AdvmfgSerialPrefix(models.Model):
    """The text put in front of every serial number of a company (one record per company)."""
    _name = 'advmfg.serial.prefix'
    _description = 'Serial Number Prefix'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'prefix'

    company_id = fields.Many2one('res.company', string='Company', required=True, tracking=True,
                                 default=lambda self: self.env.company)
    prefix = fields.Char(string='SN Prefix', required=True, tracking=True)

    _sql_constraints = [
        ('company_uniq', 'unique(company_id)', 'A configuration already exists for this company. Only one record per company is allowed.'),
    ]
