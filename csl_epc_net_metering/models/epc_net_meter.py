# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

STUCK_SUMMARY = "Net-metering application is stuck"


class EpcNetMeter(models.Model):
    """Net-metering application with the electricity board for one project,
    followed from the application to the meter sync."""
    _name = 'epc.net.meter'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Net Metering Application'
    _order = 'id desc'

    name = fields.Char(string='Reference', default='New', copy=False, readonly=True,
                       help="Auto-generated number, e.g. NM/2026/00001.")
    project_id = fields.Many2one('project.project', string='Project', required=True, tracking=True,
                                 help="The project whose system is being connected.")
    partner_id = fields.Many2one('res.partner', string='Customer', related='project_id.partner_id', store=True,
                                 help="The customer.")
    discom_id = fields.Many2one('epc.discom', string='DISCOM', related='project_id.discom_id',
                                help="The electricity board, taken from the project.")
    consumer_number = fields.Char(string='Consumer Number', related='project_id.consumer_number',
                                  help="The customer's consumer number, taken from the project.")
    state = fields.Selection(
        [('draft', 'Draft'), ('applied', 'Applied'), ('discom_approved', 'DISCOM Approved'),
         ('inspection_done', 'Inspection Done'), ('meter_installed', 'Meter Installed'),
         ('synced', 'Synced'), ('rejected', 'Rejected')],
        string='Status', default='draft', required=True, tracking=True, copy=False,
        help="Where the application stands with the electricity board.",
    )
    application_number = fields.Char(string='Application No.', tracking=True, help="Number given by the DISCOM.")
    applied_date = fields.Date(string='Applied On', copy=False, help="Date the application was filed.")
    approval_date = fields.Date(string='DISCOM Approval', copy=False, help="Date the DISCOM approved.")
    inspection_date = fields.Date(string='Inspection Date', copy=False, help="Date the DISCOM inspected the system.")
    meter_installed_date = fields.Date(string='Meter Installed On', copy=False, help="Date the net meter was fitted.")
    meter_number = fields.Char(string='Meter Number', tracking=True, help="Serial number of the net meter.")
    sync_date = fields.Date(string='Synced On', copy=False, help="Date the system was synchronised with the grid.")
    last_state_date = fields.Date(string='Last Status Change', copy=False, readonly=True,
                                  help="When the status last changed; used to spot stuck applications.")
    stuck_days = fields.Integer(string='Days in This Status', compute='_compute_stuck_days',
                                help="Days since the status last changed (only while still open).")
    remarks = fields.Text(string='Remarks', help="Notes, or the reason for a rejection.")

    @api.depends('last_state_date', 'state')
    def _compute_stuck_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            open_ = rec.state not in ('draft', 'synced', 'rejected')
            rec.stuck_days = (today - rec.last_state_date).days if open_ and rec.last_state_date else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.net.meter') or 'New'
            vals.setdefault('last_state_date', fields.Date.context_today(self))
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals:
            vals = dict(vals, last_state_date=fields.Date.context_today(self))
        return super().write(vals)

    def _today(self):
        return fields.Date.context_today(self)

    def action_apply(self):
        self.write({'state': 'applied', 'applied_date': self._today()})

    def action_approve(self):
        self.write({'state': 'discom_approved', 'approval_date': self._today()})

    def action_inspection_done(self):
        self.write({'state': 'inspection_done', 'inspection_date': self._today()})

    def action_meter_installed(self):
        for rec in self:
            if not rec.meter_number:
                raise UserError("Enter the Meter Number first.")
        self.write({'state': 'meter_installed', 'meter_installed_date': self._today()})

    def action_sync(self):
        self.write({'state': 'synced', 'sync_date': self._today()})

    def action_reject(self):
        for rec in self:
            if not rec.remarks:
                raise UserError("Write the reason in Remarks before rejecting.")
        self.write({'state': 'rejected'})

    def action_reset(self):
        self.write({'state': 'draft'})

    # Daily reminder: an open application that did not move for N days gets a to-do
    # for its project's manager (switch off with "Turn Off Notifications")
    @api.model
    def _cron_remind_stuck(self):
        config = self.env['epc.config']
        if config.flag('disable_notifications'):
            return
        days = int(self.env['ir.config_parameter'].sudo().get_param('csl_epc.netmeter_stuck_days') or 15)
        limit = fields.Date.context_today(self) - timedelta(days=days)
        stuck = self.search([('state', 'in', ('applied', 'discom_approved', 'inspection_done', 'meter_installed')),
                             ('last_state_date', '<=', limit)])
        for rec in stuck:
            if rec.activity_ids.filtered(lambda a: a.summary == STUCK_SUMMARY):
                continue
            user = rec.project_id.user_id or rec.create_uid
            rec.activity_schedule('mail.mail_activity_data_todo', summary=STUCK_SUMMARY, user_id=user.id,
                                  note="No progress for %s days." % days)
