# -*- coding: utf-8 -*-
from odoo import fields, models


class EpcDiscom(models.Model):
    """Master list of electricity boards (DISCOMs) the company deals with."""
    _name = 'epc.discom'
    _description = 'Electricity Distribution Company (DISCOM)'
    _order = 'name'

    name = fields.Char(
        string='DISCOM Name', required=True,
        help="Name of the electricity distribution company, e.g. MSEDCL or BSES.",
    )
    state_id = fields.Many2one(
        'res.country.state', string='State',
        help="The state this electricity board serves.",
    )
    portal_url = fields.Char(
        string='Portal Link',
        help="Web address of the board's net-metering / rooftop-solar portal.",
    )
    active = fields.Boolean(
        default=True,
        help="Untick to hide this board from new leads without deleting it.",
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This DISCOM already exists.'),
    ]
