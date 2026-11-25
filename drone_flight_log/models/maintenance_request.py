from odoo import _, fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    drone_flight_id = fields.Many2one(
        "drone.flight.log", string="Flight", index="btree_not_null", copy=False,
        help="The flight on which the equipment broke.",
    )

    def write(self, vals):
        result = super().write(vals)
        if "stage_id" in vals:
            done = self.filtered(lambda r: r.done and r.equipment_id.drone_equipment_type)
            # A completed maintenance resets the drone's "flight hours since service".
            drones = done.equipment_id.filtered(lambda e: e.drone_equipment_type == "drone")
            if drones:
                drones.sudo().write({"last_service_date": fields.Datetime.now()})
            # A completed repair puts broken equipment back in service, in the store:
            # repairs are done at the workshop, so it is free for the next job.
            repaired = done.filtered(lambda r: r.maintenance_type == "corrective").equipment_id.filtered(
                lambda e: e.drone_operational_state == "broken")
            if repaired:
                repaired.sudo().write({
                    "drone_operational_state": "ok",
                    "drone_broken_flight_id": False,
                    "drone_project_id": False,
                    "location": _("Store"),
                })
        return result
