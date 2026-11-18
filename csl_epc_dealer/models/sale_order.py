# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    """Shows the lead's DISCOM / dealer on the order (read only, taken from the lead)."""
    _inherit = 'sale.order'

    epc_discom_id = fields.Many2one(
        'epc.discom', string='DISCOM', related='opportunity_id.discom_id',
        help="The electricity board of this customer, taken from the lead.",
    )
    epc_consumer_number = fields.Char(
        string='Consumer Number', related='opportunity_id.consumer_number',
        help="The customer's consumer number, taken from the lead.",
    )
    epc_dealer_id = fields.Many2one(
        'epc.dealer', string='Dealer', related='opportunity_id.dealer_id',
        help="The dealer who brought this order, taken from the lead.",
    )
    epc_sub_dealer_id = fields.Many2one(
        'epc.dealer', string='Sub-dealer', related='opportunity_id.sub_dealer_id',
        help="The sub-dealer who brought this order, taken from the lead.",
    )
