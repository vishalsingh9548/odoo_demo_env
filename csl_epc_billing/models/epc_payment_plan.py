# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

TRIGGERS = [
    ('order_confirmed', 'Order confirmed'),
    ('material_delivered', 'All material delivered'),
    ('installation_done', 'Installation complete'),
    ('commissioning_done', 'Commissioning approved'),
    ('handover_done', 'Handover approved'),
    ('manual', 'Manually'),
]


class EpcPaymentPlan(models.Model):
    """A reusable payment plan, e.g. 30% advance, 40% on delivery, 20% on
    commissioning, 10% retention."""
    _name = 'epc.payment.plan'
    _description = 'Solar Payment Plan'
    _order = 'name'

    name = fields.Char(string='Plan', required=True, help="Name of the plan, e.g. 30-40-20-10.")
    line_ids = fields.One2many('epc.payment.plan.line', 'plan_id', string='Stages', copy=True,
                               help="The payment stages of this plan.")
    total_percent = fields.Float(string='Total (%)', compute='_compute_total_percent', help="Must add up to 100.")
    active = fields.Boolean(default=True, help="Untick to stop using this plan.")

    @api.depends('line_ids.percentage')
    def _compute_total_percent(self):
        for plan in self:
            plan.total_percent = sum(plan.line_ids.mapped('percentage'))

    @api.constrains('line_ids')
    def _check_total(self):
        for plan in self:
            if plan.line_ids and abs(sum(plan.line_ids.mapped('percentage')) - 100.0) > 0.001:
                raise ValidationError("The stages of '%s' must add up to 100%%." % plan.name)


class EpcPaymentPlanLine(models.Model):
    _name = 'epc.payment.plan.line'
    _description = 'Solar Payment Plan Stage'
    _order = 'sequence, id'

    plan_id = fields.Many2one('epc.payment.plan', string='Plan', required=True, ondelete='cascade',
                              help="The plan this stage belongs to.")
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Stage', required=True, help="Name of the payment, e.g. Advance, Retention.")
    percentage = fields.Float(string='Percentage', required=True, help="Share of the order total for this stage.")
    trigger = fields.Selection(TRIGGERS, string='Invoice When', required=True, default='manual',
                               help="The project stage that raises this invoice.")
    days_after = fields.Integer(string='Days After', help="Wait this many days after the stage before invoicing (e.g. 90 for a retention release).")
