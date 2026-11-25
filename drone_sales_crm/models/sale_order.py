import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    line_name = fields.Char(string="Line Name", tracking=True)
    voltage_kv = fields.Integer(string="Voltage (kV)")
    site_location = fields.Char(string="Site / Route")
    span_count = fields.Integer(related="opportunity_id.span_count", string="Spans")
    total_km = fields.Float(
        related="opportunity_id.total_km", string="Surveyed Length (km)", digits=(16, 3)
    )
    certification_ids = fields.One2many(
        "drone.certification", "sale_order_id", string="Certifications"
    )
    certification_count = fields.Integer(compute="_compute_certification_count")

    @api.depends("certification_ids")
    def _compute_certification_count(self):
        for order in self:
            order.certification_count = len(order.certification_ids)

    @api.onchange("opportunity_id")
    def _onchange_opportunity_id_drone(self):
        lead = self.opportunity_id
        if lead:
            self.line_name = self.line_name or lead.line_name
            self.voltage_kv = self.voltage_kv or lead.voltage_kv
            self.site_location = self.site_location or lead.site_location

    def _action_confirm(self):
        # sale_project creates the project during super(); spans are added after it.
        result = super()._action_confirm()
        self._drone_create_span_tasks()
        return result

    def _drone_get_job_project(self):
        """The project generated from this order (or set on it), if any."""
        self.ensure_one()
        return self.order_line.project_id[:1] or self.project_id

    def _drone_create_span_tasks(self):
        """Create one span task per survey span. Safe to call more than once."""
        Task = self.env["project.task"].sudo()
        for order in self:
            spans = order.opportunity_id.survey_span_ids
            if not spans:
                continue
            project = order._drone_get_job_project()
            if not project:
                _logger.warning(
                    "Order %s has survey spans but no project; span tasks not created.",
                    order.name,
                )
                continue
            existing = Task.search([
                ("project_id", "=", project.id),
                ("survey_span_id", "in", spans.ids),
            ]).survey_span_id
            new_spans = spans - existing
            if not new_spans:
                continue
            Task.create([{
                "name": _(
                    "Span %(no)s: %(tower_from)s – %(tower_to)s",
                    no=span.name,
                    tower_from=span.tower_from or "?",
                    tower_to=span.tower_to or "?",
                ),
                "project_id": project.id,
                "partner_id": order.partner_id.id,
                "is_span": True,
                "tower_from": span.tower_from,
                "tower_to": span.tower_to,
                "span_length_m": span.length_m,
                "crossing_type": span.crossing_type,
                "survey_span_id": span.id,
                "sequence": span.sequence,
            } for span in new_spans])

    def action_view_certifications(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "drone_sales_crm.action_drone_certification"
        )
        action["domain"] = [("sale_order_id", "=", self.id)]
        action["context"] = {"default_sale_order_id": self.id}
        return action
