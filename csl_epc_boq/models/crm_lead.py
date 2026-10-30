# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Adds the BOQ link and count to the CRM Lead/Opportunity."""
    _inherit = 'crm.lead'

    boq_count = fields.Integer(
        groups='csl_epc_core.group_epc_user',
        string='BOQ Count', compute='_compute_boq_count',
        help="How many Bill of Quantities (BOQ) records exist for this lead.",
    )

    # Counts the BOQ records linked to this lead, for the smart button on the form
    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for lead in self:
            lead.boq_count = len(lead.boq_ids)

    boq_ids = fields.One2many(
        'epc.boq', 'lead_id', groups='csl_epc_core.group_epc_user', string='BOQs',
        help="All Bill of Quantities (costing sheets) prepared for this lead.",
    )
