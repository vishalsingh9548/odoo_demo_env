# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Suggests the best subsidy scheme on the lead from customer type and size."""
    _inherit = 'crm.lead'

    suggested_subsidy_scheme_id = fields.Many2one(
        'epc.subsidy.scheme', string='Suggested Subsidy Scheme', compute='_compute_subsidy_suggestion',
        help="The best matching scheme for this customer type and system size.",
    )
    expected_subsidy_amount = fields.Float(
        string='Expected Subsidy', compute='_compute_subsidy_suggestion',
        help="Estimated subsidy under the suggested scheme. Percentage schemes need a price, so "
             "they use the lead's latest quotation (not cancelled); with no quotation yet they show 0.",
    )

    @api.depends('customer_segment', 'proposed_capacity_kw', 'order_ids.state', 'order_ids.amount_untaxed')
    def _compute_subsidy_suggestion(self):
        schemes = self.env['epc.subsidy.scheme'].sudo()
        for lead in self:
            # price of the latest quotation / order of this lead (read with sudo so users
            # without sales access can still open the lead); 0 when there is none yet
            orders = lead.sudo().order_ids.filtered(lambda o: o.state != 'cancel').sorted('id')
            cost = orders[-1].amount_untaxed if orders else 0.0
            scheme = schemes._best_scheme(lead.customer_segment, lead.proposed_capacity_kw, cost)
            lead.suggested_subsidy_scheme_id = scheme
            lead.expected_subsidy_amount = scheme._compute_subsidy(lead.proposed_capacity_kw, cost) if scheme else 0.0
