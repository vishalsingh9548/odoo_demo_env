# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    """Shows the lead's DISCOM / dealer on the project, so later stages
    (document pack, subsidy, net metering) can reuse them."""
    _inherit = 'project.project'

    discom_id = fields.Many2one(
        'epc.discom', string='DISCOM', related='lead_id.discom_id', readonly=False,
        help="The electricity board of this customer, taken from the lead.",
    )
    consumer_number = fields.Char(
        string='Consumer Number', related='lead_id.consumer_number', readonly=False,
        help="The customer's consumer number, taken from the lead.",
    )
    dealer_id = fields.Many2one(
        'epc.dealer', string='Dealer', related='lead_id.dealer_id', readonly=False,
        help="The dealer who brought this project, taken from the lead.",
    )
    sub_dealer_id = fields.Many2one(
        'epc.dealer', string='Sub-dealer', related='lead_id.sub_dealer_id', readonly=False,
        help="The sub-dealer who brought this project, taken from the lead.",
    )
