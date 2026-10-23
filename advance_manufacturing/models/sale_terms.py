from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AdvmfgBankAccount(models.Model):
    """A company bank account whose details are printed on sale orders."""
    _name = 'advmfg.bank.account'
    _description = 'Bank Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'account_number'

    bank_name = fields.Char(required=True, tracking=True)
    account_name = fields.Char(tracking=True)
    account_number = fields.Char(required=True, tracking=True)
    branch_name = fields.Char(tracking=True)
    ifsc_code = fields.Char(string='IFSC Code', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    _sql_constraints = [
        ('unique_account_per_company', 'unique(company_id, account_number)',
         'An account with this number already exists for this company.'),
    ]

    @api.constrains('account_number', 'company_id', 'active')
    def _check_account_uniqueness(self):
        """Only one active account with a given number per company."""
        for rec in self.filtered('active'):
            other = self.search([('company_id', '=', rec.company_id.id), ('account_number', '=', rec.account_number),
                                 ('active', '=', True), ('id', '!=', rec.id)], limit=1)
            if other:
                raise UserError(_("Account number '%s' is already configured for company '%s'. "
                                  "Only one active account per company is allowed.",
                                  rec.account_number, rec.company_id.name))

    @api.model
    def get_default_bank_for_company(self):
        """The first active bank account of the current company."""
        return self.search([('company_id', '=', self.env.company.id), ('active', '=', True)], limit=1)

    @api.depends('account_number', 'bank_name')
    def _compute_display_name(self):
        """Show 'number - bank'."""
        for rec in self:
            rec.display_name = '%s - %s' % (rec.account_number or '', rec.bank_name or '')

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """Search by account number or bank name."""
        domain = list(domain or [])
        if name:
            domain = ['|', ('account_number', operator, name), ('bank_name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)


class ResPartner(models.Model):
    """Customers/contacts get a GST number; delivery/invoice contacts show their address in the name."""
    _inherit = 'res.partner'

    gst_number = fields.Char(string='GST Number')

    @api.depends('complete_name', 'email', 'vat', 'state_id', 'country_id', 'commercial_company_name')
    @api.depends_context('show_address', 'partner_show_db_id', 'address_inline', 'show_email', 'show_vat', 'lang')
    def _compute_display_name(self):
        """For invoice/delivery contacts (when addresses are shown): name plus address lines, no parent prefix."""
        super()._compute_display_name()
        if self.env.context.get('show_address'):
            for partner in self.filtered(lambda p: p.type in ('invoice', 'delivery')):
                lines = [partner.name or '', partner.street or '', partner.street2 or '',
                         ' '.join(x for x in [partner.city, partner.state_id.name, partner.zip] if x),
                         partner.country_id.name or '']
                partner.display_name = '\n'.join(l for l in lines if l)


class ResUsers(models.Model):
    """Per-user flags used by the sales and purchase approval rules."""
    _inherit = 'res.users'

    is_purchase_manager = fields.Boolean(string='Purchase Manager')
    is_director_marketing = fields.Boolean(string='Director Marketing')
    is_marketing_manager = fields.Boolean(string='Marketing Manager')
    # Told when a quotation reaches the final approval step (notification only).
    is_quotation_final_approver = fields.Boolean(string='Notify on Quotation Final Approval', default=False)


class ProductTemplate(models.Model):
    """Product flag: miscellaneous items (relaxes some purchase rules)."""
    _inherit = 'product.template'

    is_miscellaneous_product = fields.Boolean(string='Is Miscellaneous Product')


class ProductProduct(models.Model):
    """Wattage of a panel: the sale price is price-per-watt times wattage."""
    _inherit = 'product.product'

    wattage = fields.Float(string='Wattage (W)', default=1.0)
    higher_wattage = fields.Boolean(string='Higher Wattage', default=False)


class SaleOrderTerms(models.Model):
    """Commercial terms, bank and address details on a sale order (Terms and Conditions tab)."""
    _inherit = 'sale.order'

    advmfg_so_active = fields.Boolean(compute='_compute_advmfg_so_active')
    bank_account_id = fields.Many2one('advmfg.bank.account', string='Bank Account', tracking=True,
                                      domain="[('company_id', '=', company_id), ('active', '=', True)]")
    bank_account_number = fields.Char(related='bank_account_id.account_number', string='Account Number')
    bank_name = fields.Char(related='bank_account_id.bank_name', string='Bank Name')
    bank_account_name = fields.Char(related='bank_account_id.account_name', string='Account Name')
    bank_branch_name = fields.Char(related='bank_account_id.branch_name', string='Branch')
    bank_ifsc_code = fields.Char(related='bank_account_id.ifsc_code', string='IFSC Code')
    billing_address_id = fields.Many2one(related='partner_invoice_id', readonly=False, string='Billing Address')
    shipping_address_id = fields.Many2one(related='partner_shipping_id', readonly=False, string='Shipping Address')
    billing_gst_number = fields.Char(related='partner_invoice_id.gst_number', string='Billing GSTIN')
    shipping_gst_number = fields.Char(related='partner_shipping_id.gst_number', string='Shipping GSTIN')
    shipping_same_as_billing = fields.Boolean(string='Shipping same as billing')
    price_validity = fields.Date(related='validity_date', string='Price Validity')
    warranty_type = fields.Selection([('performance', 'Performance'), ('replacement', 'Replacement'),
                                      ('both', 'Both')], string='Warranty Type')
    warranty_details = fields.Text()
    warranty = fields.Char(string='Warranty (legacy)')
    delivery_type = fields.Selection([('immediate', 'Immediate'), ('scheduled', 'Scheduled'),
                                      ('discussion', 'As per discussion')], string='Delivery Type')
    dispatch_location = fields.Char()
    delivery_terms = fields.Char(string='Delivery Terms (legacy)')
    freight_type = fields.Selection([('extra', 'Extra'), ('included', 'Included'), ('cip', 'CIP')], string='Freight')
    payment_type = fields.Selection([('advance', '100% Advance'), ('partial', 'Partial Advance'),
                                     ('credit', 'Credit'), ('lc', 'Letter of Credit (LC)')], string='Payment Type')
    payment_terms_description = fields.Text()
    cancellation_policy = fields.Selection([('deduction', '3% Deduction'), ('non_refundable', 'Non-refundable'),
                                            ('custom', 'Custom')], string='Cancellation Policy')
    cancellation_details = fields.Text()
    cancellation = fields.Char(string='Cancellation (legacy)')
    certifications_type = fields.Selection([('iec', 'IEC'), ('almm', 'ALMM'), ('bis', 'BIS'),
                                            ('all', 'IEC + ALMM + BIS')], string='Certification Standard')
    certifications = fields.Char(string='Certifications (legacy)')
    tolerance_type = fields.Selection([('positive', 'Positive'), ('negative', 'Negative'),
                                       ('range', '+/- Range')], string='Tolerance')
    tolerance = fields.Char(string='Tolerance (legacy)')
    material_delivery_terms = fields.Text()
    material_delivery = fields.Char(string='Material Delivery (legacy)')
    custom_duty_clause = fields.Text()
    note_custom = fields.Text(string='Additional Notes')
    module_specifications = fields.Text()

    @api.depends('company_id')
    @api.depends_context('uid', 'company')
    def _compute_advmfg_so_active(self):
        """Is the special sales behaviour on for this order and user?"""
        switch = self.env['advmfg.switch']
        for order in self:
            order.advmfg_so_active = switch.is_active(order.company_id or self.env.company)

    @api.model
    def default_get(self, fields_list):
        """New quotations are valid for 7 days and use the company's first bank account."""
        res = super().default_get(fields_list)
        if self.env['advmfg.switch'].is_active() and 'validity_date' in fields_list:
            res['validity_date'] = fields.Date.add(fields.Date.context_today(self), days=7)
        if self.env['advmfg.switch'].is_active() and 'bank_account_id' in fields_list:
            res['bank_account_id'] = self.env['advmfg.bank.account'].get_default_bank_for_company().id
        return res

    @api.onchange('shipping_same_as_billing', 'partner_invoice_id')
    def _onchange_shipping_same_as_billing(self):
        """When ticked, the shipping address follows the billing address."""
        if self.shipping_same_as_billing and self.partner_invoice_id:
            self.partner_shipping_id = self.partner_invoice_id

    def action_quotation_send(self):
        """Only certain roles may send a quotation."""
        if self.env['advmfg.switch'].is_active():
            user = self.env.user
            allowed = (user.has_group('base.group_system') or user.has_group('sales_team.group_sale_salesman')
                       or user.has_group('sales_team.group_sale_salesman_all_leads')
                       or user.has_group('sales_team.group_sale_manager')
                       or user.is_director_marketing or user.is_marketing_manager)
            if not allowed:
                raise UserError(_('You do not have the necessary permissions to send this quotation.'))
        return super().action_quotation_send()
