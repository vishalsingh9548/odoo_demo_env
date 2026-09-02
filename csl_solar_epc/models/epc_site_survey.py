# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcSiteSurvey(models.Model):
    """Stage 2 of the EPC pipeline: the physical visit to the customer's site
    to measure the roof/land, check the electrical connection and record
    anything that will affect the solar system design.
    """
    _name = 'epc.site.survey'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Site Survey'
    _order = 'survey_date desc, id desc'

    name = fields.Char(
        string='Survey Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this survey, e.g. SS/2026/00001.",
    )
    lead_id = fields.Many2one(
        'crm.lead', string='Lead / Opportunity', tracking=True,
        help="The CRM lead this survey was requested from.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='lead_id.partner_id', store=True,
        help="The customer whose site is being surveyed, taken from the lead.",
    )
    survey_date = fields.Date(
        string='Survey Date', tracking=True,
        help="The date the engineer visited (or will visit) the site.",
    )
    engineer_id = fields.Many2one(
        'res.users', string='Survey Engineer', tracking=True,
        help="The engineer responsible for carrying out this site survey.",
    )

    site_address = fields.Text(
        string='Site Address', related='lead_id.site_address', readonly=False,
        help="The address of the site being surveyed.",
    )
    roof_or_land_type = fields.Selection(
        [
            ('rcc_roof', 'RCC Roof'),
            ('sheet_roof', 'Sheet Roof'),
            ('ground_mounted', 'Ground Mounted'),
        ],
        string='Roof / Land Type',
        help="What kind of surface the panels will be mounted on.",
    )
    available_area_sqft = fields.Float(
        string='Available Area (sqft)',
        help="Usable roof or land area measured on site, in square feet.",
    )
    sanctioned_load_kw = fields.Float(
        string='Sanctioned Load (kW)',
        help="The maximum electrical load the site's utility connection allows.",
    )
    has_existing_transformer = fields.Boolean(
        string='Existing Transformer Available',
        help="Tick this if a transformer is already present at the site.",
    )
    grid_access_available = fields.Boolean(
        string='Grid Access Available',
        help="Tick this if the site already has a working grid connection.",
    )
    shadow_analysis = fields.Text(
        string='Shadow Analysis',
        help="Notes on anything that could cast a shadow on the panels during the "
             "day (trees, water tanks, neighbouring buildings, etc.).",
    )
    site_photo = fields.Binary(
        string='Site Photo',
        help="A representative photo of the site. Additional photos and files can "
             "be attached in the chatter below.",
    )
    site_photo_filename = fields.Char(
        string='Site Photo Filename', help="Original filename of the uploaded site photo.",
    )
    survey_report = fields.Html(
        string='Survey Report',
        help="The engineer's written summary of what was found during the visit.",
    )
    is_feasible = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Feasible?',
        help="The engineer's on-the-spot verdict on whether this site is workable "
             "for solar. A detailed Technical Feasibility study happens next.",
    )

    feasibility_count = fields.Integer(
        string='Feasibility Study Count', compute='_compute_feasibility_count',
        help="How many Technical Feasibility studies were created from this survey.",
    )
    feasibility_ids = fields.One2many(
        'epc.feasibility', 'site_survey_id', string='Feasibility Studies',
        help="Technical Feasibility studies created from this survey.",
    )

    # Fills in the sequence-based reference number the first time a survey is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.site.survey') or 'New'
        return super().create(vals_list)

    # Counts the Feasibility studies linked to this survey, for the smart button on the form
    @api.depends('feasibility_ids')
    def _compute_feasibility_count(self):
        for survey in self:
            survey.feasibility_count = len(survey.feasibility_ids)

    # Creates a new Technical Feasibility study pre-linked to this survey, called
    # from the "Create Feasibility Study" button
    def action_create_feasibility(self):
        self.ensure_one()
        feasibility = self.env['epc.feasibility'].create({
            'site_survey_id': self.id,
            'lead_id': self.lead_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.feasibility',
            'view_mode': 'form',
            'res_id': feasibility.id,
            'target': 'current',
        }

    # Opens the list of Feasibility studies already linked to this survey, called
    # from the "Feasibility Studies" smart button
    def action_view_feasibility(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feasibility Studies',
            'res_model': 'epc.feasibility',
            'view_mode': 'list,form',
            'domain': [('site_survey_id', '=', self.id)],
            'context': {'default_site_survey_id': self.id, 'default_lead_id': self.lead_id.id},
        }
