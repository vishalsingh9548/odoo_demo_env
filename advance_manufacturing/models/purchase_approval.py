from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductCategoryApproval(models.Model):
    """Which categories restricted purchasers may buy, and which go to the IT approver."""
    _inherit = 'product.category'

    allowed = fields.Boolean(string='Allowed for Restricted Purchasers')
    allowed_it = fields.Boolean(string='Allowed (IT Approval)')


class PurchaseOrderApproval(models.Model):
    """Approval for restricted purchasers: they pick categories and send; an approver confirms or rejects."""
    _inherit = 'purchase.order'

    approval_state = fields.Selection(
        [('none', 'Not Sent'), ('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='none', tracking=True, copy=False)
    approval_channel = fields.Selection([('purchase', 'Purchase'), ('it', 'IT')], copy=False)
    approval_requested_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    is_approval_locked = fields.Boolean(readonly=True, copy=False)
    allowed_category_ids = fields.Many2many('product.category', 'po_allowed_categ_rel', 'po_id', 'categ_id',
                                            string='Categories')
    description = fields.Text(string='Description')
    is_current_user_restricted_purchaser = fields.Boolean(compute='_compute_viewer_flags')
    is_current_user_purchase_approver = fields.Boolean(compute='_compute_viewer_flags')
    is_current_user_it_approver = fields.Boolean(compute='_compute_viewer_flags')

    @api.depends_context('uid')
    def _compute_viewer_flags(self):
        """What the person looking at the order is allowed to do."""
        user = self.env.user
        restricted = user.has_group('advance_manufacturing.group_restricted_purchase_user')
        approver = user.has_group('advance_manufacturing.group_purchase_approver')
        it = user.has_group('advance_manufacturing.group_it_approver')
        for po in self:
            po.is_current_user_restricted_purchaser = restricted
            po.is_current_user_purchase_approver = approver
            po.is_current_user_it_approver = it

    def _advmfg_can_decide(self):
        """May the current user confirm / reject this order?"""
        self.ensure_one()
        user = self.env.user
        if user.has_group('base.group_system') or user.has_group('purchase.group_purchase_manager'):
            return True
        group = 'group_it_approver' if self.approval_channel == 'it' else 'group_purchase_approver'
        return user.has_group('advance_manufacturing.' + group)

    def action_advmfg_send_approval(self):
        """Send Approval: restricted buyers submit; IT approver if any chosen category is an IT one."""
        for po in self:
            if po.approval_state not in ('none', 'rejected'):
                raise UserError(_('%s was already sent for approval.', po.name))
            if not po.allowed_category_ids:
                raise UserError(_('Please choose at least one category first.'))
            po.write({
                'approval_state': 'pending',
                'approval_channel': 'it' if po.allowed_category_ids.filtered('allowed_it') else 'purchase',
                'approval_requested_by_id': self.env.user.id,
            })
            group = 'group_it_approver' if po.approval_channel == 'it' else 'group_purchase_approver'
            for user in self.env.ref('advance_manufacturing.' + group).users[:3]:
                po.sudo().activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                                            note=_('Purchase order %s is waiting for your approval.', po.name))
        return True

    def action_advmfg_reject(self):
        """Reject: only the matching approver may reject an order that is pending."""
        for po in self:
            if po.approval_state != 'pending' or not po._advmfg_can_decide():
                raise UserError(_('%s is pending approval - only Purchase Approver (or IT Approver) can reject it.', po.name))
            po.approval_state = 'rejected'
            po.message_post(body=_('Rejected by %s.', self.env.user.name))
        return True

    def button_confirm(self):
        """Orders pending approval can only be confirmed by the matching approver; confirming marks them approved and locked."""
        for po in self:
            if po.approval_state == 'pending' and not po._advmfg_can_decide():
                raise UserError(_('%s is pending approval - only Purchase Approver (or IT Approver) can confirm it.', po.name))
        res = super().button_confirm()
        for po in self:
            if po.approval_state == 'pending':
                if po.state in ('to approve', 'draft', 'sent'):
                    po.sudo().write({'state': 'purchase'})
                po.sudo().write({'approval_state': 'approved', 'approved_by_id': self.env.user.id,
                                 'is_approval_locked': True})
        return res

    def write(self, vals):
        """Once approved and locked, the order can no longer be edited (system fields excepted)."""
        allowed = {'state', 'message_ids', 'message_follower_ids', 'activity_ids', 'invoice_status', 'is_approval_locked',
                   'approval_state', 'approved_by_id', 'receipt_status', 'date_approve', 'effective_date',
                   'advmfg_label', 'is_shipped', 'date_planned'}
        if any(po.is_approval_locked for po in self) and set(vals) - allowed and not self.env.su:
            raise UserError(_('%s is locked after approval and can no longer be edited.', self[:1].name))
        return super().write(vals)
