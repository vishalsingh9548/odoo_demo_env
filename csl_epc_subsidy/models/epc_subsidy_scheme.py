# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcSubsidyScheme(models.Model):
    """A government subsidy scheme. All amounts are typed in by the admin here,
    nothing is hard-coded, because scheme rates change."""
    _name = 'epc.subsidy.scheme'
    _description = 'Solar Subsidy Scheme'
    _order = 'name'

    name = fields.Char(string='Scheme', required=True, help="Name of the scheme, e.g. PM Surya Ghar.")
    authority = fields.Char(string='Authority', help="Who pays the subsidy (ministry, state agency).")
    segment = fields.Selection(
        [('all', 'All customers'), ('residential', 'Residential'),
         ('commercial', 'Commercial'), ('industrial', 'Industrial')],
        string='Applies To', default='residential', required=True,
        help="Which type of customer can get this subsidy.",
    )
    max_capacity_kw = fields.Float(
        string='Maximum System Size (kW)',
        help="Systems larger than this are not eligible. Leave 0 for no limit.",
    )
    amount_type = fields.Selection(
        [('percent', 'Percentage of project cost'), ('flat', 'Flat amount'), ('per_kw', 'Amount per kW')],
        string='Amount Type', required=True, default='per_kw',
        help="How the subsidy is worked out.",
    )
    amount = fields.Float(
        string='Amount / Percentage', help="The percentage, flat amount or per-kW amount, depending on the type.",
    )
    max_amount = fields.Float(
        string='Maximum Subsidy', help="The subsidy is never more than this. Leave 0 for no cap.",
    )
    valid_from = fields.Date(string='Valid From', help="First day the scheme can be used.")
    valid_to = fields.Date(string='Valid Until', help="Last day the scheme can be used.")
    document_template_ids = fields.Many2many(
        'epc.document.template', string='Papers Needed',
        help="Papers this scheme asks for. They are added to the project when an application is made.",
    )
    notes = fields.Text(string='Notes', help="Rules or reminders about this scheme.")
    active = fields.Boolean(default=True, help="Untick to stop using this scheme.")

    # True when this scheme can be used for the given customer type, size and date
    def _is_eligible(self, segment, capacity_kw, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        if self.segment != 'all' and self.segment != segment:
            return False
        if self.max_capacity_kw and capacity_kw > self.max_capacity_kw:
            return False
        if self.valid_from and on_date < self.valid_from:
            return False
        if self.valid_to and on_date > self.valid_to:
            return False
        return True

    # Subsidy for a system of this size / cost under this scheme
    def _compute_subsidy(self, capacity_kw, project_cost=0.0):
        self.ensure_one()
        if self.amount_type == 'percent':
            value = project_cost * self.amount / 100.0
        elif self.amount_type == 'flat':
            value = self.amount
        else:
            value = capacity_kw * self.amount
        return min(value, self.max_amount) if self.max_amount else value

    # The eligible scheme that pays the most (empty when none fits)
    @api.model
    def _best_scheme(self, segment, capacity_kw, project_cost=0.0):
        if not segment or capacity_kw <= 0:
            return self.browse()
        eligible = self.search([]).filtered(lambda s: s._is_eligible(segment, capacity_kw))
        if not eligible:
            return eligible
        return max(eligible, key=lambda s: s._compute_subsidy(capacity_kw, project_cost))
