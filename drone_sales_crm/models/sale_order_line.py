from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    is_stringing_km = fields.Boolean(related="product_id.is_stringing_km")

    def write(self, vals):
        if (
            "qty_delivered" in vals
            and not self.env.context.get("drone_from_certification")
            and self.filtered("is_stringing_km")
        ):
            raise UserError(_(
                "The delivered km on this line comes from client certifications. "
                "Record a certification instead of editing the quantity."))
        return super().write(vals)

    def _timesheet_create_project(self):
        # sale_project appends " - <template name>" to the name after
        # _timesheet_create_project_prepare_values(), so the name is set once the project exists.
        project = super()._timesheet_create_project()
        if self.is_stringing_km:
            # Only drone stringing jobs; other orders keep Odoo's standard project name.
            project.name = self._drone_project_name()
        return project

    def _drone_project_name(self):
        """'<order> - <partner> - <line name>'; the line name is left out when empty."""
        self.ensure_one()
        order = self.order_id
        parts = [order.name, order.partner_id.name, order.line_name]
        return " - ".join(part for part in parts if part)
