from odoo import fields, models

from .survey_span import CROSSING_TYPES


class ProjectTask(models.Model):
    _inherit = "project.task"

    is_span = fields.Boolean(string="Is a Span")
    tower_from = fields.Char(string="Tower From")
    tower_to = fields.Char(string="Tower To")
    span_length_m = fields.Float(string="Span Length (m)", digits=(16, 2))
    crossing_type = fields.Selection(CROSSING_TYPES, string="Crossing")
    survey_span_id = fields.Many2one(
        "drone.survey.span", string="Survey Span", copy=False, index="btree_not_null"
    )
