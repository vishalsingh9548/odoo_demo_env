# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    epc_subsidy_scheme_id = fields.Many2one(
        'epc.subsidy.scheme', string='Subsidy Scheme', compute='_compute_epc_subsidy',
        help="Best matching subsidy scheme for this order.",
    )
    epc_expected_subsidy = fields.Monetary(
        string='Expected Subsidy', compute='_compute_epc_subsidy', currency_field='currency_id',
        help="Estimated subsidy for this order. It does not change the order total.",
    )
    epc_customer_pays = fields.Monetary(
        string='Customer Pays After Subsidy', compute='_compute_epc_subsidy', currency_field='currency_id',
        help="Order total minus the expected subsidy (shown for information only).",
    )

    @api.depends('opportunity_id.customer_segment', 'opportunity_id.proposed_capacity_kw', 'amount_untaxed', 'amount_total')
    def _compute_epc_subsidy(self):
        schemes = self.env['epc.subsidy.scheme'].sudo()
        for order in self:
            lead = order.opportunity_id
            capacity = lead.proposed_capacity_kw
            scheme = schemes._best_scheme(lead.customer_segment, capacity, order.amount_untaxed) if lead else schemes
            subsidy = scheme._compute_subsidy(capacity, order.amount_untaxed) if scheme else 0.0
            order.epc_subsidy_scheme_id = scheme
            order.epc_expected_subsidy = subsidy
            order.epc_customer_pays = max(order.amount_total - subsidy, 0.0)

    # After the order is confirmed, open a Draft subsidy application when a scheme
    # fits. A problem here never stops the order from confirming.
    def action_confirm(self):
        result = super().action_confirm()
        for order in self.filtered('epc_project_id'):
            project = order.epc_project_id
            scheme = order.epc_subsidy_scheme_id
            if not scheme or project.subsidy_ids:
                continue
            try:
                with self.env.cr.savepoint():
                    self.env['epc.subsidy.application'].sudo().create({
                        'project_id': project.id, 'scheme_id': scheme.id,
                        'claimed_amount': order.epc_expected_subsidy,
                    })
            except Exception:  # pylint: disable=broad-except
                _logger.exception("Could not create the subsidy application for %s", order.name)
        return result
