import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AdvmfgSaleConfirmWizard(models.TransientModel):
    """'Confirm Sale Order' window: for each product choose how many finished units come from stock; the rest is manufactured."""
    _name = 'advmfg.sale.confirm.wizard'
    _description = 'Sale Order Confirmation Wizard - MO Control'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    mode = fields.Selection([('automatic', 'Automatic'), ('manual', 'Manual')], default='manual', required=True)
    line_ids = fields.One2many('advmfg.sale.confirm.wizard.line', 'wizard_id', string='Products')
    can_send_for_approval = fields.Boolean(compute='_compute_approval_fields')
    is_sales_admin_user = fields.Boolean(compute='_compute_approval_fields')
    approval_recipient_name = fields.Char(compute='_compute_approval_fields')
    confirm_sale_order = fields.Boolean(related='sale_order_id.confirm_sale_order')

    @api.depends('sale_order_id')
    def _compute_approval_fields(self):
        """Copy the approval flags from the order (orders copied from a reference skip approval)."""
        for wiz in self:
            order = wiz.sale_order_id
            if order.reference_so_id:
                wiz.can_send_for_approval, wiz.is_sales_admin_user = False, True
            else:
                wiz.can_send_for_approval, wiz.is_sales_admin_user = order.can_send_for_approval, order.is_sales_admin_user
            wiz.approval_recipient_name = (_('Sales Administrator') if order.approval_state == 'pending_second_approval'
                                           or order.env.user.has_group('advance_manufacturing.group_sale_second_approval')
                                           else _('Second Approval'))

    @api.model
    def default_get(self, fields_list):
        """Start fresh (delete old windows of this order), restore a saved snapshot, or compute the lines."""
        res = super().default_get(fields_list)
        order = self.env['sale.order'].browse(res.get('sale_order_id') or self.env.context.get('default_sale_order_id'))
        if not order:
            return res
        self.sudo().search([('sale_order_id', '=', order.id)]).unlink()
        # A saved snapshot (made by "Send for Approval") is restored if its lines still exist.
        if order.pending_wizard_state:
            try:
                snap = json.loads(order.pending_wizard_state)
                lines = []
                for l in snap.get('lines', []):
                    if not self.env['sale.order.line'].browse(l['sale_line_id']).exists():
                        raise ValueError
                    lines.append(l)
                res['mode'] = snap.get('mode', 'manual')
                res['line_ids'] = [(0, 0, self._line_vals(order, l['sale_line_id'], l['manual_stock_qty'])) for l in lines]
                order.pending_wizard_state = False
                return res
            except ValueError:
                order.pending_wizard_state = False
        res['line_ids'] = [(0, 0, self._line_vals(order, l.id, 0)) for l in order.order_line
                           if l.product_id and l.product_id.type == 'consu']
        return res

    def _available_units(self, product):
        """Finished, finished-and-done units of this product that nobody has claimed yet (oldest first)."""
        return self.env['advmfg.unit'].search([
            ('product_id', '=', product.id), ('state', '=', 'completed'), ('stock_sale_order_id', '=', False),
            ('production_id.state', '=', 'done')], order='id asc')

    def _line_vals(self, order, line_id, manual):
        """Values for one wizard line."""
        line = self.env['sale.order.line'].browse(line_id)
        return {'sale_line_id': line.id, 'product_id': line.product_id.id, 'ordered_qty': line.product_uom_qty,
                'available_qty': len(self._available_units(line.product_id)), 'manual_stock_qty': manual}

    @api.onchange('mode')
    def _onchange_mode(self):
        """Switching mode clears every 'take from stock' number."""
        for line in self.line_ids:
            line.manual_stock_qty = 0

    def _control_map(self):
        """{product id: {stock_qty, mo_qty}} after validating the numbers."""
        control, total_by_product = {}, {}
        for line in self.line_ids:
            stock = line.stock_qty
            if self.mode == 'manual':
                if stock > line.available_qty:
                    raise UserError(_("Stock quantity (%s) cannot exceed available quantity (%s) for product '%s'.",
                                      stock, line.available_qty, line.product_id.display_name))
                if stock > line.ordered_qty:
                    raise UserError(_("Stock quantity (%s) cannot exceed ordered quantity (%s) for product '%s'.",
                                      stock, line.ordered_qty, line.product_id.display_name))
            data = control.setdefault(line.product_id.id, {'stock_qty': 0, 'mo_qty': 0})
            data['stock_qty'] += stock
            data['mo_qty'] += max(0, line.ordered_qty - stock)
            total_by_product[line.product_id.id] = total_by_product.get(line.product_id.id, 0) + stock
        for pid, total in total_by_product.items():
            avail = max(l.available_qty for l in self.line_ids if l.product_id.id == pid)
            if total > avail:
                raise UserError(_('Total stock quantity (%s) exceeds the available stock (%s) for %s.', total, avail,
                                  self.env['product.product'].browse(pid).display_name))
        return control

    def _reserve_stock_units(self, control):
        """Claim finished units from stock for this order (so nobody else can take them)."""
        order = self.sale_order_id
        for pid, data in control.items():
            if data['stock_qty'] > 0:
                units = self._available_units(self.env['product.product'].browse(pid))[:int(data['stock_qty'])]
                units.write({'stock_sale_order_id': order.id})

    def action_confirm(self):
        """Confirm MO/Delivery: reserve stock units, confirm the order, shrink the manufacturing orders."""
        self.ensure_one()
        control = self._control_map()
        self._reserve_stock_units(control)
        order = self.sale_order_id.with_context(skip_confirm_wizard=True, mo_control_map=control)
        order.action_confirm()
        return {'type': 'ir.actions.act_window_close'}

    def action_move_to_confirm_order(self):
        """Confirm Sales Order: Sales Administrators only park the order as confirmed (no manufacturing yet)."""
        self.ensure_one()
        self.sale_order_id.pending_wizard_state = False
        return self.sale_order_id.action_move_to_confirm_order_state()

    def action_send_for_approval(self):
        """Send for Approval: remember these numbers, then notify the next approvers."""
        self.ensure_one()
        snap = {'mode': self.mode, 'lines': [{'sale_line_id': l.sale_line_id.id, 'ordered_qty': l.ordered_qty,
                                              'manual_stock_qty': l.manual_stock_qty} for l in self.line_ids]}
        self.sale_order_id.pending_wizard_state = json.dumps(snap)
        self.sale_order_id.action_send_for_approval()
        return {'type': 'ir.actions.act_window_close'}


class AdvmfgSaleConfirmWizardLine(models.TransientModel):
    """One product line of the confirm window."""
    _name = 'advmfg.sale.confirm.wizard.line'
    _description = 'Sale Confirm Wizard Line'

    wizard_id = fields.Many2one('advmfg.sale.confirm.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', readonly=True, ondelete='cascade')
    ordered_qty = fields.Float(readonly=True)
    available_qty = fields.Float(string='Available (Stock)', readonly=True)
    manual_stock_qty = fields.Float(string='Take from Stock')
    stock_qty = fields.Float(compute='_compute_qty', string='Take from Stock (final)')
    mo_qty = fields.Float(compute='_compute_qty', string='Create MO For')

    @api.depends('wizard_id.mode', 'manual_stock_qty', 'available_qty', 'ordered_qty')
    def _compute_qty(self):
        """Automatic mode: take as much as is available (up to the order); manual: what was typed."""
        for line in self:
            if line.wizard_id.mode == 'automatic':
                stock = min(line.available_qty, line.ordered_qty)
            else:
                stock = line.manual_stock_qty
            line.stock_qty = stock
            line.mo_qty = max(0.0, line.ordered_qty - stock)

    @api.onchange('manual_stock_qty')
    def _onchange_manual_stock_qty(self):
        """Keep the typed number between 0 and what is available / ordered."""
        for line in self:
            qty = max(0.0, line.manual_stock_qty)
            qty = min(qty, line.available_qty, line.ordered_qty)
            line.manual_stock_qty = qty


class AdvmfgSaleRejectWizard(models.TransientModel):
    """Split reason window: cancels manufacturing and delivery and marks the order 'Splited'."""
    _name = 'advmfg.sale.reject.wizard'
    _description = 'Sale Reject Wizard'

    sale_order_id = fields.Many2one('sale.order', required=True)
    reason = fields.Text(string='Split Reason', required=True)

    def action_confirm_reject(self):
        """Cancel open MOs and deliveries, free reserved stock units, set the state to Splited."""
        self.ensure_one()
        order = self.sale_order_id
        if order.state not in ('confirm_order', 'sale', 'done'):
            raise UserError(_("Only confirmed sale orders can be rejected. Order '%s' is in state '%s'.",
                              order.name, order.state))
        for mo in self.env['mrp.production'].sudo().search([('origin', '=', order.name),
                                                            ('state', 'not in', ('done', 'cancel'))]):
            mo.action_cancel()
        for picking in order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')):
            picking.action_cancel()
        self.env['advmfg.unit'].sudo().search([('stock_sale_order_id', '=', order.id)]).write({'stock_sale_order_id': False})
        order.write({'state': 'rejected', 'rejection_reason': self.reason})
        return {'type': 'ir.actions.act_window_close'}
