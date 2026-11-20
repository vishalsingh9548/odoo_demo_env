# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcSubsidyApplication(models.Model):
    """One subsidy application for one project: what was claimed, approved and
    finally paid out."""
    _name = 'epc.subsidy.application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Subsidy Application'
    _order = 'id desc'

    name = fields.Char(string='Reference', default='New', copy=False, readonly=True,
                       help="Auto-generated number, e.g. SUB/2026/00001.")
    project_id = fields.Many2one('project.project', string='Project', required=True, tracking=True,
                                 help="The project this subsidy is for.")
    partner_id = fields.Many2one('res.partner', string='Customer', related='project_id.partner_id', store=True,
                                 help="The customer receiving the subsidy.")
    scheme_id = fields.Many2one('epc.subsidy.scheme', string='Scheme', required=True, tracking=True,
                                help="The subsidy scheme applied under.")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id,
                                  help="Currency of the amounts.")
    capacity_kw = fields.Float(string='System Capacity (kW)', related='project_id.capacity_kw',
                               help="System size taken from the project.")
    state = fields.Selection(
        [('draft', 'Draft'), ('docs_ready', 'Documents Ready'), ('applied', 'Applied'),
         ('approved', 'Approved'), ('disbursed', 'Disbursed'), ('rejected', 'Rejected')],
        string='Status', default='draft', required=True, tracking=True, copy=False,
        help="Where the application stands.",
    )
    expected_amount = fields.Monetary(string='Expected Subsidy', compute='_compute_expected', currency_field='currency_id',
                                      help="What the scheme rules say this project should get.")
    claimed_amount = fields.Monetary(string='Claimed', currency_field='currency_id', tracking=True,
                                     help="Amount we asked for.")
    approved_amount = fields.Monetary(string='Approved', currency_field='currency_id', tracking=True,
                                      help="Amount the authority approved.")
    disbursed_amount = fields.Monetary(string='Disbursed', currency_field='currency_id', tracking=True,
                                       help="Amount actually paid out.")
    portal_number = fields.Char(string='Portal Application No.', tracking=True,
                                help="Application number given by the government portal.")
    applied_date = fields.Date(string='Applied On', copy=False, help="Date the application was filed.")
    approved_date = fields.Date(string='Approved On', copy=False, help="Date the authority approved it.")
    disbursed_date = fields.Date(string='Disbursed On', copy=False, help="Date the money was received.")
    days_pending = fields.Integer(string='Days Pending', compute='_compute_days_pending',
                                  help="Days since the application was filed while still waiting for money.")
    remarks = fields.Text(string='Remarks', help="Notes, or the reason for a rejection.")

    @api.depends('scheme_id', 'capacity_kw', 'project_id.epc_sale_order_id.amount_untaxed')
    def _compute_expected(self):
        for app in self:
            cost = app.project_id.epc_sale_order_id.amount_untaxed
            app.expected_amount = app.scheme_id._compute_subsidy(app.capacity_kw, cost) if app.scheme_id else 0.0

    @api.depends('applied_date', 'state')
    def _compute_days_pending(self):
        today = fields.Date.context_today(self)
        for app in self:
            app.days_pending = (today - app.applied_date).days if app.applied_date and app.state in ('applied', 'approved') else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.subsidy.application') or 'New'
        records = super().create(vals_list)
        for app in records:
            if not app.claimed_amount:
                app.claimed_amount = app.expected_amount
            # Add the papers this scheme asks for to the project
            if app.scheme_id.document_template_ids:
                app.project_id.sudo()._epc_create_documents(app.scheme_id.document_template_ids)
        return records

    # The papers this scheme needs, as they exist on the project
    def _scheme_documents(self):
        self.ensure_one()
        return self.project_id.document_ids.filtered(
            lambda d: d.template_id in self.scheme_id.document_template_ids)

    def action_docs_ready(self):
        for app in self:
            missing = app._scheme_documents().filtered(lambda d: d.state == 'pending')
            if missing:
                raise UserError("These papers are still pending: %s" % ", ".join(missing.mapped('name')))
        self.write({'state': 'docs_ready'})

    def action_apply(self):
        self.write({'state': 'applied', 'applied_date': fields.Date.context_today(self)})

    def action_approve(self):
        for app in self:
            if not app.approved_amount:
                raise UserError("Enter the Approved amount first.")
            if not app.portal_number:
                raise UserError("Enter the Portal Application No. first.")
        self.write({'state': 'approved', 'approved_date': fields.Date.context_today(self)})

    def action_disburse(self):
        for app in self:
            if not app.disbursed_amount:
                raise UserError("Enter the Disbursed amount first.")
        self.write({'state': 'disbursed', 'disbursed_date': fields.Date.context_today(self)})

    def action_reject(self):
        for app in self:
            if not app.remarks:
                raise UserError("Write the reason in Remarks before rejecting.")
        self.write({'state': 'rejected'})

    def action_reset(self):
        self.write({'state': 'draft'})
