# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Adds Solar EPC qualification questions to the standard CRM Lead/Opportunity
    form, so a sales person captures everything needed to schedule a Site Survey
    right from the very first conversation with the customer.
    """
    _inherit = 'crm.lead'

    customer_segment = fields.Selection(
        [
            ('residential', 'Residential'),
            ('commercial', 'Commercial'),
            ('industrial', 'Industrial'),
        ],
        string='Customer Segment',
        help="What kind of customer this is (home, business or factory). This "
             "decides which product range and paperwork apply later on.",
    )
    proposed_capacity_kw = fields.Float(
        string='Proposed Capacity (kW)',
        help="The solar system size the customer is asking about, in kilowatts. "
             "This is a rough starting number — the exact size gets confirmed "
             "during the Site Survey and Technical Feasibility stages.",
    )
    monthly_electricity_bill = fields.Float(
        string='Monthly Electricity Bill',
        help="The customer's average current electricity bill. Used to sanity-check "
             "the proposed system size against their real power usage.",
    )
    roof_or_land_type = fields.Selection(
        [
            ('rcc_roof', 'RCC Roof'),
            ('sheet_roof', 'Sheet Roof'),
            ('ground_mounted', 'Ground Mounted'),
        ],
        string='Roof / Land Type',
        help="Where the panels would physically go: a concrete roof, a metal sheet "
             "roof, or open ground. This affects the mounting structure design.",
    )
    site_address = fields.Text(
        string='Site Address',
        help="The physical address where the solar system would be installed, if "
             "different from the contact's main address.",
    )
    site_latitude = fields.Char(
        string='Site Latitude',
        help="GPS latitude of the installation site, used to plan the site visit "
             "and later to estimate sun exposure.",
    )
    site_longitude = fields.Char(
        string='Site Longitude',
        help="GPS longitude of the installation site, used to plan the site visit "
             "and later to estimate sun exposure.",
    )
    sanctioned_load_kw = fields.Float(
        string='Sanctioned Load (kW)',
        help="The maximum electrical load the customer's utility connection is "
             "approved for. Solar system size is often capped by this number.",
    )
    has_existing_transformer = fields.Boolean(
        string='Existing Transformer Available',
        help="Tick this if the site already has its own electrical transformer "
             "available for the solar connection.",
    )
    grid_access_available = fields.Boolean(
        string='Grid Access Available',
        help="Tick this if the site already has a working grid electricity "
             "connection to tie the solar system into.",
    )
    expected_closure_date = fields.Date(
        string='Expected Closure Date',
        help="The date the sales person expects to close this deal. Used for "
             "pipeline forecasting.",
    )

    site_survey_count = fields.Integer(
        string='Site Survey Count', compute='_compute_site_survey_count',
        help="How many Site Survey records exist for this lead.",
    )
    feasibility_count = fields.Integer(
        string='Feasibility Study Count', compute='_compute_feasibility_count',
        help="How many Technical Feasibility studies exist for this lead.",
    )
    boq_count = fields.Integer(
        string='BOQ Count', compute='_compute_boq_count',
        help="How many Bill of Quantities (BOQ) records exist for this lead.",
    )

    # Counts the Site Survey records linked to this lead, for the smart button on the form
    @api.depends('site_survey_ids')
    def _compute_site_survey_count(self):
        for lead in self:
            lead.site_survey_count = len(lead.site_survey_ids)

    # Counts the Feasibility Study records linked to this lead, for the smart button on the form
    @api.depends('feasibility_ids')
    def _compute_feasibility_count(self):
        for lead in self:
            lead.feasibility_count = len(lead.feasibility_ids)

    # Counts the BOQ records linked to this lead, for the smart button on the form
    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for lead in self:
            lead.boq_count = len(lead.boq_ids)

    site_survey_ids = fields.One2many(
        'epc.site.survey', 'lead_id', string='Site Surveys',
        help="All Site Survey visits scheduled or completed for this lead.",
    )
    feasibility_ids = fields.One2many(
        'epc.feasibility', 'lead_id', string='Feasibility Studies',
        help="All Technical Feasibility studies done for this lead.",
    )
    boq_ids = fields.One2many(
        'epc.boq', 'lead_id', string='BOQs',
        help="All Bill of Quantities (costing sheets) prepared for this lead.",
    )

    # Opens (or creates, if none exist yet) a Site Survey for this lead, called from
    # the "Schedule Site Survey" button on the Lead form
    def action_create_site_survey(self):
        self.ensure_one()
        survey = self.env['epc.site.survey'].create({'lead_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.site.survey',
            'view_mode': 'form',
            'res_id': survey.id,
            'target': 'current',
        }

    # Opens the list of Site Surveys already linked to this lead, called from the
    # "Site Surveys" smart button
    def action_view_site_surveys(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Site Surveys',
            'res_model': 'epc.site.survey',
            'view_mode': 'list,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }
