# -*- coding: utf-8 -*-
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
