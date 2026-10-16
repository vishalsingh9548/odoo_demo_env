from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

STATES = [
    ('draft', 'Draft'),
    ('generated', 'Generated'),
    ('listed', 'Listed'),
    ('sold', 'Sold'),
    ('transferred', 'Transferred'),
    ('cancelled', 'Cancelled'),
]
PORTAL_NO_STATES = ('generated', 'listed', 'sold', 'transferred')


def indian_financial_year(date):
    """ '2026-27' for any date between 1 April 2026 and 31 March 2027. """
    start = date.year if date.month >= 4 else date.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


class UgEprCertificate(models.Model):
    _name = 'ug.epr.certificate'
    _description = 'EPR Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'generation_date desc, id desc'

    name = fields.Char('Reference', required=True, readonly=True, copy=False, default=lambda self: _('New'))
    portal_certificate_no = fields.Char('CPCB Certificate No.', tracking=True, copy=False,
        help="Certificate number generated on the CPCB EPR portal.")
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', required=True,
        default=lambda self: self.env.company.currency_id)

    generation_date = fields.Date(default=fields.Date.context_today, tracking=True)
    financial_year = fields.Char('Financial Year', compute='_compute_financial_year', store=True, readonly=False,
        index=True, help="Indian financial year (April–March), e.g. 2026-27.")
    epr_category_id = fields.Many2one('ug.epr.category', string='Battery Category', required=True, tracking=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Battery Chemistry', tracking=True)
    quantity_kg = fields.Float('Quantity (kg)', digits='Product Unit of Measure', tracking=True)

    production_ids = fields.Many2many('mrp.production', 'ug_epr_certificate_production_rel',
        'certificate_id', 'production_id', string='Manufacturing Orders', check_company=True,
        domain="[('state', '=', 'done'), ('ug_is_recycling', '=', True), ('ug_epr_available_kg', '>', 0)]")
    allocation_ids = fields.One2many('ug.epr.allocation', 'certificate_id', string='Allocation', readonly=True)
    available_kg = fields.Float('Available on MOs (kg)', compute='_compute_available_kg', digits='Product Unit of Measure',
        help="Eligible kg of the linked orders not claimed by other certificates.")

    state = fields.Selection(STATES, default='draft', required=True, tracking=True, index=True, copy=False)

    partner_id = fields.Many2one('res.partner', string='Buyer (Producer)', tracking=True)
    price_per_kg = fields.Monetary('Price per kg', tracking=True)
    amount = fields.Monetary(compute='_compute_amount', store=True)
    sale_order_id = fields.Many2one('sale.order', string='Quotation', readonly=True, copy=False, index=True)
    invoice_ids = fields.Many2many('account.move', compute='_compute_invoice_ids', string='Invoices')
    invoice_count = fields.Integer(compute='_compute_invoice_ids')

    transfer_ref = fields.Char('Transfer Reference', tracking=True, copy=False)
    transfer_date = fields.Date(tracking=True, copy=False)

    @api.depends('generation_date')
    def _compute_financial_year(self):
        for certificate in self:
            certificate.financial_year = certificate.generation_date and indian_financial_year(certificate.generation_date)

    @api.depends('quantity_kg', 'price_per_kg')
    def _compute_amount(self):
        for certificate in self:
            certificate.amount = certificate.quantity_kg * certificate.price_per_kg

    @api.depends('sale_order_id.invoice_ids')
    def _compute_invoice_ids(self):
        for certificate in self:
            certificate.invoice_ids = certificate.sale_order_id.invoice_ids
            certificate.invoice_count = len(certificate.invoice_ids)

    @api.depends('production_ids', 'production_ids.ug_epr_eligible_kg', 'allocation_ids')
    def _compute_available_kg(self):
        for certificate in self:
            certificate.available_kg = sum(
                certificate._ug_production_available(production) for production in certificate.production_ids)

    @api.constrains('state', 'portal_certificate_no')
    def _check_portal_no(self):
        for certificate in self:
            if certificate.state in PORTAL_NO_STATES and not certificate.portal_certificate_no:
                raise ValidationError(_("Enter the CPCB certificate number of %s.", certificate.name))

    @api.constrains('quantity_kg')
    def _check_quantity(self):
        for certificate in self:
            if certificate.quantity_kg < 0:
                raise ValidationError(_("The certificate quantity cannot be negative."))

    # ------------------------------------------------------------------
    # Allocation over manufacturing orders (prevents double claiming)
    # ------------------------------------------------------------------
    def _ug_production_available(self, production):
        """ Eligible kg of `production` not claimed by certificates other than self. """
        self.ensure_one()
        others = self.env['ug.epr.allocation'].sudo().search([
            ('production_id', '=', production._origin.id or production.id),
            ('certificate_id', '!=', self._origin.id or False),
            ('certificate_state', '!=', 'cancelled'),
        ])
        return production.ug_epr_eligible_kg - sum(others.mapped('quantity_kg'))

    def _ug_allocate(self):
        Allocation = self.env['ug.epr.allocation'].sudo()
        for certificate in self:
            certificate.allocation_ids.sudo().unlink()
            if certificate.state == 'cancelled' or not certificate.quantity_kg:
                continue
            remaining = certificate.quantity_kg
            vals_list = []
            for production in certificate.production_ids.sorted(lambda p: (p.date_finished or p.create_date, p.id)):
                take = min(certificate._ug_production_available(production), remaining)
                if take <= 0:
                    continue
                vals_list.append({'certificate_id': certificate.id, 'production_id': production.id, 'quantity_kg': take})
                remaining -= take
            if remaining > 1e-6:
                raise ValidationError(_(
                    "Certificate %(cert)s claims %(qty).2f kg but only %(avail).2f kg is available on the linked "
                    "manufacturing orders (after other certificates).",
                    cert=certificate.name, qty=certificate.quantity_kg,
                    avail=certificate.quantity_kg - remaining))
            Allocation.create(vals_list)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('ug.epr.certificate') or _('New')
        certificates = super().create(vals_list)
        certificates._ug_allocate()
        return certificates

    def write(self, vals):
        if 'state' in vals and not self.env.context.get('ug_epr_state_change'):
            self._ug_check_officer()
        if set(vals) & {'quantity_kg', 'production_ids'} and any(c.state in ('sold', 'transferred') for c in self):
            raise UserError(_("The quantity and orders of a sold certificate cannot be changed."))
        res = super().write(vals)
        if set(vals) & {'quantity_kg', 'production_ids', 'state'}:
            self._ug_allocate()
        return res

    def unlink(self):
        if any(c.state not in ('draft', 'cancelled') for c in self):
            raise UserError(_("Only draft or cancelled certificates can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _ug_check_officer(self):
        if not self.env.su and not self.env.user.has_group('ug_recycling_base.group_ug_epr'):
            raise UserError(_("Only EPR Officers can change the status of EPR certificates."))

    def _ug_set_state(self, state):
        self._ug_check_officer()
        self.with_context(ug_epr_state_change=True).write({'state': state})

    def action_generate(self):
        for certificate in self:
            if certificate.state != 'draft':
                raise UserError(_("Only draft certificates can be marked as generated."))
            if not certificate.quantity_kg or not certificate.production_ids:
                raise UserError(_("Set the quantity and the manufacturing orders of %s.", certificate.name))
            if not certificate.portal_certificate_no:
                raise UserError(_("Enter the CPCB certificate number of %s first.", certificate.name))
        self._ug_set_state('generated')

    def action_list(self):
        if any(c.state != 'generated' for c in self):
            raise UserError(_("Only generated certificates can be listed for sale."))
        self._ug_set_state('listed')

    def action_create_quotation(self):
        self.ensure_one()
        self._ug_check_officer()
        if self.state != 'listed':
            raise UserError(_("Only listed certificates can be quoted."))
        if not self.partner_id or not self.price_per_kg:
            raise UserError(_("Set the buyer and the price per kg first."))
        if self.sale_order_id and self.sale_order_id.state != 'cancel':
            raise UserError(_("Quotation %s already exists for this certificate.", self.sale_order_id.name))
        product = self.company_id._ug_get_epr_product()
        if not product:
            raise UserError(_("Configure the EPR service product in the settings."))
        order = self.env['sale.order'].with_company(self.company_id).create({
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'order_line': [Command.create({
                'product_id': product.id,
                'name': _("EPR certificate %(no)s – %(cat)s – FY %(fy)s",
                          no=self.portal_certificate_no, cat=self.epr_category_id.name, fy=self.financial_year),
                'product_uom_qty': self.quantity_kg,
                'product_uom': product.uom_id.id,
                'price_unit': self.price_per_kg,
            })],
        })
        if order.currency_id != self.currency_id:
            order.order_line.price_unit = self.currency_id._convert(
                self.price_per_kg, order.currency_id, self.company_id, fields.Date.context_today(self))
        self.sale_order_id = order
        self.message_post(body=_("Quotation %s created.", order._get_html_link()))
        return self.action_view_sale_order()

    def _ug_mark_sold(self):
        for certificate in self.filtered(lambda c: c.state == 'listed'):
            certificate.with_context(ug_epr_state_change=True).sudo().write({'state': 'sold'})
            certificate.message_post(body=_("Invoice posted: certificate sold."))

    def action_mark_transferred(self):
        for certificate in self:
            if certificate.state != 'sold':
                raise UserError(_("Only sold certificates can be transferred."))
            if not certificate.transfer_ref:
                raise UserError(_("Enter the transfer reference of %s on the CPCB portal.", certificate.name))
            if not certificate.transfer_date:
                certificate.transfer_date = fields.Date.context_today(self)
        self._ug_set_state('transferred')

    def action_cancel(self):
        if any(c.state == 'transferred' for c in self):
            raise UserError(_("Transferred certificates cannot be cancelled."))
        self._ug_set_state('cancelled')

    def action_reset_draft(self):
        if any(c.state != 'cancelled' for c in self):
            raise UserError(_("Only cancelled certificates can be reset to draft."))
        self._ug_set_state('draft')

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'views': [[False, 'form']],
        }

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        action['context'] = {'create': False}
        return action


class UgEprAllocation(models.Model):
    _name = 'ug.epr.allocation'
    _description = 'EPR Claim on Manufacturing Order'
    _order = 'certificate_id, id'

    certificate_id = fields.Many2one('ug.epr.certificate', required=True, ondelete='cascade', index=True)
    certificate_state = fields.Selection(related='certificate_id.state', store=True, index=True)
    company_id = fields.Many2one(related='certificate_id.company_id', store=True, index=True)
    production_id = fields.Many2one('mrp.production', required=True, ondelete='restrict', index=True)
    quantity_kg = fields.Float('Claimed (kg)', digits='Product Unit of Measure')
