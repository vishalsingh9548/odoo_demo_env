from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

FLIGHT_RESULTS = [
    ("success", "Rope passed"),
    ("retry", "Retry needed"),
    ("aborted", "Aborted"),
]

WEATHER = [
    ("clear", "Clear"),
    ("cloudy", "Cloudy"),
    ("windy", "Windy"),
    ("rain", "Rain"),
    ("fog", "Fog / low visibility"),
]


class DroneFlightLog(models.Model):
    """One drone flight on a span: which drone, pilot and batteries, and how it went."""

    _name = "drone.flight.log"
    _description = "Drone Flight Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "takeoff_time desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default=lambda self: _("New"),
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")],
        default="draft", required=True, tracking=True, copy=False,
    )
    company_id = fields.Many2one(
        "res.company", required=True, compute="_compute_company_id", store=True, readonly=False,
        precompute=True,
        help="The span task's company; the current company when the task has none.",
    )

    @api.depends("task_id")
    def _compute_company_id(self):
        for flight in self:
            flight.company_id = flight.task_id.company_id or flight.company_id or self.env.company

    # --- Where -------------------------------------------------------------------------------
    task_id = fields.Many2one(
        "project.task", string="Span", required=True, index=True, tracking=True,
        domain="[('is_span', '=', True)]",
        help="The span task this flight was for.",
    )
    project_id = fields.Many2one(related="task_id.project_id", store=True, string="Job")
    partner_id = fields.Many2one(related="task_id.partner_id", store=True, string="Customer")
    tower_from = fields.Char(related="task_id.tower_from")
    tower_to = fields.Char(related="task_id.tower_to")
    crossing_type = fields.Selection(related="task_id.crossing_type")

    # --- Who and what --------------------------------------------------------------------------
    drone_id = fields.Many2one(
        "maintenance.equipment", string="Drone", required=True, tracking=True,
        domain="[('drone_equipment_type', '=', 'drone'), ('drone_operational_state', '=', 'ok'), ('scrap_date', '=', False)]",
    )
    drone_serial_no = fields.Char(related="drone_id.serial_no", string="Drone Serial No.")
    battery_ids = fields.Many2many(
        "maintenance.equipment", "drone_flight_log_battery_rel", "flight_id", "battery_id",
        string="Batteries",
        domain="[('drone_equipment_type', '=', 'battery'), ('drone_operational_state', '=', 'ok'), ('scrap_date', '=', False)]",
        help="Batteries used on this flight, by serial number. Each completed flight counts "
             "as one charge cycle for every battery on it.",
    )
    pilot_id = fields.Many2one(
        "hr.employee", string="Pilot", required=True, tracking=True,
        default=lambda self: self.env.user.employee_id,
    )

    # --- When and how ----------------------------------------------------------------------------
    takeoff_time = fields.Datetime(string="Take-off", required=True, default=fields.Datetime.now)
    landing_time = fields.Datetime(string="Landing", help="Required to confirm the flight.")
    duration_min = fields.Float(
        string="Flight Time (min)", compute="_compute_duration", store=True, digits=(16, 1),
    )
    result = fields.Selection(FLIGHT_RESULTS, required=True, default="success", tracking=True)
    abort_reason = fields.Char(string="Reason")
    weather = fields.Selection(WEATHER, default="clear")
    wind_kmh = fields.Float(string="Wind (km/h)", digits=(16, 1))
    note = fields.Text(string="Remarks")

    equipment_request_ids = fields.One2many("drone.equipment.request", "flight_id", string="Replacement Requests")
    equipment_request_count = fields.Integer(compute="_compute_breakdown_counts")
    repair_request_ids = fields.One2many("maintenance.request", "drone_flight_id", string="Repair Requests")
    repair_request_count = fields.Integer(compute="_compute_breakdown_counts")

    _sql_constraints = [
        ("wind_kmh_positive", "CHECK(wind_kmh >= 0)", "Wind speed cannot be negative."),
    ]

    @api.depends("takeoff_time", "landing_time")
    def _compute_duration(self):
        for flight in self:
            if flight.takeoff_time and flight.landing_time and flight.landing_time > flight.takeoff_time:
                flight.duration_min = (flight.landing_time - flight.takeoff_time).total_seconds() / 60.0
            else:
                flight.duration_min = 0.0

    @api.depends("equipment_request_ids", "repair_request_ids")
    def _compute_breakdown_counts(self):
        for flight in self:
            flight.equipment_request_count = len(flight.equipment_request_ids)
            flight.repair_request_count = len(flight.repair_request_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("drone.flight.log") or _("New")
        return super().create(vals_list)

    # --- Checks ------------------------------------------------------------------------------------

    @api.constrains("takeoff_time", "landing_time")
    def _check_times(self):
        for flight in self:
            if flight.landing_time and flight.takeoff_time and flight.landing_time <= flight.takeoff_time:
                raise ValidationError(_("%s: landing must be after take-off.", flight.name))

    @api.constrains("drone_id", "battery_ids", "takeoff_time", "landing_time", "state")
    def _check_no_overlap(self):
        """The same drone or battery cannot be on two flights at the same time."""
        for flight in self.filtered(lambda f: f.state != "cancel" and f.takeoff_time and f.landing_time):
            overlapping = self.search([
                ("id", "!=", flight.id),
                ("state", "!=", "cancel"),
                ("takeoff_time", "<", flight.landing_time),
                ("landing_time", ">", flight.takeoff_time),
                ("landing_time", "!=", False),
                "|", ("drone_id", "=", flight.drone_id.id), ("battery_ids", "in", flight.battery_ids.ids),
            ], limit=1)
            if overlapping:
                shared = (overlapping.drone_id & flight.drone_id) | (overlapping.battery_ids & flight.battery_ids)
                raise ValidationError(_(
                    "%(equipment)s is already on flight %(other)s at that time.",
                    equipment=", ".join(shared.mapped("display_name")), other=overlapping.name))

    @api.constrains("drone_id", "battery_ids")
    def _check_equipment_types(self):
        for flight in self:
            if flight.drone_id.drone_equipment_type != "drone":
                raise ValidationError(_("%s is not a drone.", flight.drone_id.display_name))
            not_batteries = flight.battery_ids.filtered(lambda b: b.drone_equipment_type != "battery")
            if not_batteries:
                raise ValidationError(_(
                    "Not drone batteries: %s", ", ".join(not_batteries.mapped("display_name"))))

    def _check_ready_to_confirm(self):
        for flight in self:
            if not flight.landing_time:
                raise UserError(_("%s: enter the landing time (or tap 'Landed now').", flight.name))
            if not flight.battery_ids:
                raise UserError(_("%s: add the batteries used on this flight.", flight.name))
            if flight.result != "success" and not flight.abort_reason:
                raise UserError(_("%s: give the reason the flight did not pass the rope.", flight.name))
            scrapped = (flight.drone_id | flight.battery_ids).filtered("scrap_date")
            if scrapped:
                raise UserError(_(
                    "%(flight)s: scrapped equipment cannot fly: %(items)s",
                    flight=flight.name, items=", ".join(scrapped.mapped("display_name"))))
            # Equipment that broke on another flight is out of service until repaired.
            broken = (flight.drone_id | flight.battery_ids).filtered(
                lambda e: e.drone_operational_state == "broken" and e.drone_broken_flight_id != flight)
            if broken:
                raise UserError(_(
                    "%(flight)s: broken equipment cannot fly until it is repaired: %(items)s",
                    flight=flight.name, items=", ".join(broken.mapped("display_name"))))
            retired = flight.battery_ids.filtered(lambda b: b.battery_health == "retire")
            if retired:
                raise UserError(_(
                    "%(flight)s: these batteries have reached their cycle limit and must be "
                    "retired: %(items)s",
                    flight=flight.name, items=", ".join(retired.mapped("display_name"))))

    # --- Actions -----------------------------------------------------------------------------------

    def action_done(self):
        flights = self.filtered(lambda f: f.state == "draft")
        flights._check_ready_to_confirm()
        flights.write({"state": "done"})
        for flight in flights.filtered("project_id"):
            # The drone and batteries that flew are with this job now.
            (flight.drone_id | flight.battery_ids)._drone_assign_project(flight.project_id)
        flights._move_spans_to_strung()
        (flights.drone_id | flights.battery_ids)._drone_check_service_due()
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})
        return True

    def action_draft(self):
        self.filtered(lambda f: f.state == "cancel").write({"state": "draft"})
        return True

    def action_takeoff_now(self):
        """One tap on site: the drone has taken off."""
        self.filtered(lambda f: f.state == "draft").write(
            {"takeoff_time": fields.Datetime.now(), "landing_time": False})
        return True

    def action_landed_now(self):
        """One tap on site: the drone has landed."""
        now = fields.Datetime.now()
        for flight in self.filtered(lambda f: f.state == "draft"):
            if flight.takeoff_time and flight.takeoff_time >= now:
                raise UserError(_("%s: take-off is not before now; check the take-off time.", flight.name))
            flight.landing_time = now
        return True

    def action_report_breakdown(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Report Equipment Breakdown"),
            "res_model": "drone.breakdown.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_flight_id": self.id},
        }

    def action_view_equipment_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("drone_flight_log.action_drone_equipment_request")
        action["domain"] = [("flight_id", "=", self.id)]
        action["context"] = {}
        if len(self.equipment_request_ids) == 1:
            action.update({"res_id": self.equipment_request_ids.id, "view_mode": "form",
                           "views": [(False, "form")]})
        return action

    def action_view_repair_requests(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("maintenance.hr_equipment_request_action")
        action["domain"] = [("drone_flight_id", "=", self.id)]
        action["context"] = {}
        return action

    def _move_spans_to_strung(self):
        """A flight that passed the rope moves its span task to the 'Strung' stage,
        unless the task is already further along (e.g. 'Certified')."""
        strung = self.env.ref("drone_sales_crm.task_type_strung", raise_if_not_found=False)
        if not strung:
            return
        for flight in self.filtered(lambda f: f.result == "success"):
            task = flight.task_id
            if strung in task.project_id.type_ids and task.stage_id.sequence < strung.sequence:
                task.sudo().stage_id = strung

    def unlink(self):
        if self.filtered(lambda f: f.state == "done"):
            raise UserError(_("A completed flight cannot be deleted. Cancel it instead."))
        return super().unlink()
