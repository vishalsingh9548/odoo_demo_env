from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    warranty_type = fields.Selection([
        ('performance_warranty', 'Performance Warranty'),
        ('product_warranty', 'Product Warranty'),
        ('none', 'None'),
    ], string='Warranty Type', default='performance_warranty')

    delivery_type = fields.Selection([
        ('as_per_discussion', 'As Per Discussion'),
        ('within_7_days', 'Within 7 Days'),
        ('within_15_days', 'Within 15 Days'),
        ('within_30_days', 'Within 30 Days'),
    ], string='Delivery Type', default='as_per_discussion')

    freight_type = fields.Selection([
        ('included', 'Included'),
        ('extra', 'Extra'),
        ('to_be_confirmed', 'To Be Confirmed'),
    ], string='Freight Type', default='included')

    payment_type = fields.Selection([
        ('advance_100', 'Advance 100%'),
        ('cash', 'Full Cash'),
        ('loan', 'Loan'),
        ('partial_loan', 'Partial Loan'),
    ], string='Payment Type', default='advance_100')

    cancellation_policy = fields.Selection([
        ('custom', 'Custom'),
        ('standard', 'Standard'),
        ('non_refundable', 'Non Refundable'),
    ], string='Cancellation Policy', default='custom')

    certifications_type = fields.Selection([
        ('iec_almm_bis', 'IEC / ALMM / BIS'),
        ('iec_only', 'IEC Only'),
        ('bis_only', 'BIS Only'),
    ], string='Certifications', default='iec_almm_bis')

    tolerance_type = fields.Selection([
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ('zero', 'Zero'),
    ], string='Tolerance Type', default='positive')

    advance_payment = fields.Monetary(
        string='Advance Payment',
        currency_field='currency_id',
    )
    outstanding_payment = fields.Monetary(
        string='Outstanding Payment',
        currency_field='currency_id',
        compute='_compute_solar_payment_amounts',
        store=True,
    )
    remaining_amount = fields.Monetary(
        string='Remaining Amount',
        currency_field='currency_id',
        compute='_compute_solar_payment_amounts',
        store=True,
    )

    @api.depends('amount_total', 'advance_payment')
    def _compute_solar_payment_amounts(self):
        for order in self:
            remaining = order.amount_total - order.advance_payment
            order.outstanding_payment = remaining
            order.remaining_amount = remaining

    # ---------------------------------------------------------------
    # Stage 6: Quotation Process
    # Sales Rep Provides Quotation -> Quotation Decision (Rejected/Approved)
    # -> Collect Initial Token Payment -> Confirm Payment Mode
    # -> Collect Client Documents -> Shares Deal with Registration Dept.
    # ---------------------------------------------------------------
    quotation_stage = fields.Selection([
        ('quotation_provided', 'Quotation Provided'),
        ('rejected', 'Rejected'),
        ('token_payment', 'Token Payment Collected'),
        ('payment_mode_confirmed', 'Payment Mode Confirmed'),
        ('documents_collected', 'Client Documents Collected'),
        ('shared_with_registration', 'Shared with Registration Dept'),
    ], string='Quotation Stage', default='quotation_provided', tracking=True)

    token_payment_amount = fields.Monetary(
        string='Initial Token Payment',
        currency_field='currency_id',
    )
    token_payment_date = fields.Date(string='Token Payment Date')

    client_documents_collected = fields.Boolean(string='Client Documents Collected')

    registration_id = fields.Many2one(
        'solar.registration',
        string='Registration',
        copy=False,
    )
    registration_count = fields.Integer(compute='_compute_registration_count')

    def _compute_registration_count(self):
        for order in self:
            order.registration_count = 1 if order.registration_id else 0

    def action_quotation_approve(self):
        self.write({'quotation_stage': 'token_payment'})

    def action_quotation_reject(self):
        self.write({'quotation_stage': 'rejected'})

    def action_collect_token_payment(self):
        self.ensure_one()
        self.write({
            'token_payment_date': fields.Date.context_today(self),
            'quotation_stage': 'payment_mode_confirmed',
        })

    def action_confirm_payment_mode(self):
        self.ensure_one()
        if not self.payment_type:
            raise UserError("Please select a Payment Type before confirming the payment mode.")
        self.write({'quotation_stage': 'documents_collected' if self.client_documents_collected else 'payment_mode_confirmed'})

    def action_collect_client_documents(self):
        self.ensure_one()
        self.write({
            'client_documents_collected': True,
            'quotation_stage': 'documents_collected',
        })

    def action_share_with_registration(self):
        """Hand the approved, fully-processed deal to the Registration Dept (Stage 7)."""
        self.ensure_one()
        if self.registration_id:
            return self.action_view_registration()

        design = self.env['solar.design'].search([('sale_order_id', '=', self.id)], limit=1)
        registration = self.env['solar.registration'].create({
            'sale_order_id': self.id,
            'design_id': design.id if design else False,
        })
        self.write({
            'registration_id': registration.id,
            'quotation_stage': 'shared_with_registration',
        })
        return self.action_view_registration()

    def action_view_registration(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.registration',
            'res_id': self.registration_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_combo = fields.Boolean(
        string='Is Combo',
    )
    display_hsn_code = fields.Char(
        string='HSN/SAC Code',
    )
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
    )
