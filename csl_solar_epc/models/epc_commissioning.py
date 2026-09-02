# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    # Fills in the sequence-based reference number the first time a record is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.commissioning') or 'New'
        return super().create(vals_list)
