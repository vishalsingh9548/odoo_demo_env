# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class EpcAmcContract(models.Model):
    """Stage 17 of the EPC pipeline: O&M / AMC (Annual Maintenance Contract)
    Management. This is the one document standard Odoo has no equivalent for —
    it records the maintenance agreement itself (how often to service the
    system, until when, for how much), and hands off the day-to-day complaint
    -> visit -> parts-used work to the standard Helpdesk + Field Service apps
    this module depends on.
    """
    _name = 'epc.amc.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar AMC (Annual Maintenance Contract)'
    _order = 'id desc'

    name = fields.Char(
        string='AMC Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this contract, e.g. AMC/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar installation project this maintenance contract covers.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='project_id.partner_id', store=True,
        help="The customer this maintenance contract is with.",
    )
    start_date = fields.Date(
        string='Start Date', default=fields.Date.context_today, tracking=True,
        help="The date this maintenance contract begins.",
    )
    end_date = fields.Date(
        string='End Date', tracking=True,
        help="The date this maintenance contract expires.",
    )
    contract_value = fields.Float(
        string='Contract Value',
        help="How much the customer pays for this maintenance contract.",
    )
    service_frequency = fields.Selection(
        [
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('half_yearly', 'Half-Yearly'),
            ('yearly', 'Yearly'),
        ],
        string='Preventive Service Frequency',
        help="How often a preventive maintenance visit should happen under this contract.",
    )
    next_service_date = fields.Date(
        string='Next Preventive Service Due',
        help="The date the next scheduled preventive maintenance visit is due.",
    )
    preventive_maintenance_plan = fields.Html(
        string='Preventive Maintenance Plan',
        help="What gets checked/cleaned/serviced during each preventive maintenance visit.",
    )
    sla_response_hours = fields.Float(
        string='SLA Response Time (Hours)',
        help="How many hours the company commits to respond within when the customer raises a complaint.",
    )
    warranty_end_date = fields.Date(
        string='Warranty End Date',
        help="When the equipment manufacturer's warranty ends, separate from this AMC contract.",
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired'), ('terminated', 'Terminated')],
        string='Status', default='draft', tracking=True,
        help="Whether this contract is still being set up, currently active, has run its "
             "course, or was cancelled early.",
    )
    helpdesk_team_id = fields.Many2one(
        'helpdesk.team', string='Support Team',
        help="Which Helpdesk team handles complaints raised under this AMC contract. "
             "The team must have Field Service enabled so visits can be scheduled.",
    )

    ticket_ids = fields.One2many(
        'helpdesk.ticket', 'amc_contract_id', string='Complaint Tickets',
        help="Every complaint/service ticket raised under this AMC contract.",
    )
    ticket_count = fields.Integer(
        string='Ticket Count', compute='_compute_ticket_count',
        help="How many complaint tickets have been raised under this contract.",
    )

    reminder_sent = fields.Boolean(
        string='Expiry Reminder Sent', copy=False,
        help="Set once the 'contract ending soon' reminder has been sent, so it is sent only once.",
    )

    # Fills in the sequence-based reference number the first time a contract is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.amc.contract') or 'New'
        return super().create(vals_list)

    # Counts the complaint tickets linked to this contract, for the smart button on the form
    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        for contract in self:
            contract.ticket_count = len(contract.ticket_ids)

    # Switches the contract to Active once it's ready to start covering the customer
    def action_activate(self):
        self.write({'state': 'active'})

    # Switches the contract to Terminated if it needs to be cancelled before its end date
    def action_terminate(self):
        self.write({'state': 'terminated'})

    # Opens a blank Helpdesk ticket pre-filled with this contract's team and customer,
    # so a complaint can be logged in a couple of clicks — from there, the standard
    # Helpdesk + Field Service apps take over (Ticket -> FSM Task -> Engineer Visit)
    def action_log_complaint(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_team_id': self.helpdesk_team_id.id,
                'default_partner_id': self.partner_id.id,
                'default_amc_contract_id': self.id,
            },
        }

    # Opens the list of complaint tickets already linked to this contract, called
    # from the "Complaint Tickets" smart button
    def action_view_tickets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Complaint Tickets',
            'res_model': 'helpdesk.ticket',
            'view_mode': 'list,form',
            'domain': [('amc_contract_id', '=', self.id)],
            'context': {'default_amc_contract_id': self.id, 'default_partner_id': self.partner_id.id},
        }

    # Months between two preventive services for each frequency
    _EPC_FREQUENCY_MONTHS = {'monthly': 1, 'quarterly': 3, 'half_yearly': 6, 'yearly': 12}

    # Runs every day: marks finished contracts as Expired, reminds the team a
    # month before a contract ends and (when switched on) creates the field
    # service visits that have fallen due
    @api.model
    def _cron_epc_amc_maintenance(self):
        today = fields.Date.context_today(self)
        config = self.env['epc.config']

        expired = self.search([('state', '=', 'active'), ('end_date', '!=', False), ('end_date', '<', today)])
        for contract in expired:
            contract.state = 'expired'
            contract.message_post(body="Contract end date passed - marked as Expired.")

        if not config.flag('disable_notifications'):
            soon = self.search([
                ('state', '=', 'active'), ('reminder_sent', '=', False),
                ('end_date', '!=', False), ('end_date', '>=', today),
                ('end_date', '<=', today + relativedelta(days=30)),
            ])
            for contract in soon:
                users = contract.project_id.user_id or self.env['epc.approval.mixin']._epc_approvers()
                for user in users:
                    contract.activity_schedule(
                        'mail.mail_activity_data_todo', user_id=user.id,
                        summary="AMC %s ends on %s - renew?" % (contract.name, contract.end_date))
                contract.reminder_sent = True

        if config.flag('amc_generate_services'):
            self._epc_generate_due_services(today)

    # Creates one Field Service task per contract whose preventive service is
    # due, then moves the next due date forward by the contract's frequency
    @api.model
    def _epc_generate_due_services(self, today):
        fsm_project = self.env.ref('csl_epc_amc.epc_fsm_project', raise_if_not_found=False)
        if not fsm_project:
            return
        due = self.search([
            ('state', '=', 'active'), ('service_frequency', '!=', False),
            ('next_service_date', '!=', False), ('next_service_date', '<=', today),
        ])
        for contract in due:
            self.env['project.task'].create({
                'name': "Preventive service - %s (%s)" % (contract.name, contract.partner_id.name or ''),
                'project_id': fsm_project.id,
                'partner_id': contract.partner_id.id,
                'date_deadline': contract.next_service_date,
            })
            months = self._EPC_FREQUENCY_MONTHS[contract.service_frequency]
            next_date = contract.next_service_date
            while next_date <= today:
                next_date = next_date + relativedelta(months=months)
            contract.next_service_date = next_date
            contract.message_post(body="Preventive service task created; next service due %s." % next_date)

    # Makes a new draft contract that starts the day after this one ends and
    # runs for the same length of time
    def action_renew(self):
        self.ensure_one()
        start = (self.end_date or fields.Date.context_today(self)) + relativedelta(days=1)
        length = (self.end_date - self.start_date) if self.end_date and self.start_date else relativedelta(years=1)
        end = start + (length if isinstance(length, relativedelta) else length)
        months = self._EPC_FREQUENCY_MONTHS.get(self.service_frequency)
        new = self.copy({
            'start_date': start,
            'end_date': end,
            'state': 'draft',
            'next_service_date': start + relativedelta(months=months) if months else False,
        })
        self.message_post(body="Renewed as %s." % new.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.amc.contract',
            'view_mode': 'form',
            'res_id': new.id,
            'target': 'current',
        }
