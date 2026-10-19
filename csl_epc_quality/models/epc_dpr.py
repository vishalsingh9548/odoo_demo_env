# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcDailyProgressReport(models.Model):
    """Stage 11 of the EPC pipeline: the Daily Progress Report (DPR) — a short
    daily diary entry from the site, one per project per day, so anyone in the
    office can see exactly what happened on site without having to call the
    engineer.
    """
    _name = 'epc.dpr'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Daily Progress Report'
    _order = 'report_date desc, id desc'
    _sql_constraints = [
        ('project_date_unique', 'unique(project_id, report_date)',
         'Only one Daily Progress Report is allowed per project per day. Please edit the existing one instead.'),
    ]

    name = fields.Char(
        string='DPR Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this report, e.g. DPR/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project this progress report is for.",
    )
    report_date = fields.Date(
        string='Report Date', default=fields.Date.context_today, required=True, tracking=True,
        help="The day this report covers.",
    )
    reported_by = fields.Many2one(
        'res.users', string='Reported By', default=lambda self: self.env.user,
        help="The person filing this report, usually the site engineer or supervisor.",
    )
    weather = fields.Selection(
        [('sunny', 'Sunny'), ('cloudy', 'Cloudy'), ('rainy', 'Rainy'), ('windy', 'Windy')],
        string='Weather',
        help="Today's weather at site — useful context if progress was slower than planned.",
    )
    manpower_deployed = fields.Integer(
        string='Manpower Deployed',
        help="How many workers were on site today.",
    )
    work_progress_summary = fields.Html(
        string="Today's Work Progress",
        help="A summary of what work was actually done today versus what was planned.",
    )
    material_received = fields.Text(
        string='Material Received',
        help="Any material that arrived on site today.",
    )
    material_consumed = fields.Text(
        string='Material Consumed',
        help="Any material that was used/installed today.",
    )
    equipment_deployed = fields.Text(
        string='Equipment Deployed',
        help="Tools or machinery used on site today (cranes, welding equipment, testing kits, etc.).",
    )
    site_photo = fields.Binary(
        string='Site Photo',
        help="A photo showing today's progress. More photos can be attached in the chatter below.",
    )
    site_photo_filename = fields.Char(
        string='Site Photo Filename', help="Original filename of the uploaded site photo.",
    )
    issues_risks = fields.Text(
        string='Issues / Risks',
        help="Anything that went wrong today, or any risk to tomorrow's plan that management should know about.",
    )
    tomorrow_plan = fields.Text(
        string="Tomorrow's Plan",
        help="What work is planned for the next day.",
    )

    # Fills in the sequence-based reference number the first time a report is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.dpr') or 'New'
        return super().create(vals_list)
