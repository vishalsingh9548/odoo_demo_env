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
