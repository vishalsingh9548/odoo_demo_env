from odoo import api, models, _
from odoo.exceptions import UserError


class ReportCustomPurchaseOrder(models.AbstractModel):
    """Data for the Custom Purchase Order PDF; refuses to print before the order is confirmed."""
    _name = 'report.advance_manufacturing.report_custom_purchase_order'
    _description = 'Custom Purchase Order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Only confirmed (or done) purchase orders can be printed."""
        docs = self.env['purchase.order'].browse(docids)
        for po in docs:
            if po.state not in ('purchase', 'done'):
                raise UserError(_('Report Not Available - Purchase Order %s must be in Purchase Order (confirmed) state to print.', po.name))
        return {'doc_ids': docids, 'doc_model': 'purchase.order', 'docs': docs}


class ReportCustomSaleOrder(models.AbstractModel):
    """Data for the Custom Sale Order PDF; confirmed orders only; combo lines merged into one row."""
    _name = 'report.advance_manufacturing.report_custom_sale_order'
    _description = 'Custom Sale Order Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Only confirmed (or done) sale orders can be printed."""
        docs = self.env['sale.order'].browse(docids)
        for so in docs:
            if so.state not in ('sale', 'done'):
                raise UserError(_('Report Not Available - Sale Order %s must be in Sale Order (confirmed) state to print.', so.name))
        return {'doc_ids': docids, 'doc_model': 'sale.order', 'docs': docs, 'rows': self._rows,
                'title': _('Sale Order')}

    @staticmethod
    def _rows(order):
        """Turn the order lines into print rows: consecutive combo lines become one 'Solar Power Generating System' row."""
        rows, combo = [], []

        def flush():
            if combo:
                rows.append({
                    'name': 'Solar Power Generating System (%s)' % ' + '.join(l.product_id.display_name for l in combo),
                    'hsn': combo[0].display_hsn_code, 'qty': 1, 'uom': '',
                    'price': sum(l.price_subtotal for l in combo),
                    'tax': ', '.join(sorted({t.name for l in combo for t in l.tax_id})),
                    'amount': sum(l.price_subtotal for l in combo)})
                combo.clear()
        for line in order.order_line:
            if line.display_type:
                continue
            if line.is_combo:
                combo.append(line)
                continue
            flush()
            rows.append({'name': line.name, 'hsn': line.display_hsn_code, 'qty': line.product_uom_qty,
                         'uom': line.product_uom.name, 'price': line.price_unit,
                         'tax': ', '.join(line.tax_id.mapped('name')), 'amount': line.price_subtotal})
        flush()
        return rows


class ReportCustomQuotation(models.AbstractModel):
    """Same as the sale order report but as a Proforma Invoice and printable in every state."""
    _name = 'report.advance_manufacturing.report_custom_quotation'
    _description = 'Custom Quotation Report'
    _inherit = 'report.advance_manufacturing.report_custom_sale_order'

    @api.model
    def _get_report_values(self, docids, data=None):
        """No state guard for quotations."""
        docs = self.env['sale.order'].browse(docids)
        return {'doc_ids': docids, 'doc_model': 'sale.order', 'docs': docs, 'rows': self._rows,
                'title': _('Proforma Invoice')}
