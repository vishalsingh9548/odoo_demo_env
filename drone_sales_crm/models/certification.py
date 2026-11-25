from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class DroneCertification(models.Model):
    """Km certified by the client's engineer. Drives the invoiceable km on the order."""

    _name = "drone.certification"
    _description = "Client Certification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True,
        default=lambda self: _("New"),
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Sales Order", required=True, index=True, tracking=True,
        domain="[('state', '=', 'sale')]",
    )
    partner_id = fields.Many2one(related="sale_order_id.partner_id", store=True)
    company_id = fields.Many2one(related="sale_order_id.company_id", store=True)
    project_id = fields.Many2one(
        "project.project", string="Job", compute="_compute_project_id", store=True
    )
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    certified_km = fields.Float(
        string="Certified (km)", digits=(16, 3), required=True, tracking=True
    )
    client_engineer = fields.Char(string="Client Engineer")
    attachment_ids = fields.Many2many(
        "ir.attachment", string="Signed Sheet",
        help="Attach the certification signed by the client's engineer.",
    )
    note = fields.Text()
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("invoiced", "Invoiced")],
        default="draft", required=True, tracking=True, copy=False,
    )
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True, copy=False)

    _sql_constraints = [
        ("certified_km_positive", "CHECK(certified_km > 0)",
         "The certified km must be greater than zero."),
    ]

    @api.depends("sale_order_id")
    def _compute_project_id(self):
        for cert in self:
            order = cert.sale_order_id
            cert.project_id = order._drone_get_job_project() if order else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "drone.certification") or _("New")
        return super().create(vals_list)

    def _get_km_line(self):
        self.ensure_one()
        line = self.sale_order_id.order_line.filtered("is_stringing_km")[:1]
        if not line:
            raise UserError(_(
                "Order %s has no line billed per certified km.", self.sale_order_id.name))
        if line.qty_delivered_method != "manual":
            raise UserError(_(
                "The product '%s' must use manually delivered quantities to be billed per "
                "certified km.", line.product_id.display_name))
        return line

    def action_confirm(self):
        for cert in self.filtered(lambda c: c.state == "draft"):
            line = cert._get_km_line()
            already = cert.sale_order_id.certification_ids.filtered(
                lambda c: c.state in ("confirmed", "invoiced") and c != cert
            )
            total = sum(already.mapped("certified_km")) + cert.certified_km
            if float_compare(
                total, line.product_uom_qty, precision_rounding=line.product_uom.rounding
            ) > 0:
                raise UserError(_(
                    "Certified km would reach %(total)s, more than the %(ordered)s km on the "
                    "order. Update the order quantity first if the scope has grown.",
                    total=round(total, 3), ordered=line.product_uom_qty))
            cert.state = "confirmed"
        self._sync_delivered_qty()
        return True

    def action_reset_to_draft(self):
        if self.filtered(lambda c: c.state == "invoiced"):
            raise UserError(_("An invoiced certification cannot be reset to draft."))
        self.write({"state": "draft"})
        self._sync_delivered_qty()
        return True

    def _sync_delivered_qty(self):
        """Delivered km on the order line = confirmed + invoiced certifications."""
        for order in self.sale_order_id:
            line = order.order_line.filtered("is_stringing_km")[:1]
            if not line:
                continue
            total = sum(order.certification_ids.filtered(
                lambda c: c.state in ("confirmed", "invoiced")).mapped("certified_km"))
            line.sudo().with_context(drone_from_certification=True).write(
                {"qty_delivered": total})

    def _drone_report_values(self):
        """Figures printed on the certification: km before / with this certificate, balance,
        and the value of the work at the order's rate."""
        self.ensure_one()
        order = self.sale_order_id
        line = order.order_line.filtered("is_stringing_km")[:1]
        counted = order.certification_ids.filtered(
            lambda c: c.state in ("confirmed", "invoiced") and c != self)
        previous = counted.filtered(lambda c: (c.date, c.id) < (self.date, self.id))
        previous_km = sum(previous.mapped("certified_km"))
        cumulative_km = previous_km + self.certified_km
        ordered_km = line.product_uom_qty if line else 0.0
        rate = line.price_unit * (1 - (line.discount or 0.0) / 100.0) if line else 0.0
        return {
            "ordered_km": ordered_km,
            "previous_km": previous_km,
            "cumulative_km": cumulative_km,
            "balance_km": max(ordered_km - cumulative_km, 0.0),
            "rate": rate,
            "amount": rate * self.certified_km,
            "currency": order.currency_id,
            "progress_pct": min(100.0, 100.0 * cumulative_km / ordered_km) if ordered_km else 0.0,
            "state_label": dict(self._fields["state"]._description_selection(self.env)).get(self.state, ""),
        }

    def action_print_certification(self):
        return self.env.ref("drone_sales_crm.action_report_drone_certification").report_action(self)

    def unlink(self):
        if self.filtered(lambda c: c.state != "draft"):
            raise UserError(_("Only draft certifications can be deleted."))
        return super().unlink()
