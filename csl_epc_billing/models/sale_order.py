# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_plan_id = fields.Many2one('epc.payment.plan', string='Payment Plan',
                                      help="Pick a plan, then 'Load Stages from Plan'. Stages are also loaded when the order is confirmed.")
    milestone_ids = fields.One2many('epc.order.milestone', 'order_id', string='Payment Stages', copy=False,
                                    help="The stage-wise payments of this order.")
    milestone_total_percent = fields.Float(string='Stages Total (%)', compute='_compute_milestone_totals',
                                           help="Must add up to 100.")
    milestone_billed_amount = fields.Monetary(string='Billed by Stages', compute='_compute_milestone_totals',
                                              currency_field='currency_id', help="Amount of stages already invoiced.")

    @api.depends('milestone_ids.percentage', 'milestone_ids.state', 'milestone_ids.amount')
    def _compute_milestone_totals(self):
        for order in self:
            order.milestone_total_percent = sum(order.milestone_ids.mapped('percentage'))
            order.milestone_billed_amount = sum(order.milestone_ids.filtered(lambda m: m.state == 'invoiced').mapped('amount'))

    # Copies the stages of the chosen plan onto the order
    def action_load_milestones(self):
        for order in self:
            if not order.payment_plan_id:
                raise UserError("Choose a Payment Plan first.")
            if order.milestone_ids.filtered(lambda m: m.state != 'pending'):
                raise UserError("Some stages are already invoiced, so the plan cannot be reloaded.")
            order.milestone_ids.unlink()
            self.env['epc.order.milestone'].create([{
                'order_id': order.id, 'sequence': line.sequence, 'name': line.name,
                'percentage': line.percentage, 'trigger': line.trigger, 'days_after': line.days_after,
            } for line in order.payment_plan_id.line_ids])

    # Confirms as usual. Only orders that use a payment plan are touched: the
    # stages are checked / loaded, and 'order confirmed' stages are invoiced.
    def action_confirm(self):
        for order in self.filtered('payment_plan_id'):
            if not order.milestone_ids:
                order.sudo().action_load_milestones()
            if abs(sum(order.sudo().milestone_ids.mapped('percentage')) - 100.0) > 0.001:
                raise UserError("The payment stages of %s must add up to 100%% before it is confirmed." % order.name)
        result = super().action_confirm()
        for order in self.filtered('payment_plan_id'):
            order._epc_trigger_milestones('order_confirmed')
        return result

    # A project stage was reached: wake up the matching payment stages
    def _epc_trigger_milestones(self, trigger):
        for order in self:
            stages = order.sudo().milestone_ids.filtered(lambda m: m.trigger == trigger)
            if stages:
                try:
                    with self.env.cr.savepoint():
                        stages._epc_stage_reached()
                except Exception:  # pylint: disable=broad-except
                    _logger.exception("Milestone trigger %s failed for %s", trigger, order.name)
