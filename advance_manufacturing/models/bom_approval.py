import json

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Fields that may change on a BOM without needing approval (bookkeeping only).
IGNORED_FIELDS = {'approval_state', '__last_update', 'write_date', 'write_uid', 'message_ids',
                  'message_follower_ids', 'activity_ids', 'message_main_attachment_id'}


class MrpBom(models.Model):
    """A Bill of Materials that ordinary users cannot change directly.

    Non-administrators send a change request; an administrator or "BOM Approver" approves it.
    """
    _inherit = 'mrp.bom'

    approval_state = fields.Selection([('none', 'None'), ('pending', 'Pending')], default='none',
                                      string='Approval State', copy=False)
    # The manufacturing order that triggered a revision of this BOM (for tracing).
    production_id = fields.Many2one('mrp.production', string='Production #', copy=False)
    # Screen helper: is the approval workflow in force for the current user on this BOM?
    advmfg_approval_active = fields.Boolean(compute='_compute_advmfg_approval_active')

    @api.depends('company_id')
    @api.depends_context('uid', 'company')
    def _compute_advmfg_approval_active(self):
        """The workflow applies to switched-on users who are not administrators."""
        for bom in self:
            bom.advmfg_approval_active = (self.env['advmfg.switch'].is_active(bom.company_id or self.env.company)
                                          and not self.env.user.has_group('base.group_system'))

    def _advmfg_needs_approval(self):
        """True when the current user's change must go through approval."""
        return (self.env['advmfg.switch'].is_active(self.company_id or self.env.company)
                and not self.env.user.has_group('base.group_system')
                and not self.env.context.get('bypass_bom_approval'))

    def write(self, vals):
        """Block direct edits by non-administrators: turn them into an approval request instead."""
        changed = set(vals) - IGNORED_FIELDS
        if changed and self._advmfg_needs_approval():
            for bom in self:
                if bom.approval_state == 'pending':
                    raise UserError(_("BOM '%s' already has a pending approval request. "
                                      "Wait for admin to approve/reject first.", bom.display_name))
                snapshot = [{'id': l.id, 'product_id': l.product_id.id, 'name': l.product_id.display_name,
                             'qty': l.product_qty, 'uom': l.product_uom_id.display_name} for l in bom.bom_line_ids]
                self.env['mrp.bom.approval.request'].sudo().create({
                    'bom_id': bom.id, 'requested_by': self.env.user.id,
                    'proposed_vals': json.dumps(vals, default=str),
                    'original_vals': json.dumps({'bom_line_ids': snapshot}, default=str),
                    'note': _('Direct edit by %s', self.env.user.name),
                })
                super(MrpBom, bom.with_context(bypass_bom_approval=True)).write({'approval_state': 'pending'})
                bom._advmfg_notify_admins(_('A change was requested on this Bill of Materials by %s.', self.env.user.name))
            # Not an error: raising would roll the saved request back. The record simply keeps its old values,
            # shows "Pending", and the change is applied when an approver approves.
            return True
        return super().write(vals)

    def _advmfg_notify_admins(self, text):
        """Leave a note on the BOM addressed to every administrator (in-app only, no email)."""
        admins = self.env.ref('base.group_system').users.partner_id
        self.sudo().message_post(body=text, partner_ids=admins.ids, message_type='comment', subtype_xmlid='mail.mt_note')

    def action_send_bom_for_approval(self):
        """Request Change button: open the change-request window."""
        self.ensure_one()
        if self.approval_state == 'pending':
            raise UserError(_('This BOM already has a pending approval request.'))
        return {'type': 'ir.actions.act_window', 'name': _('Request BOM Change'),
                'res_model': 'mrp.bom.change.wizard', 'view_mode': 'form', 'target': 'new',
                'context': {'default_bom_id': self.id}}


class MrpBomLine(models.Model):
    """Component lines follow the same rule: non-administrators cannot edit them directly."""
    _inherit = 'mrp.bom.line'

    def _advmfg_block(self):
        """Raise when a non-administrator tries to edit lines outside the request window."""
        if any(l.bom_id._advmfg_needs_approval() for l in self):
            raise UserError(_('Use "Request Change" to change the components of this Bill of Materials.'))

    def write(self, vals):
        self._advmfg_block()
        return super().write(vals)

    def unlink(self):
        self._advmfg_block()
        return super().unlink()


class MrpBomApprovalRequest(models.Model):
    """One request to change a BOM, waiting for an approver."""
    _name = 'mrp.bom.approval.request'
    _description = 'BOM Change Approval Request'
    _order = 'create_date desc'
    _rec_name = 'bom_id'

    bom_id = fields.Many2one('mrp.bom', string='BOM', required=True, ondelete='cascade')
    requested_by = fields.Many2one('res.users', string='Requested By', required=True)
    proposed_vals = fields.Text(string='Proposed Changes (JSON)')
    original_vals = fields.Text(string='Original Values (JSON)')
    state = fields.Selection([('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                             default='pending', required=True)
    reviewed_by = fields.Many2one('res.users', string='Reviewed By', readonly=True)
    review_date = fields.Datetime(string='Review Date', readonly=True)
    reject_reason = fields.Text(string='Rejection Reason')
    note = fields.Text(string='Reason for Change')
    changes_summary = fields.Html(compute='_compute_changes_summary', sanitize=False)

    def _compute_changes_summary(self):
        """Build the Field / Current / Proposed table, with components shown as Add / Update / Remove."""
        labels = {'product_id': 'Product', 'product_tmpl_id': 'Product Template', 'product_qty': 'Quantity',
                  'product_uom_id': 'Unit of Measure', 'type': 'BOM Type', 'code': 'Reference'}
        for req in self:
            try:
                proposed = json.loads(req.proposed_vals or '{}')
                original = json.loads(req.original_vals or '{}')
            except ValueError:
                proposed, original = {}, {}
            rows = []
            for key, label in labels.items():
                if key in proposed:
                    old = original.get(key, '')
                    rows.append((label, old, proposed[key]))
            html = '<table class="table table-sm"><thead><tr><th>Field</th><th>Current Value</th><th>Proposed Value</th></tr></thead><tbody>'
            for label, old, new in rows:
                html += '<tr><td>%s</td><td>%s</td><td>%s</td></tr>' % (escape(label), escape(str(old)), escape(str(new)))
            lines = proposed.get('bom_line_ids') or []
            old_lines = {l['id']: l for l in original.get('bom_line_ids', [])}
            for cmd in lines:
                if not isinstance(cmd, (list, tuple)) or not cmd:
                    continue
                if cmd[0] == 0:
                    vals = cmd[2]
                    html += '<tr class="table-success"><td>Component (Add)</td><td></td><td>%s x %s</td></tr>' % (
                        escape(str(vals.get('name') or vals.get('product_id'))), escape(str(vals.get('product_qty'))))
                elif cmd[0] == 1 and cmd[1] in old_lines and cmd[2].get('product_qty') not in (None, old_lines[cmd[1]]['qty']):
                    html += '<tr class="table-warning"><td>Component (Update)</td><td>%s x %s</td><td>%s</td></tr>' % (
                        escape(old_lines[cmd[1]]['name']), escape(str(old_lines[cmd[1]]['qty'])), escape(str(cmd[2].get('product_qty'))))
                elif cmd[0] == 2 and cmd[1] in old_lines:
                    html += '<tr class="table-danger"><td>Component (Remove)</td><td>%s x %s</td><td></td></tr>' % (
                        escape(old_lines[cmd[1]]['name']), escape(str(old_lines[cmd[1]]['qty'])))
            html += '</tbody></table>'
            req.changes_summary = Markup(html)

    def _check_can_review(self):
        """Only administrators or BOM Approvers may approve or reject, and only while pending."""
        user = self.env.user
        if not (user.has_group('base.group_system') or user.has_group('advance_manufacturing.group_advmfg_manager')):
            raise UserError(_('Only administrators or BOM Approvers can review BOM changes.'))
        if self.state != 'pending':
            raise UserError(_('This request is already processed.'))

    def action_approve(self):
        """Approve: apply the proposed changes to the BOM and unlock it."""
        self.ensure_one()
        self._check_can_review()
        proposed = json.loads(self.proposed_vals or '{}')
        for cmd in proposed.get('bom_line_ids') or []:
            if cmd[0] in (0, 1) and isinstance(cmd[2], dict):
                vals = cmd[2]
                if cmd[0] == 0 and not vals.get('product_id'):
                    raise UserError(_('A component line is missing both product and UoM.'))
                if not vals.get('product_uom_id') and vals.get('product_id'):
                    vals['product_uom_id'] = self.env['product.product'].browse(vals['product_id']).uom_id.id
                vals.setdefault('product_qty', 1.0)
        bom = self.bom_id.with_context(bypass_bom_approval=True)
        bom.write(proposed)
        bom.write({'approval_state': 'none'})
        self.write({'state': 'approved', 'reviewed_by': self.env.user.id, 'review_date': fields.Datetime.now()})
        bom._advmfg_notify_requester(self, _('Your BOM change request was approved by %s.', self.env.user.name))
        return True

    def action_reject(self):
        """Reject: leave the BOM unchanged and unlock it."""
        self.ensure_one()
        self._check_can_review()
        self.bom_id.with_context(bypass_bom_approval=True).write({'approval_state': 'none'})
        self.write({'state': 'rejected', 'reviewed_by': self.env.user.id, 'review_date': fields.Datetime.now()})
        self.bom_id._advmfg_notify_requester(self, _('Your BOM change request was rejected by %s. Reason: %s',
                                                     self.env.user.name, self.reject_reason or '-'))
        return True


class MrpBomNotify(models.Model):
    """Small helper: leave an in-app note for the person who asked for a change."""
    _inherit = 'mrp.bom'

    def _advmfg_notify_requester(self, request, text):
        """Post a note on the BOM addressed to the requester."""
        self.sudo().message_post(body=text, partner_ids=request.requested_by.partner_id.ids,
                                 message_type='comment', subtype_xmlid='mail.mt_note')
