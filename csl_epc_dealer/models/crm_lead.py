# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Adds electricity-board (DISCOM) details and the dealer to the lead so
    they are typed once and reused on the order, project and government forms."""
    _inherit = 'crm.lead'

    discom_id = fields.Many2one(
        'epc.discom', string='DISCOM',
        help="The electricity board that supplies this customer.",
    )
    consumer_number = fields.Char(
        string='Consumer Number',
        help="The customer's consumer / account number on their electricity bill. "
             "Needed on subsidy and net-metering forms.",
    )
    connection_type = fields.Selection(
        [('residential', 'Residential'), ('commercial', 'Commercial'), ('industrial', 'Industrial'),
         ('agricultural', 'Agricultural')],
        string='Connection Type',
        help="The type of electricity connection, as written on the customer's bill.",
    )
    dealer_id = fields.Many2one(
        'epc.dealer', string='Dealer', domain="[('parent_id', '=', False)]",
        help="The dealer who brought this lead (leave empty for direct sales).",
    )
    sub_dealer_id = fields.Many2one(
        'epc.dealer', string='Sub-dealer', domain="[('parent_id', '=', dealer_id)]",
        help="The sub-dealer under the chosen dealer, if any.",
    )

    # Choosing another dealer clears a sub-dealer that belongs to the old one
    @api.onchange('dealer_id')
    def _onchange_dealer_id(self):
        if self.sub_dealer_id and self.sub_dealer_id.parent_id != self.dealer_id:
            self.sub_dealer_id = False
