from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

BREAKDOWN_TYPES = [
    ("crash", "Crash"),
    ("damage", "Damaged"),
    ("malfunction", "Malfunction"),
    ("lost", "Lost"),
]


class DroneBreakdownWizard(models.TransientModel):
    """Report equipment that broke on a flight: take it out of service, open a repair
    request and, if needed, request a replacement for the site."""

    _name = "drone.breakdown.wizard"
    _description = "Report Equipment Breakdown"

    flight_id = fields.Many2one("drone.flight.log", required=True, readonly=True)
    flight_equipment_ids = fields.Many2many(
        "maintenance.equipment", compute="_compute_flight_equipment", string="Equipment on the Flight",
    )
    equipment_ids = fields.Many2many(
        "maintenance.equipment", string="Broken Equipment", required=True,
        domain="[('id', 'in', flight_equipment_ids)]",
    )
    breakdown_type = fields.Selection(BREAKDOWN_TYPES, string="What Happened", required=True, default="malfunction")
    description = fields.Text(string="Details", required=True)
    request_replacement = fields.Boolean(string="Request Replacement", default=True)
    required_date = fields.Date(
        string="Needed On Site By", default=lambda self: fields.Date.context_today(self) + timedelta(days=1),
    )
    site_location = fields.Char(string="Send To (Site)")
    abort_flight = fields.Boolean(
        string="Mark Flight as Aborted", default=True,
        help="Only for flights not confirmed yet: the result becomes 'Aborted' with the breakdown as reason.",
    )
    flight_state = fields.Selection(related="flight_id.state")

    @api.depends("flight_id")
    def _compute_flight_equipment(self):
        for wizard in self:
            wizard.flight_equipment_ids = wizard.flight_id.drone_id | wizard.flight_id.battery_ids

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        flight = self.env["drone.flight.log"].browse(values.get("flight_id") or self.env.context.get("active_id"))
        if flight:
            values["flight_id"] = flight.id
            order = flight.project_id.reinvoiced_sale_order_id
            values.setdefault("site_location", order.site_location or flight.project_id.name)
        return values

    def action_confirm(self):
        self.ensure_one()
        flight = self.flight_id
        if not self.equipment_ids:
            raise UserError(_("Select the equipment that broke."))
        if self.request_replacement and not self.site_location:
            raise UserError(_("Give the site the replacement must be sent to."))
        type_label = dict(BREAKDOWN_TYPES)[self.breakdown_type]
        repair_requests = self.env["maintenance.request"]
        replacement_requests = self.env["drone.equipment.request"]
        for equipment in self.equipment_ids:
            equipment.sudo().write({"drone_operational_state": "broken", "drone_broken_flight_id": flight.id})
            repair = self.env["maintenance.request"].sudo().create({
                "name": _("%(type)s on %(flight)s: %(item)s",
                          type=type_label, flight=flight.name, item=equipment.display_name),
                "equipment_id": equipment.id,
                "maintenance_type": "corrective",
                "priority": "3",
                "drone_flight_id": flight.id,
                "description": "<p>%s</p>" % (self.description or "").replace("\n", "<br/>"),
            })
            repair_requests |= repair
            if self.request_replacement:
                replacement_requests |= self.env["drone.equipment.request"].create({
                    "flight_id": flight.id,
                    "task_id": flight.task_id.id,
                    "project_id": flight.project_id.id,
                    "broken_equipment_id": equipment.id,
                    "equipment_type": equipment.drone_equipment_type,
                    "maintenance_request_id": repair.id,
                    "reason": "%s: %s" % (type_label, self.description),
                    "required_date": self.required_date,
                    "site_location": self.site_location,
                })
        if self.abort_flight and flight.state == "draft":
            flight.write({
                "result": "aborted",
                "abort_reason": _("Equipment breakdown (%(type)s): %(items)s",
                                  type=type_label.lower(), items=", ".join(self.equipment_ids.mapped("display_name"))),
            })
        flight.message_post(body=_(
            "Breakdown reported (%(type)s): %(items)s. Repair requests: %(repairs)s.%(replacements)s",
            type=type_label.lower(),
            items=", ".join(self.equipment_ids.mapped("display_name")),
            repairs=", ".join(repair_requests.mapped("name")),
            replacements=(_(" Replacement requests: %s.", ", ".join(replacement_requests.mapped("name")))
                          if replacement_requests else ""),
        ))
        if replacement_requests:
            return flight.action_view_equipment_requests()
        return {"type": "ir.actions.act_window_close"}
