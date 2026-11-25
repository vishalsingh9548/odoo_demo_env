from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    drone_flight_ids = fields.One2many("drone.flight.log", "task_id", string="Flights")
    drone_flight_count = fields.Integer(compute="_compute_drone_flights", string="Flights")
    drone_flight_minutes = fields.Float(
        compute="_compute_drone_flights", string="Flight Time (min)", digits=(16, 1),
    )

    @api.depends("drone_flight_ids.state", "drone_flight_ids.duration_min")
    def _compute_drone_flights(self):
        for task in self:
            flights = task.drone_flight_ids.filtered(lambda f: f.state != "cancel")
            task.drone_flight_count = len(flights)
            task.drone_flight_minutes = sum(
                flights.filtered(lambda f: f.state == "done").mapped("duration_min"))

    def action_view_drone_flights(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("drone_flight_log.action_drone_flight_log")
        action["domain"] = [("task_id", "=", self.id)]
        action["context"] = {"default_task_id": self.id}
        return action

    def action_log_drone_flight(self):
        """New flight on this span, starting now (for the crew on site)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Log Flight"),
            "res_model": "drone.flight.log",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
            "context": {"default_task_id": self.id},
        }
