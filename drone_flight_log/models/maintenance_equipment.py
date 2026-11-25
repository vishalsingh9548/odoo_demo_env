from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DRONE_EQUIPMENT_TYPES = [("drone", "Drone"), ("battery", "Drone Battery")]

# A battery is "near limit" from this share of its cycle limit.
BATTERY_WARNING_RATIO = 0.8


class MaintenanceEquipmentCategory(models.Model):
    _inherit = "maintenance.equipment.category"

    drone_equipment_type = fields.Selection(
        DRONE_EQUIPMENT_TYPES, string="Drone Equipment Type",
        help="Equipment in this category is tracked in the drone flight log.",
    )


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    drone_equipment_type = fields.Selection(
        related="category_id.drone_equipment_type", store=True, string="Drone Equipment Type",
    )

    # --- Drone ---------------------------------------------------------------------------
    drone_flight_ids = fields.One2many("drone.flight.log", "drone_id", string="Flights (as drone)")
    service_interval_hours = fields.Float(
        string="Service Interval (flight hours)", default=25.0,
        help="A preventive maintenance request is created when the drone has flown this "
             "many hours since its last completed maintenance.",
    )
    last_service_date = fields.Datetime(
        string="Last Service", readonly=True, copy=False,
        help="Set when a maintenance request of this drone is moved to a 'done' stage.",
    )
    hours_since_service = fields.Float(
        string="Flight Hours Since Service", compute="_compute_hours_since_service", digits=(16, 2),
    )

    # --- Battery -------------------------------------------------------------------------
    battery_flight_ids = fields.Many2many(
        "drone.flight.log", "drone_flight_log_battery_rel", "battery_id", "flight_id",
        string="Flights (as battery)",
    )
    battery_cycle_limit = fields.Integer(
        string="Cycle Limit", default=300,
        help="Number of flights (charge cycles) after which the battery must be retired.",
    )
    battery_health = fields.Selection(
        [("ok", "OK"), ("warning", "Near limit"), ("retire", "Retire")],
        string="Battery Health", compute="_compute_drone_usage", store=True,
    )

    # --- Breakdowns and replacements ------------------------------------------------------
    drone_operational_state = fields.Selection(
        [("ok", "Operational"), ("broken", "Broken")],
        string="Operational Status", default="ok", tracking=True, copy=False,
        help="Broken equipment cannot be put on a flight. It becomes Operational again when "
             "its repair request is completed.",
    )
    drone_broken_flight_id = fields.Many2one(
        "drone.flight.log", string="Broke On Flight", readonly=True, copy=False,
    )
    drone_replacement_request_ids = fields.One2many(
        "drone.equipment.request", "broken_equipment_id", string="Replacement Requests",
    )
    drone_replacement_request_count = fields.Integer(compute="_compute_drone_replacement_request_count")

    # --- Where it is and whether it can be used ----------------------------------------
    drone_project_id = fields.Many2one(
        "project.project", string="Assigned Job", tracking=True, copy=False, index="btree_not_null",
        help="The job this equipment is with. Set when it flies a confirmed flight on a job or is "
             "dispatched to a site as a replacement; cleared with 'Release to Store'.",
    )
    drone_availability = fields.Selection(
        [("free", "Free"), ("busy", "On a Job"), ("broken", "Broken"), ("retired", "Retired")],
        string="Availability", compute="_compute_drone_availability", store=True, group_expand=True,
    )

    # Kanban helpers (not stored)
    drone_kanban_color = fields.Integer(compute="_compute_drone_kanban", string="Board Colour")
    drone_last_flight_day = fields.Date(compute="_compute_drone_kanban", string="Last Flight Day")
    drone_usage_percent = fields.Integer(
        compute="_compute_drone_kanban", string="Usage (%)",
        help="Battery: share of its cycle life used. Drone: share of its service interval used.",
    )

    # --- Both ----------------------------------------------------------------------------
    drone_flight_count = fields.Integer(
        string="Flights", compute="_compute_drone_usage", store=True,
        help="Completed flights. For a battery, this is its number of charge cycles.",
    )
    drone_flight_minutes = fields.Float(
        string="Flight Time (min)", compute="_compute_drone_usage", store=True, digits=(16, 1),
    )
    drone_flight_hours = fields.Float(
        string="Flight Hours", compute="_compute_drone_usage", store=True, digits=(16, 2),
    )
    drone_last_flight_date = fields.Datetime(
        string="Last Flight", compute="_compute_drone_usage", store=True,
    )

    _sql_constraints = [
        ("battery_cycle_limit_positive", "CHECK(battery_cycle_limit >= 0)",
         "The battery cycle limit cannot be negative."),
    ]

    def _drone_done_flights(self):
        self.ensure_one()
        if self.drone_equipment_type == "drone":
            flights = self.drone_flight_ids
        elif self.drone_equipment_type == "battery":
            flights = self.battery_flight_ids
        else:
            flights = self.env["drone.flight.log"]
        return flights.filtered(lambda f: f.state == "done")

    @api.depends(
        "drone_equipment_type", "battery_cycle_limit",
        "drone_flight_ids.state", "drone_flight_ids.duration_min", "drone_flight_ids.takeoff_time",
        "battery_flight_ids.state", "battery_flight_ids.duration_min", "battery_flight_ids.takeoff_time",
    )
    def _compute_drone_usage(self):
        for equipment in self:
            flights = equipment._drone_done_flights()
            minutes = sum(flights.mapped("duration_min"))
            equipment.drone_flight_count = len(flights)
            equipment.drone_flight_minutes = minutes
            equipment.drone_flight_hours = minutes / 60.0
            equipment.drone_last_flight_date = max(flights.mapped("takeoff_time"), default=False)
            if equipment.drone_equipment_type != "battery":
                equipment.battery_health = False
            elif equipment.battery_cycle_limit and len(flights) >= equipment.battery_cycle_limit:
                equipment.battery_health = "retire"
            elif (equipment.battery_cycle_limit
                  and len(flights) >= equipment.battery_cycle_limit * BATTERY_WARNING_RATIO):
                equipment.battery_health = "warning"
            else:
                equipment.battery_health = "ok"

    @api.depends("drone_equipment_type", "drone_operational_state", "battery_health", "scrap_date",
                 "drone_project_id")
    def _compute_drone_availability(self):
        for equipment in self:
            if not equipment.drone_equipment_type:
                equipment.drone_availability = False
            elif equipment.scrap_date or equipment.battery_health == "retire":
                equipment.drone_availability = "retired"
            elif equipment.drone_operational_state == "broken":
                equipment.drone_availability = "broken"
            elif equipment.drone_project_id:
                equipment.drone_availability = "busy"
            else:
                equipment.drone_availability = "free"

    # Odoo colour index per availability, used for the card's left edge.
    _DRONE_KANBAN_COLORS = {"free": 10, "busy": 4, "broken": 1, "retired": 0}

    @api.depends("drone_availability", "drone_equipment_type", "drone_flight_count", "battery_cycle_limit",
                 "hours_since_service", "service_interval_hours", "drone_last_flight_date")
    def _compute_drone_kanban(self):
        for equipment in self:
            equipment.drone_last_flight_day = (
                fields.Datetime.context_timestamp(equipment, equipment.drone_last_flight_date).date()
                if equipment.drone_last_flight_date else False)
            equipment.drone_kanban_color = self._DRONE_KANBAN_COLORS.get(equipment.drone_availability, 0)
            if equipment.drone_equipment_type == "battery" and equipment.battery_cycle_limit:
                ratio = equipment.drone_flight_count / equipment.battery_cycle_limit
            elif equipment.drone_equipment_type == "drone" and equipment.service_interval_hours:
                ratio = equipment.hours_since_service / equipment.service_interval_hours
            else:
                ratio = 0.0
            equipment.drone_usage_percent = round(min(ratio, 1.0) * 100)

    def _drone_assign_project(self, project, location=None):
        """Record that the equipment is now with this job (and, optionally, at this site)."""
        for equipment in self.filtered(lambda e: e.drone_project_id != project or location):
            vals = {"drone_project_id": project.id}
            if location:
                vals["location"] = location
            equipment.sudo().write(vals)

    def action_drone_release(self):
        """Back from site: no longer with a job."""
        self.sudo().write({"drone_project_id": False, "location": _("Store")})
        return True

    @api.depends("last_service_date", "drone_flight_ids.state", "drone_flight_ids.duration_min",
                 "drone_flight_ids.takeoff_time")
    def _compute_hours_since_service(self):
        for equipment in self:
            flights = equipment.drone_flight_ids.filtered(
                lambda f: f.state == "done"
                and (not equipment.last_service_date or f.takeoff_time > equipment.last_service_date)
            )
            equipment.hours_since_service = sum(flights.mapped("duration_min")) / 60.0

    @api.constrains("serial_no", "drone_equipment_type")
    def _check_drone_serial_no(self):
        """Drones and batteries are identified by serial number, so it is required.
        Uniqueness is already enforced by the standard Maintenance app."""
        for equipment in self.filtered("drone_equipment_type"):
            if not equipment.serial_no:
                raise ValidationError(_(
                    "%s is a drone or battery, so it needs a serial number.", equipment.name))

    def _drone_open_request(self, maintenance_type):
        self.ensure_one()
        return self.env["maintenance.request"].search([
            ("equipment_id", "=", self.id),
            ("maintenance_type", "=", maintenance_type),
            ("stage_id.done", "=", False),
            ("archive", "=", False),
        ], limit=1)

    def _drone_check_service_due(self):
        """Create one preventive request per drone when its service interval is reached,
        and one request per battery when it reaches its cycle limit."""
        Request = self.env["maintenance.request"].sudo()
        for equipment in self:
            if (equipment.drone_equipment_type == "drone"
                    and equipment.service_interval_hours
                    and equipment.hours_since_service >= equipment.service_interval_hours
                    and not equipment._drone_open_request("preventive")):
                Request.create({
                    "name": _("Service due: %(drone)s (%(hours).1f flight hours since last service)",
                              drone=equipment.display_name, hours=equipment.hours_since_service),
                    "equipment_id": equipment.id,
                    "maintenance_type": "preventive",
                })
            elif (equipment.drone_equipment_type == "battery"
                    and equipment.battery_health == "retire"
                    and not equipment._drone_open_request("corrective")):
                Request.create({
                    "name": _("Retire battery %(battery)s: %(cycles)s of %(limit)s cycles used",
                              battery=equipment.display_name, cycles=equipment.drone_flight_count,
                              limit=equipment.battery_cycle_limit),
                    "equipment_id": equipment.id,
                    "maintenance_type": "corrective",
                })

    def _compute_drone_replacement_request_count(self):
        for equipment in self:
            equipment.drone_replacement_request_count = self.env["drone.equipment.request"].search_count(
                ["|", ("broken_equipment_id", "=", equipment.id), ("replacement_equipment_id", "=", equipment.id)])

    def action_view_drone_replacement_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("drone_flight_log.action_drone_equipment_request")
        action["domain"] = ["|", ("broken_equipment_id", "=", self.id), ("replacement_equipment_id", "=", self.id)]
        action["context"] = {}
        return action

    def action_view_drone_flights(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("drone_flight_log.action_drone_flight_log")
        field = "drone_id" if self.drone_equipment_type == "drone" else "battery_ids"
        action["domain"] = [(field, "in", self.ids)]
        action["context"] = {"default_drone_id": self.id} if field == "drone_id" else {}
        return action
