from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    drone_certification_ids = fields.One2many(
        "drone.certification", "project_id", string="Client Certifications"
    )
    drone_certification_count = fields.Integer(
        compute="_compute_drone_certification_count", string="Certifications"
    )

    @api.depends("drone_certification_ids")
    def _compute_drone_certification_count(self):
        for project in self:
            project.drone_certification_count = len(project.drone_certification_ids)

    def action_view_drone_certifications(self):
        """Certifications of the orders billed through this job."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "drone_sales_crm.action_drone_certification"
        )
        action["domain"] = [("project_id", "=", self.id)]
        order = self.drone_certification_ids.sale_order_id[:1] or self.reinvoiced_sale_order_id
        action["context"] = {"default_sale_order_id": order.id} if order else {}
        return action
