# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcFeasibility(models.Model):
    """Stage 3 of the EPC pipeline: turns the raw site-survey measurements into
    a concrete technical proposal — how big the system should be, how it will
    be laid out, and how much power it is expected to generate — before any
    price is quoted to the customer.
    """
    _name = 'epc.feasibility'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Technical Feasibility Study'
    _order = 'id desc'

    name = fields.Char(
        string='Feasibility Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this study, e.g. TF/2026/00001.",
    )
    site_survey_id = fields.Many2one(
        'epc.site.survey', string='Site Survey', tracking=True,
        help="The Site Survey this feasibility study is based on.",
    )
    lead_id = fields.Many2one(
        'crm.lead', string='Lead / Opportunity', tracking=True,
        help="The CRM lead this feasibility study belongs to.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='lead_id.partner_id', store=True,
        help="The customer this feasibility study is for.",
    )

    proposed_capacity_kw = fields.Float(
        string='Proposed Capacity (kW)',
        help="The recommended solar system size after checking the site's real "
             "constraints (area, load, shading).",
    )
    system_type = fields.Selection(
        [('rooftop', 'Rooftop'), ('ground_mounted', 'Ground Mounted')],
        string='System Type',
        help="Whether the system will sit on a rooftop or on the ground.",
    )
    module_tilt_angle = fields.Float(
        string='Module Tilt Angle (°)',
        help="The angle the solar panels will be tilted at, in degrees, chosen to "
             "maximise sunlight capture at this location.",
    )
    module_orientation = fields.Selection(
        [('north', 'North'), ('south', 'South'), ('east', 'East'), ('west', 'West')],
        string='Module Orientation',
        help="The compass direction the panels will face.",
    )
    plant_layout = fields.Binary(
        string='Plant Layout Drawing',
        help="The site/plant layout drawing (e.g. an AutoCAD export) showing "
             "where each panel row and inverter will be placed.",
    )
    plant_layout_filename = fields.Char(
        string='Plant Layout Filename', help="Original filename of the uploaded layout drawing.",
    )
    annual_generation_estimate_kwh = fields.Float(
        string='Estimated Annual Generation (kWh)',
        help="How much electricity the system is expected to generate in a year, "
             "used to calculate customer savings.",
    )
    performance_ratio = fields.Float(
        string='Performance Ratio (%)',
        help="A standard efficiency measure (0-100%) showing how much of the "
             "theoretical maximum power the system will actually deliver, after "
             "accounting for losses (heat, wiring, shading, dust, etc.).",
    )
    financial_benefits = fields.Html(
        string='Financial Benefits',
        help="Explanation of the customer's expected savings and payback period "
             "based on the estimated generation and their current electricity bill.",
    )
    feasibility_report = fields.Html(
        string='Feasibility Report',
        help="The full written feasibility report shared internally and, if "
             "needed, with the customer.",
    )
    feasibility_result = fields.Selection(
        [('yes', 'Feasible'), ('no', 'Not Feasible')],
        string='Feasibility Result', tracking=True,
        help="The final technical verdict: whether this project should move "
             "forward to costing and quotation.",
    )

    boq_count = fields.Integer(
        string='BOQ Count', compute='_compute_boq_count',
        help="How many Bill of Quantities (BOQ) records were created from this study.",
    )
    boq_ids = fields.One2many(
        'epc.boq', 'feasibility_id', string='BOQs',
        help="Bill of Quantities (costing sheets) created from this feasibility study.",
    )

    # Fills in the sequence-based reference number the first time a study is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.feasibility') or 'New'
        return super().create(vals_list)

    # Counts the BOQs linked to this study, for the smart button on the form
    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for feasibility in self:
            feasibility.boq_count = len(feasibility.boq_ids)

    # Creates a new BOQ (costing sheet) pre-linked to this feasibility study,
    # called from the "Create BOQ" button
    def action_create_boq(self):
        self.ensure_one()
        boq = self.env['epc.boq'].create({
            'feasibility_id': self.id,
            'lead_id': self.lead_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.boq',
            'view_mode': 'form',
            'res_id': boq.id,
            'target': 'current',
        }

    # Opens the list of BOQs already linked to this study, called from the
    # "BOQs" smart button
    def action_view_boq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'BOQs',
            'res_model': 'epc.boq',
            'view_mode': 'list,form',
            'domain': [('feasibility_id', '=', self.id)],
            'context': {'default_feasibility_id': self.id, 'default_lead_id': self.lead_id.id},
        }
