from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaleOrderPayment(models.Model):
    """Advance / outstanding payment and LC interest on the sale order, and the pending amount."""
    _inherit = 'sale.order'

    advance_payment = fields.Monetary(tracking=True)
    outstanding_payment = fields.Monetary(tracking=True)
    lc_amount = fields.Float(string='LC Interest (%)', digits=(16, 4), tracking=True)
    lc_total_amount = fields.Monetary(string='LC Interest Amount', compute='_compute_lc_total', store=True)
    lc_total_label = fields.Char(compute='_compute_lc_total')
    remaining_amount = fields.Monetary(string='Pending Amount', compute='_compute_remaining_amount')

    @api.depends('order_line.price_subtotal', 'lc_amount')
    def _compute_lc_total(self):
        """LC interest = percentage of the untaxed total (sum of line subtotals)."""
        for order in self:
            base = sum(order.order_line.mapped('price_subtotal'))
            order.lc_total_amount = base * order.lc_amount / 100.0
            order.lc_total_label = _('Interest @ %s %% of the total LC amount', order.lc_amount) if order.lc_amount else False

    @api.depends('amount_total', 'advance_payment', 'outstanding_payment')
    def _compute_remaining_amount(self):
        """Pending = total - advance + outstanding (LC interest is already inside the total)."""
        for order in self:
            order.remaining_amount = order.amount_total - order.advance_payment + order.outstanding_payment

    @api.depends('lc_amount')
    def _compute_amounts(self):
        """Standard totals, then add the LC interest into the grand total when one is set."""
        super()._compute_amounts()
        for order in self:
            if order.lc_amount:
                order.amount_total += order.amount_untaxed * order.lc_amount / 100.0

    @api.constrains('amount_total', 'advance_payment', 'outstanding_payment')
    def _check_not_negative(self):
        """The pending amount must never go below zero."""
        for order in self:
            if order.advance_payment or order.outstanding_payment:
                if order.amount_total - order.advance_payment + order.outstanding_payment < 0:
                    raise ValidationError(_('Total amount cannot be negative.'))


class AccountMove(models.Model):
    """Gate number on vendor bills / invoices."""
    _inherit = 'account.move'

    gate_number = fields.Char(string='Gate No.', copy=False)


class ResPartner(models.Model):
    """Customer / vendor classification fields are shown on the partner form (see the view)."""
    _inherit = 'res.partner'


class ProductProduct(models.Model):
    """Same product-creation gate as on the template (variants can be made directly too)."""
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        """Block product creation for switched-on users who lack the right (administrators are exempt)."""
        user = self.env.user
        if (not self.env.su and not self.env.context.get('create_product_product')
                and self.env['advmfg.switch'].is_active()
                and not user.has_group('advance_manufacturing.group_advmfg_manager')
                and not user.has_group('base.group_system')):
            from odoo.exceptions import AccessError
            raise AccessError(_('You do not have permission to create products. Please contact your administrator.'))
        return super().create(vals_list)
