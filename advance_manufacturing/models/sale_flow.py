import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    """Sale-order flow for Advance Manufacturing: use stock or make, split, approvals."""
    _inherit = 'sale.order'

    reference_so_id = fields.Many2one('sale.order', string='Reference PI', domain=[('state', '=', 'rejected')], copy=False,
                                      help='Select a splited sale order to auto-fill the order lines.')
    rejection_reason = fields.Text(string='Splited Reason:')
    confirm_sale_order = fields.Boolean(string='Confirm MO/Delivery', default=False,
                                        help='If enabled, the sale order can be confirmed.')
    state = fields.Selection(selection_add=[('confirm_order', 'Order Confirmed'), ('rejected', 'Splited')],
                             ondelete={'confirm_order': 'set default', 'rejected': 'set default'})
    # --- approval workflow
    approval_state = fields.Selection([('not_sent', 'Not Sent'), ('pending_second_approval', 'Pending Second Approval'),
                                       ('pending_admin', 'Pending Admin Approval'), ('approved', 'Approved')],
                                      default='not_sent', copy=False)
    approval_level = fields.Integer(default=0, copy=False)
    current_approval_user_id = fields.Many2one('res.users', copy=False)
    is_sent_for_approval = fields.Boolean(copy=False)
    mto_mo_admin_mail_sent = fields.Boolean(copy=False)
    pending_wizard_state = fields.Text(copy=False)
    mrp_admin = fields.Many2one('res.users', string='Manufacturing Admin', compute='_compute_mrp_admin', store=True)
    can_send_for_approval = fields.Boolean(compute='_compute_approval_flags')
    is_sales_admin_user = fields.Boolean(compute='_compute_approval_flags')

    @api.depends('company_id')
    def _compute_mrp_admin(self):
        """The first user who is a Manufacturing Administrator."""
        manager = self.env.ref('mrp.group_mrp_manager')
        for order in self:
            order.mrp_admin = manager.users[:1]

    # ------------------------------------------------------------------ who may do what
    def _is_sales_admin(self):
        """Admin Approval group or a system administrator."""
        user = self.env.user
        return user.has_group('advance_manufacturing.group_sale_admin_approval') or user.has_group('base.group_system')

    @api.depends_context('uid')
    @api.depends('state', 'approval_state', 'reference_so_id')
    def _compute_approval_flags(self):
        """Compute 'may send for approval' and 'is a sales administrator' for the current user."""
        user = self.env.user
        for order in self:
            admin = order._is_sales_admin()
            order.is_sales_admin_user = admin or bool(order.reference_so_id)
            can = False
            if not order.reference_so_id and not admin and order.state in ('draft', 'sent'):
                if order.approval_state == 'not_sent':
                    can = True
                elif order.approval_state == 'pending_second_approval':
                    can = user.has_group('advance_manufacturing.group_sale_second_approval')
                elif order.approval_state == 'pending_admin':
                    can = user.has_group('advance_manufacturing.group_sale_second_approval')
            order.can_send_for_approval = can

    def _notify_users(self, users, text):
        """Leave an in-app note addressed to these users."""
        self.sudo().message_post(body=text, partner_ids=users.partner_id.ids, message_type='comment',
                                 subtype_xmlid='mail.mt_note')

    def action_send_for_approval(self):
        """Send for Approval: first-level senders notify Second Approvers; second approvers notify the final approvers."""
        self.ensure_one()
        if self._is_sales_admin():
            raise UserError(_('Sales Administrators cannot use Send for Approval. Please confirm directly.'))
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Only quotations in Draft or Quotation Sent can be submitted for approval.'))
        if not self.can_send_for_approval:
            raise UserError(_('You are not allowed to send this quotation for approval at this stage.'))
        if self.approval_state == 'not_sent':
            label, users = _('Second Approval'), self.env.ref('advance_manufacturing.group_sale_second_approval').users
            nxt, level = 'pending_second_approval', 1
        else:
            label = _('Sales Administrator')
            users = self.env['res.users'].search([('is_quotation_final_approver', '=', True)])
            nxt, level = 'pending_admin', 2
        users = users.filtered('active')
        if not users:
            raise UserError(_('No users found in the %s group. Please configure the group members.', label))
        self.sudo().write({'approval_state': nxt, 'approval_level': level, 'is_sent_for_approval': True,
                    'current_approval_user_id': users[:1].id})
        self._notify_users(users, _('Quotation %s was sent for approval by %s.', self.name, self.env.user.name))
        return True

    # ------------------------------------------------------------------ confirm
    def _confirmation_error_message(self):
        """A confirm-pending order only needs every line to have a product."""
        self.ensure_one()
        if self.state == 'confirm_order':
            if any(not l.display_type and not l.is_downpayment and not l.product_id for l in self.order_line):
                return _('A line on these orders missing a product, you cannot confirm it.')
            return False
        return super()._confirmation_error_message()

    def action_move_to_confirm_order_state(self):
        """Park the order as 'Order Confirmed' without creating manufacturing or delivery."""
        self.write({'state': 'confirm_order'})
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm(self):
        """Confirm: in Advance Manufacturing mode open the stock-or-make window first."""
        switch = self.env['advmfg.switch']
        if not all(switch.is_active(o.company_id) for o in self):
            return super().action_confirm()
        ctx = self.env.context
        if ctx.get('skip_confirm_wizard'):
            return self._action_confirm_with_mo_control(ctx.get('mo_control_map', {}))
        for order in self:
            if not order.reference_so_id and order.state in ('draft', 'sent') and not order._is_sales_admin():
                raise UserError(_('Only Sales Administrators can confirm quotations. '
                                  'Please use Send for Approval.'))
        if not any(l.product_id and l.product_id.type == 'consu' for l in self.order_line):
            res = super().action_confirm()
            self.write({'approval_state': 'approved', 'current_approval_user_id': False})
            return res
        wizard = self.env['advmfg.sale.confirm.wizard'].with_context(active_id=self.id, default_sale_order_id=self.id).create(
            {'sale_order_id': self.id})
        return {'type': 'ir.actions.act_window', 'name': _('Confirm Sale Order'), 'res_model': 'advmfg.sale.confirm.wizard',
                'res_id': wizard.id, 'view_mode': 'form', 'target': 'new',
                'context': {'active_id': self.id, 'default_sale_order_id': self.id}}

    def _action_confirm_with_mo_control(self, control_map):
        """Confirm the order, then shrink (or remove) the manufacturing orders to what really has to be made."""
        res = super(SaleOrder, self.with_context(skip_confirm_wizard=False)).action_confirm()
        for order in self:
            order.write({'approval_state': 'approved', 'current_approval_user_id': False})
            if control_map:
                remaining = {pid: d.get('mo_qty', 0) for pid, d in control_map.items()}
            else:
                remaining = {l.product_id.id: l.product_uom_qty for l in order.order_line if l.product_id.type == 'consu'}
            mos = self.env['mrp.production'].search([('origin', '=', order.name), ('state', 'in', ('draft', 'confirmed'))],
                                                    order='id asc')
            for mo in mos:
                needed = remaining.get(mo.product_id.id, 0)
                if needed <= 0:
                    # Fully covered by finished stock: no manufacturing order needed.
                    mo.action_cancel()
                    mo.unlink()
                    continue
                if mo.product_qty != needed:
                    self.env['change.production.qty'].sudo().with_context(skip_activity=True).create(
                        {'mo_id': mo.id, 'product_qty': needed}).change_prod_qty()
                remaining[mo.product_id.id] = 0
        return res

    # ------------------------------------------------------------------ split
    def action_reject(self):
        """Split button: ask for a reason, then cancel the manufacturing and delivery."""
        return {'name': _('Split Sale Order'), 'type': 'ir.actions.act_window', 'res_model': 'advmfg.sale.reject.wizard',
                'view_mode': 'form', 'target': 'new', 'context': {'default_sale_order_id': self.id}}

    @api.onchange('reference_so_id')
    def _onchange_reference_so_id(self):
        """Copy customer, lines, optional products and all terms from a splited order into this new one."""
        src = self.reference_so_id
        if not src:
            return
        self.partner_id = src.partner_id
        self.order_line = [(5, 0, 0)] + [(0, 0, {
            'product_id': l.product_id.id, 'name': l.name, 'product_uom_qty': l.product_uom_qty,
            'product_uom': l.product_uom.id, 'price_unit': l.price_unit, 'discount': l.discount,
            'tax_id': [(6, 0, l.tax_id.ids)], 'is_from_reference_so': True, 'unit_price': l.unit_price,
        }) for l in src.order_line]
        self.sale_order_option_ids = [(5, 0, 0)] + [(0, 0, {
            'product_id': o.product_id.id, 'name': o.name, 'quantity': o.quantity, 'uom_id': o.uom_id.id,
            'price_unit': o.price_unit, 'discount': o.discount, 'is_from_reference_so': True,
        }) for o in src.sale_order_option_ids]
        for f in ('payment_type', 'payment_terms_description', 'payment_term_id', 'warranty_type', 'warranty_details',
                  'delivery_type', 'delivery_terms', 'dispatch_location', 'freight_type', 'material_delivery_terms',
                  'cancellation_policy', 'cancellation_details', 'cancellation', 'custom_duty_clause', 'note_custom',
                  'material_delivery', 'certifications_type', 'tolerance_type', 'tolerance', 'module_specifications',
                  'bank_account_id', 'note'):
            self[f] = src[f]
        return {'warning': {'title': _('Sales Order Copied'),
                            'message': _("Sales Order have been copied from rejected sale order '%s'. ", src.name)}}


class SaleOrderLine(models.Model):
    """Wattage pricing and the lock on lines copied from a reference order."""
    _inherit = 'sale.order.line'

    wattage = fields.Float(string='Wattage (W)')
    unit_price = fields.Float(string='Per Unit Price')
    higher_wattage = fields.Boolean(string='Higher Wattage', default=False)
    is_from_reference_so = fields.Boolean(string='From Reference SO', default=False,
                                          help='Copied from a reference sales order and therefore read-only.')

    PROTECTED_FIELDS = ['product_id', 'product_template_id', 'price_unit', 'product_uom', 'price_subtotal']

    @api.onchange('product_id')
    def _onchange_product_id_wattage(self):
        """On picking a product: per-unit price from the list price, wattage from the product, price = unit x wattage."""
        if self.product_id and self.env['advmfg.switch'].is_active(self.order_id.company_id or self.env.company):
            self.unit_price = self.product_id.lst_price
            self.wattage = self.product_id.wattage or 1.0
            self.price_unit = (self.product_id.lst_price or 1.0) * self.wattage
            self.higher_wattage = self.product_id.higher_wattage or False

    @api.onchange('unit_price')
    def _onchange_unit_price(self):
        """Typing a per-unit price re-prices the line (unit price x wattage)."""
        if self.unit_price and self.env['advmfg.switch'].is_active(self.order_id.company_id or self.env.company):
            self.wattage = self.product_id.wattage or 1.0
            self.price_unit = self.unit_price * self.wattage

    @api.model_create_multi
    def create(self, vals_list):
        """No new lines on an order copied from a reference order."""
        for vals in vals_list:
            if vals.get('is_from_reference_so') or not vals.get('order_id'):
                continue
            if self.env['sale.order'].browse(vals['order_id']).reference_so_id:
                raise UserError(_('You cannot add new order lines to a sale order that was copied from a Reference SO.'))
        return super().create(vals_list)

    def write(self, vals):
        """Copied lines keep their product, price and discount."""
        for line in self:
            if line.is_from_reference_so:
                blocked = [f for f in self.PROTECTED_FIELDS if f in vals]
                if blocked:
                    raise UserError(_('You cannot modify %s on a line copied from a Reference SO.', ', '.join(blocked)))
                if 'discount' in vals and 'product_uom_qty' not in vals:
                    raise UserError(_('You cannot modify discount on a line copied from a Reference SO.'))
                if 'discount' in vals:
                    vals['discount'] = line.discount
        return super().write(vals)


class SaleOrderOption(models.Model):
    """Optional products copied from a reference order are flagged too."""
    _inherit = 'sale.order.option'

    is_from_reference_so = fields.Boolean(default=False)


class MrpProductionConfirm(models.Model):
    """Link between finished units reserved from stock and the sale order that took them."""
    _inherit = 'advmfg.unit'

    stock_sale_order_id = fields.Many2one('sale.order', string='Reserved for Sale Order', copy=False,
                                          help='Finished unit taken from stock for this sale order.')
