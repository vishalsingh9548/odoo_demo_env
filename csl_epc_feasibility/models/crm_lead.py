# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Adds the Feasibility Study link and count to the CRM Lead/Opportunity."""
    _inherit = 'crm.lead'

    feasibility_count = fields.Integer(
        groups='csl_epc_core.group_epc_user',
        string='Feasibility Study Count', compute='_compute_feasibility_count',
        help="How many Technical Feasibility studies exist for this lead.",
    )
    # Counts the Feasibility Study records linked to this lead, for the smart button on the form
    @api.depends('feasibility_ids')
    def _compute_feasibility_count(self):
        for lead in self:
            lead.feasibility_count = len(lead.feasibility_ids)

    feasibility_ids = fields.One2many(
        'epc.feasibility', 'lead_id', groups='csl_epc_core.group_epc_user', string='Feasibility Studies',
        help="All Technical Feasibility studies done for this lead.",
    )
