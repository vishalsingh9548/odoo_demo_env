# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from .epc_payment_plan import TRIGGERS

_logger = logging.getLogger(__name__)


class EpcOrderMilestone(models.Model):
    """One payment stage of one Sales Order. When its project stage is reached a
    DRAFT down-payment invoice is raised for it (never posted automatically)."""
    _name = 'epc.order.milestone'
    _description = 'Solar Order Payment Milestone'
    _order = 'order_id, sequence, id'

    order_id = fields.Many2one('sale.order', string='Order', required=True, ondelete='cascade', index=True,
                               help="The Sales Order this stage belongs to.")
    partner_id = fields.Many2one('res.partner', string='Customer', related='order_id.partner_id', store=True,
                                 help="The customer.")
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id', store=True,
                                  help="Currency of the order.")
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Stage', required=True, help="Name of the payment, e.g. Advance.")
    percentage = fields.Float(string='Percentage', required=True, help="Share of the order total.")
    amount = fields.Monetary(string='Amount', compute='_compute_amount', currency_field='currency_id',
                             help="Order total x percentage.")
    trigger = fields.Selection(TRIGGERS, string='Invoice When', required=True, default='manual',
                               help="The project stage that raises this invoice.")
    days_after = fields.Integer(string='Days After', help="Days to wait after the stage before invoicing.")
    due_date = fields.Date(string='Invoice On', copy=False, help="Set when the stage is reached and a delay applies.")
    state = fields.Selection(
        [('pending', 'Waiting for Stage'), ('scheduled', 'Scheduled'), ('invoiced', 'Invoiced')],
        string='Status', default='pending', required=True, copy=False,
        help="Waiting: stage not reached. Scheduled: stage reached, invoice due on the date. Invoiced: draft invoice raised.",
    )
    invoice_id = fields.Many2one('account.move', string='Invoice', copy=False, readonly=True,
                                 help="The invoice raised for this stage.")
    payment_state = fields.Selection(related='invoice_id.payment_state', string='Payment Status',
                                     help="Payment status of the invoice.")

    @api.depends('percentage', 'order_id.amount_total')
    def _compute_amount(self):
        for ms in self:
            ms.amount = ms.order_id.amount_total * ms.percentage / 100.0

    # Raises the draft invoice. In automatic use a failure is logged on the order
    # and never blocks the stage itself (delivery, approval...).
    def _epc_raise_invoice(self, raise_error=False):
        for ms in self.filtered(lambda m: m.state != 'invoiced'):
            order = ms.order_id
            try:
                with self.env.cr.savepoint():
                    wizard = self.env['sale.advance.payment.inv'].sudo().with_context(
                        active_model='sale.order', active_ids=order.ids, active_id=order.id,
                    ).create({'advance_payment_method': 'percentage', 'amount': ms.percentage})
                    invoice = wizard._create_invoices(order)
                    ms.sudo().write({'state': 'invoiced', 'invoice_id': invoice.id})
                    order.sudo().message_post(body="Draft invoice %s raised for stage '%s' (%s%%)." % (
                        invoice.display_name, ms.name, ms.percentage))
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Milestone invoice failed for %s / %s", order.name, ms.name)
                if raise_error:
                    raise UserError("Could not raise the invoice: %s" % exc) from exc
                order.sudo().message_post(
                    body="Could not raise the invoice for stage '%s' automatically. Use the button on the stage. (%s)" % (ms.name, exc))

    # The project reached this stage: invoice now, or schedule it after the delay
    def _epc_stage_reached(self):
        today = fields.Date.context_today(self)
        for ms in self.filtered(lambda m: m.state == 'pending'):
            if ms.days_after:
                ms.sudo().write({'state': 'scheduled', 'due_date': today + fields.date_utils.relativedelta(days=ms.days_after)})
            else:
                ms._epc_raise_invoice()

    # Button: raise the invoice by hand (also for "Manually" stages)
    def action_raise_invoice(self):
        self._epc_raise_invoice(raise_error=True)

    # Daily: raise invoices of scheduled stages that are due
    @api.model
    def _cron_raise_due_invoices(self):
        due = self.search([('state', '=', 'scheduled'), ('due_date', '<=', fields.Date.context_today(self))])
        due._epc_raise_invoice()
