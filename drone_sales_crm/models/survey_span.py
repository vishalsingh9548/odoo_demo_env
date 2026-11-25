from odoo import fields, models

CROSSING_TYPES = [
    ("river", "River"),
    ("farmland", "Farmland / Crops"),
    ("road", "Road / Highway"),
    ("power_line", "Power Line"),
    ("rail", "Railway"),
    ("other", "Other"),
]


class DroneSurveySpan(models.Model):
    """One span measured during the site survey, kept on the opportunity."""

    _name = "drone.survey.span"
    _description = "Survey Span"
    _order = "lead_id, sequence, id"

    lead_id = fields.Many2one(
        "crm.lead", string="Opportunity", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Span No.", required=True)
    tower_from = fields.Char(string="Tower From")
    tower_to = fields.Char(string="Tower To")
    length_m = fields.Float(string="Length (m)", digits=(16, 2))
    crossing_type = fields.Selection(CROSSING_TYPES, string="Crossing", default="farmland")
    remarks = fields.Text()

    _sql_constraints = [
        ("length_m_positive", "CHECK(length_m >= 0)", "A span length cannot be negative."),
    ]
