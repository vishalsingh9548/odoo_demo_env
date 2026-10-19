# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcCommissioning(models.Model):
    """Stage 13 of the EPC pipeline: Commissioning — the formal switch-on and
    hand-off point where the system is tested end-to-end, the customer is
    walked through it, and a commissioning certificate is issued.
    """
    _name = 'epc.commissioning'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Commissioning'
    _order = 'id desc'

    name = fields.Char(
        string='Commissioning Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this commissioning record, e.g. COM/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project being commissioned.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='project_id.partner_id', store=True,
        help="The customer taking ownership of the commissioned system.",
    )
    commissioning_date = fields.Date(
        string='Commissioning Date', default=fields.Date.context_today,
        help="The date the system was switched on and commissioned.",
    )
    commissioning_checklist = fields.Html(
        string='Commissioning Checklist',
        help="A written checklist of everything verified before switching the system on.",
    )
    system_testing_done = fields.Boolean(
        string='System Testing Done',
        help="Tick this once the complete system has been tested end-to-end.",
    )
    generation_verification_kwh = fields.Float(
        string='Verified Generation (kWh)',
        help="The actual power generation measured during commissioning, to confirm "
             "the system performs as designed.",
    )
    customer_walkthrough_done = fields.Boolean(
        string='Customer Walkthrough Done',
        help="Tick this once the customer has been walked through how the system works.",
    )
    customer_approved = fields.Boolean(
        string='Customer Approved',
        help="Tick this once the customer has formally accepted the commissioned system.",
    )
    commissioning_certificate = fields.Binary(
        string='Commissioning Certificate',
        help="The signed commissioning certificate document.",
    )
    commissioning_certificate_filename = fields.Char(
        string='Commissioning Certificate Filename', help="Original filename of the uploaded certificate.",
    )
    epc_needs_final_qc = fields.Boolean(
        string='Needs Final QC', compute='_compute_epc_needs_final_qc',
        help="True while this project still has no passed Final Quality Check "
             "logged against it — drives the 'Log Quality Check' button, and "
             "blocks Submit for Approval until it's resolved. A system "
             "shouldn't be commissioned before its Final QC has actually passed.",
    )
    epc_can_consume_site_stock = fields.Boolean(
        string='Can Consume Site Stock', compute='_compute_epc_can_consume_site_stock',
        help="True once this project has a passed Final QC and still has "
             "material sitting at its site location — drives the 'Consume "
             "Site Stock' button, so it can be done from here instead of "
             "having to go find the Final QC record itself.",
    )
    epc_needs_handover = fields.Boolean(
        string='Needs Handover', compute='_compute_epc_needs_handover',
        help="True once this commissioning has been approved and its project "
             "still has no Handover & Closure record yet — drives the "
             "'Proceed to Handover' button, so the last pipeline step is one "
             "click away instead of having to go find the Handover menu and "
             "fill in the project by hand.",
    )

    # Fills in the sequence-based reference number the first time a record is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.commissioning') or 'New'
        return super().create(vals_list)

    # Works out whether this commissioning's project is still missing a
    # passed Final Quality Check, so the "Log Quality Check" button only
    # shows up exactly when it's actually needed
    @api.depends('project_id')
    def _compute_epc_needs_final_qc(self):
        for commissioning in self:
            passed_final_qc = self.env['epc.quality.check'].search_count([
                ('project_id', '=', commissioning.project_id.id),
                ('category', '=', 'final'),
                ('overall_result', '=', 'pass'),
            ]) if commissioning.project_id else 0
            commissioning.epc_needs_final_qc = not passed_final_qc

    # Works out whether there's still material sitting at this project's site
    # that a passed Final QC could consume, so the "Consume Site Stock"
    # button only shows up exactly when it would actually do something
    @api.depends('project_id')
    def _compute_epc_can_consume_site_stock(self):
        for commissioning in self:
            site_location = commissioning.project_id.site_location_id
            commissioning.epc_can_consume_site_stock = bool(site_location) and bool(
                self.env['stock.quant'].search_count([
                    ('location_id', '=', site_location.id),
                    ('quantity', '>', 0),
                ])
            )

    # Works out whether this commissioning's project still needs a Handover
    # & Closure record, so the "Proceed to Handover" button only shows up
    # exactly when it would actually do something
    @api.depends('approval_state', 'project_id')
    def _compute_epc_needs_handover(self):
        for commissioning in self:
            has_handover = bool(commissioning.project_id) and self.env['epc.handover'].search_count([
                ('project_id', '=', commissioning.project_id.id),
            ])
            commissioning.epc_needs_handover = commissioning.approval_state == 'approved' and not has_handover

    # Opens a new, blank Handover & Closure record pre-filled with this
    # commissioning's project, so Stage 14 can be started directly from here
    # the moment commissioning is approved — called from the "Proceed to
    # Handover" header button
    def action_create_handover(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.handover',
            'view_mode': 'form',
            'context': {'default_project_id': self.project_id.id},
            'target': 'current',
        }

    # Finds this project's passed Final QC and consumes whatever material is
    # still sitting at its site location through it — called from the
    # "Consume Site Stock" header button, so this can be done directly from
    # Commissioning instead of having to go find the Final QC record itself
    def action_consume_site_stock(self):
        self.ensure_one()
        final_qc = self.env['epc.quality.check'].search([
            ('project_id', '=', self.project_id.id),
            ('category', '=', 'final'),
            ('overall_result', '=', 'pass'),
        ], order='id desc', limit=1)
        if not final_qc:
            raise UserError(
                "This project has no passed Final Quality Check to consume site stock against."
            )
        return final_qc.action_consume_site_stock()

    # Opens a blank, pre-filled Final Quality Check form as a wizard-style
    # dialog right on top of this commissioning record (target 'new', not a
    # page navigation) — called from the "Log Quality Check" header button,
    # the same pattern used for a project's incoming receipts
    def action_log_quality_check(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.quality.check',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_category': 'final',
            },
        }

    # Blocks Submit for Approval until the project has actually passed its
    # Final Quality Check — a system shouldn't move toward commissioning
    # sign-off on the strength of an on-screen checkbox alone
    def action_submit(self):
        for commissioning in self:
            if commissioning.epc_needs_final_qc:
                raise UserError(
                    "This project has not passed its Final Quality Check yet. "
                    "Log one (category Final QC) and pass it before submitting "
                    "this commissioning for approval."
                )
        return super().action_submit()
