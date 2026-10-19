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

    # Fills in the sequence-based reference number the first time a survey is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.site.survey') or 'New'
        return super().create(vals_list)
