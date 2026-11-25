from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        Certification = self.env["drone.certification"].sudo()
        for invoice in posted.filtered(lambda m: m.move_type == "out_invoice"):
            km_lines = invoice.invoice_line_ids.sale_line_ids.filtered("is_stringing_km")
            if not km_lines:
                continue
            certifications = Certification.search([
                ("sale_order_id", "in", km_lines.order_id.ids),
                ("state", "=", "confirmed"),
            ])
            certifications.write({"state": "invoiced", "invoice_id": invoice.id})
        return posted
