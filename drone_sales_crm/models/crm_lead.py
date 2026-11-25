from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    line_name = fields.Char(
        string="Line Name", tracking=True,
        help="Transmission line, e.g. 765kV Nimrana-Bareilly.",
    )
    voltage_kv = fields.Integer(string="Voltage (kV)", tracking=True)
    site_location = fields.Char(string="Site / Route")
    survey_span_ids = fields.One2many(
        "drone.survey.span", "lead_id", string="Survey Spans", copy=True
    )
    span_count = fields.Integer(
        string="Spans", compute="_compute_span_totals", store=True
    )
    total_km = fields.Float(
        string="Total Length (km)", digits=(16, 3),
        compute="_compute_span_totals", store=True,
    )

    @api.depends("survey_span_ids", "survey_span_ids.length_m")
    def _compute_span_totals(self):
        for lead in self:
            lead.span_count = len(lead.survey_span_ids)
            lead.total_km = sum(lead.survey_span_ids.mapped("length_m")) / 1000.0

    def _prepare_opportunity_quotation_context(self):
        """Carry the job details onto a quotation created from the opportunity."""
        context = super()._prepare_opportunity_quotation_context()
        context.update({
            "default_line_name": self.line_name,
            "default_voltage_kv": self.voltage_kv,
            "default_site_location": self.site_location,
        })
        return context
