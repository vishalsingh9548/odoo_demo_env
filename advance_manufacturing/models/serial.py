from odoo import fields, models


class AdvmfgSerial(models.Model):
    """One reserved serial number waiting in the 'serial pool' of a manufacturing order.

    Pool = a roll of numbered stickers. 'Allocate' sticks them onto the units.
    """
    _name = 'advmfg.serial'
    _description = 'Serial Number Pool'
    _order = 'name'

    name = fields.Char(string='Serial Number', required=True, copy=False)
    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade')
    product_id = fields.Many2one(related='production_id.product_id', store=True)
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    state = fields.Selection(
        [('available', 'Available'), ('allocated', 'Allocated')], default='available', required=True)

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)', 'This serial number already exists!'),
    ]
