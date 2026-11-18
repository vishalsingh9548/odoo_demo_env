# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcDesign(models.Model):
    """System Design: the engineer's choice of panels, inverter and string
    layout for a feasible site. Sits between Feasibility and BOQ; it is
    optional unless the 'Require Approved Design Before BOQ' switch is on."""
    _name = 'epc.design'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar System Design'
    _order = 'id desc'

    name = fields.Char(
        string='Design Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this design, e.g. DSG/2026/00001.",
    )
    feasibility_id = fields.Many2one(
        'epc.feasibility', string='Feasibility Study', tracking=True,
        help="The approved feasibility study this design is based on.",
    )
    lead_id = fields.Many2one(
        'crm.lead', string='Lead / Opportunity', tracking=True,
        help="The CRM lead this design belongs to.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='lead_id.partner_id', store=True,
        help="The customer this design is for.",
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
        help="Currency used for the estimated system cost.",
    )

    # --- Panels ---
    panel_make = fields.Char(string='Panel Make / Model', help="Brand and model of the solar panel.")
    panel_watt = fields.Float(string='Panel Rating (Wp)', help="Rated power of one panel, in watts-peak.")
    panel_count = fields.Integer(string='Number of Panels', help="Total number of panels in the system.")
    panel_vmp = fields.Float(string='Panel Vmp (V)', help="Voltage of one panel at maximum power (from the datasheet).")
    panel_voc = fields.Float(string='Panel Voc (V)', help="Open-circuit voltage of one panel (from the datasheet).")

    # --- Inverter ---
    inverter_make = fields.Char(string='Inverter Make / Model', help="Brand and model of the inverter.")
    inverter_kw = fields.Float(string='Inverter Rating (kW)', help="AC rating of one inverter, in kilowatts.")
    inverter_count = fields.Integer(string='Number of Inverters', default=1, help="How many inverters of this model are used.")
    mppt_min_voltage = fields.Float(string='MPPT Min Voltage (V)', help="Lowest DC voltage at which the inverter tracks maximum power.")
    mppt_max_voltage = fields.Float(string='MPPT Max Voltage (V)', help="Highest DC voltage the inverter accepts.")

    # --- Strings and mounting ---
    string_count = fields.Integer(string='Number of Strings', help="How many series strings of panels are connected.")
    panels_per_string = fields.Integer(string='Panels per String', help="How many panels are connected in series in one string.")
    mounting_type = fields.Selection(
        [('rcc', 'RCC Roof Structure'), ('sheet', 'Sheet Roof Structure'),
         ('ground', 'Ground Mounted'), ('carport', 'Carport / Elevated')],
        string='Mounting Type', help="The kind of mounting structure used.",
    )

    # --- Drawings ---
    layout_drawing = fields.Binary(string='Layout Drawing', help="Structure / panel layout drawing for this site.")
    layout_drawing_filename = fields.Char(string='Layout Filename')
    sld_drawing = fields.Binary(string='Single-Line Diagram (SLD)', help="Electrical single-line diagram of the system.")
    sld_drawing_filename = fields.Char(string='SLD Filename')

    # --- Estimates ---
    specific_yield = fields.Float(
        string='Specific Yield (kWh/kWp/year)', default=1400.0,
        help="Expected yearly generation per kWp. Filled from the feasibility "
             "study when it has one, otherwise 1400. Change it if needed.",
    )
    tariff_per_unit = fields.Float(
        string='Tariff (per kWh)', default=8.0,
        help="What the customer pays per unit of electricity today; used to "
             "estimate savings.",
    )
    estimated_system_cost = fields.Monetary(
        string='Estimated System Cost', currency_field='currency_id',
        help="Optional rough cost. If filled, payback years are worked out.",
    )

    dc_capacity_kw = fields.Float(
        string='DC Capacity (kWp)', compute='_compute_capacity', store=True, digits=(16, 2),
        help="Panels x rating. This is the size of the solar array.",
    )
    ac_capacity_kw = fields.Float(
        string='AC Capacity (kW)', compute='_compute_capacity', store=True, digits=(16, 2),
        help="Inverter rating x number of inverters. The most AC power the system can deliver.",
    )
    dc_ac_ratio = fields.Float(
        string='DC/AC Ratio', compute='_compute_capacity', store=True, digits=(16, 2),
        help="DC capacity divided by AC capacity. Usually between 1.0 and 1.4.",
    )
    annual_generation_kwh = fields.Float(
        string='Expected Annual Generation (kWh)', compute='_compute_estimates', store=True, digits=(16, 0),
        help="DC capacity x specific yield.",
    )
    annual_savings = fields.Monetary(
        string='Estimated Annual Savings', compute='_compute_estimates', store=True, currency_field='currency_id',
        help="Expected yearly generation x tariff.",
    )
    payback_years = fields.Float(
        string='Payback (years)', compute='_compute_estimates', store=True, digits=(16, 1),
        help="Estimated system cost divided by yearly savings (blank when no cost is entered).",
    )
    string_voltage_vmp = fields.Float(
        string='String Vmp (V)', compute='_compute_string_check', digits=(16, 0),
        help="Panels per string x panel Vmp: working voltage of one string.",
    )
    string_voltage_voc = fields.Float(
        string='String Voc (V)', compute='_compute_string_check', digits=(16, 0),
        help="Panels per string x panel Voc: highest voltage of one string (cold morning).",
    )
    design_warning = fields.Text(
        string='Design Warnings', compute='_compute_string_check',
        help="Plain-language warnings when the numbers do not fit together.",
    )

    # Works out the array size, inverter size and their ratio
    @api.depends('panel_count', 'panel_watt', 'inverter_kw', 'inverter_count')
    def _compute_capacity(self):
        for design in self:
            dc = design.panel_count * design.panel_watt / 1000.0
            ac = design.inverter_kw * design.inverter_count
            design.dc_capacity_kw = dc
            design.ac_capacity_kw = ac
            design.dc_ac_ratio = dc / ac if ac else 0.0

    # Works out yearly generation, savings and payback
    @api.depends('dc_capacity_kw', 'specific_yield', 'tariff_per_unit', 'estimated_system_cost')
    def _compute_estimates(self):
        for design in self:
            generation = design.dc_capacity_kw * design.specific_yield
            savings = generation * design.tariff_per_unit
            design.annual_generation_kwh = generation
            design.annual_savings = savings
            design.payback_years = design.estimated_system_cost / savings if savings and design.estimated_system_cost else 0.0

    # Checks that strings, voltage and inverter size fit together
    @api.depends('panels_per_string', 'string_count', 'panel_count', 'panel_vmp', 'panel_voc',
                 'mppt_min_voltage', 'mppt_max_voltage', 'dc_ac_ratio')
    def _compute_string_check(self):
        for design in self:
            vmp = design.panels_per_string * design.panel_vmp
            voc = design.panels_per_string * design.panel_voc
            design.string_voltage_vmp = vmp
            design.string_voltage_voc = voc
            warnings = []
            if design.string_count and design.panels_per_string and design.panel_count \
                    and design.string_count * design.panels_per_string != design.panel_count:
                warnings.append("Strings x panels per string (%s) does not match the number of panels (%s)." % (
                    design.string_count * design.panels_per_string, design.panel_count))
            if design.mppt_max_voltage and voc > design.mppt_max_voltage:
                warnings.append("String Voc (%.0f V) is above the inverter's maximum voltage (%.0f V): the inverter could be damaged on a cold morning." % (voc, design.mppt_max_voltage))
            if design.mppt_min_voltage and vmp and vmp < design.mppt_min_voltage:
                warnings.append("String Vmp (%.0f V) is below the inverter's minimum MPPT voltage (%.0f V): the inverter may not start." % (vmp, design.mppt_min_voltage))
            if design.dc_ac_ratio and (design.dc_ac_ratio > 1.5 or design.dc_ac_ratio < 0.9):
                warnings.append("DC/AC ratio %.2f is unusual (normally 1.0 to 1.4)." % design.dc_ac_ratio)
            design.design_warning = "\n".join(warnings)

    # A design that starts from a feasibility study takes its yield from it
    @api.onchange('feasibility_id')
    def _onchange_feasibility_id(self):
        if self.feasibility_id:
            self.lead_id = self.feasibility_id.lead_id
            if self.feasibility_id.specific_yield:
                self.specific_yield = self.feasibility_id.specific_yield

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.design') or 'New'
        return super().create(vals_list)

    boq_ids = fields.One2many('epc.boq', 'design_id', string='BOQs', help="BOQs created from this design.")
    boq_count = fields.Integer(string='BOQ Count', compute='_compute_boq_count', help="How many BOQs were created from this design.")

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for design in self:
            design.boq_count = len(design.boq_ids)

    # Creates a BOQ from this approved design, pre-filled with panels, inverter and structure lines
    def action_create_boq(self):
        self.ensure_one()
        if self.approval_state != 'approved':
            raise UserError("Approve the design before creating a BOQ from it.")
        if self.feasibility_id:
            self.feasibility_id._epc_check_ready_for_next_stage()
        lines = []
        if self.panel_count:
            lines.append((0, 0, {
                'category': 'solar_module', 'quantity': self.panel_count,
                'description': "Solar module %s %.0f Wp" % (self.panel_make or '', self.panel_watt)}))
        if self.inverter_count:
            lines.append((0, 0, {
                'category': 'inverter', 'quantity': self.inverter_count,
                'description': "Inverter %s %.1f kW" % (self.inverter_make or '', self.inverter_kw)}))
        mounting = dict(self._fields['mounting_type'].selection).get(self.mounting_type)
        lines.append((0, 0, {
            'category': 'mounting_structure', 'quantity': 1,
            'description': "Mounting structure %s (%.2f kWp)" % (mounting or '', self.dc_capacity_kw)}))
        boq = self.env['epc.boq'].create({
            'feasibility_id': self.feasibility_id.id,
            'lead_id': self.lead_id.id,
            'design_id': self.id,
            'line_ids': lines,
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'epc.boq',
            'view_mode': 'form', 'res_id': boq.id, 'target': 'current',
        }

    # Opens the BOQs made from this design
    def action_view_boq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'BOQs', 'res_model': 'epc.boq',
            'view_mode': 'list,form', 'domain': [('design_id', '=', self.id)],
        }
