from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .maintenance_equipment import DRONE_EQUIPMENT_TYPES


class DroneEquipmentRequest(models.Model):
    """Request to send a working drone or battery to site, to replace one that broke."""

    _name = "drone.equipment.request"
    _description = "Equipment Replacement Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default=lambda self: _("New"),
    )
    state = fields.Selection(
        [
            ("requested", "Requested"),
            ("approved", "Approved"),
            ("dispatched", "Dispatched"),
            ("received", "Received"),
            ("cancel", "Cancelled"),
        ],
        default="requested", required=True, tracking=True, copy=False,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    # --- Origin ------------------------------------------------------------------------------------
    flight_id = fields.Many2one("drone.flight.log", string="Flight", index=True, tracking=True)
    task_id = fields.Many2one("project.task", string="Span")
    project_id = fields.Many2one("project.project", string="Job", index=True)
    maintenance_request_id = fields.Many2one(
        "maintenance.request", string="Repair Request", readonly=True, copy=False,
    )
    broken_equipment_id = fields.Many2one(
        "maintenance.equipment", string="Broken Equipment", tracking=True,
        domain="[('drone_equipment_type', '!=', False)]",
    )
    equipment_type = fields.Selection(DRONE_EQUIPMENT_TYPES, string="Type Needed", required=True)
    reason = fields.Text(string="What Happened")

    # --- What and where ------------------------------------------------------------------------------
    requested_by_id = fields.Many2one(
        "res.users", string="Requested By", required=True, default=lambda self: self.env.user,
    )
    required_date = fields.Date(
        string="Needed On Site By", required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=1),
    )
    site_location = fields.Char(string="Send To (Site)", required=True)
    replacement_equipment_id = fields.Many2one(
        "maintenance.equipment", string="Replacement", tracking=True,
        domain="[('drone_equipment_type', '=', equipment_type), ('drone_operational_state', '=', 'ok'),"
               " ('scrap_date', '=', False), ('id', '!=', broken_equipment_id)]",
    )
    replacement_serial_no = fields.Char(related="replacement_equipment_id.serial_no", string="Replacement Serial No.")
    dispatch_date = fields.Datetime(readonly=True, copy=False)
    receive_date = fields.Datetime(readonly=True, copy=False)
    note = fields.Text(string="Dispatch Notes")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("drone.equipment.request") or _("New")
        requests = super().create(vals_list)
        requests._schedule_dispatch_activity()
        return requests

    def _schedule_dispatch_activity(self):
        """A to-do for the person responsible for this kind of equipment."""
        for request in self:
            category = request.broken_equipment_id.category_id or self.env.ref(
                "drone_flight_log.equipment_category_%s" % request.equipment_type, raise_if_not_found=False)
            user = category.technician_user_id if category else False
            request.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=request.required_date,
                summary=_("Send a replacement %(type)s to %(site)s",
                          type=dict(DRONE_EQUIPMENT_TYPES)[request.equipment_type], site=request.site_location),
                user_id=(user or self.env.user).id,
            )

    @api.constrains("replacement_equipment_id", "equipment_type", "broken_equipment_id")
    def _check_replacement(self):
        for request in self.filtered("replacement_equipment_id"):
            replacement = request.replacement_equipment_id
            if replacement.drone_equipment_type != request.equipment_type:
                raise ValidationError(_("%(item)s is not a %(type)s.", item=replacement.display_name,
                                        type=dict(DRONE_EQUIPMENT_TYPES)[request.equipment_type]))
            if replacement == request.broken_equipment_id:
                raise ValidationError(_("The replacement cannot be the broken equipment itself."))

    # --- Workflow --------------------------------------------------------------------------------------

    def action_approve(self):
        self.filtered(lambda r: r.state == "requested").write({"state": "approved"})
        return True

    def action_dispatch(self):
        for request in self:
            if request.state not in ("requested", "approved"):
                continue
            replacement = request.replacement_equipment_id
            if not replacement:
                raise UserError(_("%s: choose the replacement equipment to send.", request.name))
            if replacement.drone_operational_state != "ok" or replacement.scrap_date:
                raise UserError(_("%s is not operational and cannot be sent.", replacement.display_name))
            other = self.search([
                ("id", "!=", request.id),
                ("replacement_equipment_id", "=", replacement.id),
                ("state", "=", "dispatched"),
            ], limit=1)
            if other:
                raise UserError(_("%(item)s is already on its way under %(other)s.",
                                  item=replacement.display_name, other=other.name))
            if request.project_id:
                replacement._drone_assign_project(request.project_id, location=request.site_location)
            else:
                replacement.sudo().location = request.site_location
            request.write({"state": "dispatched", "dispatch_date": fields.Datetime.now()})
        return True

    def action_receive(self):
        for request in self.filtered(lambda r: r.state == "dispatched"):
            request.write({"state": "received", "receive_date": fields.Datetime.now()})
            request.activity_feedback(["mail.mail_activity_data_todo"])
            if request.flight_id:
                request.flight_id.message_post(body=_(
                    "Replacement %(item)s received on site (%(request)s).",
                    item=request.replacement_equipment_id.display_name, request=request.name))
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state != "received").write({"state": "cancel"})
        self.activity_unlink(["mail.mail_activity_data_todo"])
        return True

    def action_reset(self):
        self.filtered(lambda r: r.state == "cancel").write({"state": "requested"})
        return True

    def action_new_flight(self):
        """Draft flight on the same span, with the replacement in place of the broken item."""
        self.ensure_one()
        flight = self.flight_id
        if not flight or self.state != "received":
            raise UserError(_("A new flight can be prepared once the replacement is received."))
        drone = flight.drone_id
        batteries = flight.battery_ids
        broken, replacement = self.broken_equipment_id, self.replacement_equipment_id
        if broken == drone:
            drone = replacement
        elif broken in batteries:
            batteries = (batteries - broken) | replacement
        now = fields.Datetime.now()
        new_flight = self.env["drone.flight.log"].create({
            "task_id": flight.task_id.id,
            "drone_id": drone.id,
            "battery_ids": [(6, 0, batteries.ids)],
            "pilot_id": flight.pilot_id.id,
            "takeoff_time": now,
            "note": _("Re-flight after %(request)s (replaced %(item)s).",
                      request=self.name, item=broken.display_name),
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "drone.flight.log",
            "res_id": new_flight.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }
