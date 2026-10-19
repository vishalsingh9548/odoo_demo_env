# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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

    epc_proceed_anyway = fields.Boolean(
        string='Proceed Anyway', copy=False, tracking=True,
        help="A manager ticks this to let work continue although the verdict is "
             "'not feasible' (only matters when 'Stop Work on Not Feasible' is switched on).",
    )

    # Fills in the sequence-based reference number the first time a study is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.feasibility') or 'New'
        return super().create(vals_list)

    # Only an approved, feasible study can lead on to a BOQ
    def _epc_check_ready_for_next_stage(self):
        for study in self:
            if study.approval_state != 'approved':
                raise UserError("Approve the feasibility study before creating a BOQ.")
            if (study.feasibility_result == 'no' and not study.epc_proceed_anyway
                    and self.env['epc.config'].flag('block_not_feasible')):
                raise UserError(
                    "This study says the project is not feasible. Mark the lead as lost, "
                    "or ask a Project Manager to tick 'Proceed anyway' on the study.")

    # Opens the standard "Lost" reason wizard for this study's lead / opportunity
    def action_mark_lead_lost(self):
        self.ensure_one()
        if not self.lead_id:
            raise UserError("This study is not linked to a lead.")
        action = self.env['ir.actions.actions']._for_xml_id('crm.crm_lead_lost_action')
        action['context'] = {'default_lead_ids': self.lead_id.ids, 'active_ids': self.lead_id.ids}
        return action
