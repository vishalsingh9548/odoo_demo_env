from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        invoices = posted.filtered(lambda m: m.move_type == 'out_invoice')
        orders = invoices.invoice_line_ids.sale_line_ids.order_id
        if orders:
            certificates = self.env['ug.epr.certificate'].sudo().search([
                ('sale_order_id', 'in', orders.ids), ('state', '=', 'listed'),
            ])
            certificates._ug_mark_sold()
        return posted
