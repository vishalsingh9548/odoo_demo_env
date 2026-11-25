from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    drone_flight_count = fields.Integer(compute="_compute_drone_flight_count", string="Flights")

    def _compute_drone_flight_count(self):
        counts = dict(self.env["drone.flight.log"]._read_group(
            [("project_id", "in", self.ids), ("state", "!=", "cancel")],
            ["project_id"], ["__count"],
        ))
        for project in self:
            project.drone_flight_count = counts.get(project, 0)

    def action_view_drone_flights(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("drone_flight_log.action_drone_flight_log")
        action["domain"] = [("project_id", "=", self.id)]
        action["context"] = {"search_default_group_task": 1}
        return action
