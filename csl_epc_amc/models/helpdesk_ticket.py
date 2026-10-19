# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskTicket(models.Model):
    """Links a Helpdesk complaint ticket back to the AMC contract it was raised
    under, so the O&M team can see a contract's full complaint history and the
    contract's warranty/SLA terms while working the ticket. From here onward,
    the standard 'helpdesk_fsm' app (already a dependency) takes the ticket to
    a Field Service task, an engineer visit, and parts used — nothing custom
    needed for that part of the flow.
    """
    _inherit = 'helpdesk.ticket'

    amc_contract_id = fields.Many2one(
        'epc.amc.contract', string='AMC Contract',
        help="The maintenance contract this complaint was raised under, if any.",
    )
