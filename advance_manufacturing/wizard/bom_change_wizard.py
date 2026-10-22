import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpBomChangeWizard(models.TransientModel):
    """The "Request BOM Change" window: edit a copy of the BOM, add a reason, send for approval."""
    _name = 'mrp.bom.change.wizard'
    _description = 'BOM Change Request Wizard'

    bom_id = fields.Many2one('mrp.bom', string='BOM', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Product Variant')
    product_tmpl_id = fields.Many2one('product.template', string='Product')
    product_qty = fields.Float(string='Quantity', default=1.0)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    code = fields.Char(string='Reference')
    type = fields.Selection([('normal', 'Manufacture This Product'), ('phantom', 'Kit')], string='BOM Type')
    note = fields.Text(string='Reason for Change')
    wizard_line_ids = fields.One2many('mrp.bom.change.wizard.line', 'wizard_id', string='Components')

    @api.model
    def default_get(self, fields_list):
        """Start from the BOM's current values and components."""
        res = super().default_get(fields_list)
        bom = self.env['mrp.bom'].browse(res.get('bom_id') or self.env.context.get('default_bom_id'))
        if bom:
            res.update({
                'product_id': bom.product_id.id, 'product_tmpl_id': bom.product_tmpl_id.id,
                'product_qty': bom.product_qty, 'product_uom_id': bom.product_uom_id.id,
                'code': bom.code, 'type': bom.type,
                'wizard_line_ids': [(0, 0, {'bom_line_id': l.id, 'product_id': l.product_id.id,
                                            'product_qty': l.product_qty, 'product_uom_id': l.product_uom_id.id})
                                    for l in bom.bom_line_ids],
            })
        return res

    def action_submit_for_approval(self):
        """Send for Approval: store what is proposed and what it replaces, and lock the BOM."""
        self.ensure_one()
        bom = self.bom_id
        if bom.approval_state == 'pending':
            raise UserError(_('This BOM already has a pending approval request.'))
        proposed = {'product_id': self.product_id.id, 'product_tmpl_id': self.product_tmpl_id.id,
                    'product_qty': self.product_qty, 'product_uom_id': self.product_uom_id.id,
                    'code': self.code, 'type': self.type}
        original = {'product_id': bom.product_id.display_name, 'product_tmpl_id': bom.product_tmpl_id.display_name,
                    'product_qty': bom.product_qty, 'product_uom_id': bom.product_uom_id.display_name,
                    'code': bom.code or '', 'type': bom.type}
        commands, kept = [], set()
        for line in self.wizard_line_ids:
            uom = line.product_uom_id or line.product_id.uom_id
            if not uom:
                raise UserError(_("Component '%s' has no Unit of Measure set.", line.product_id.display_name))
            vals = {'product_id': line.product_id.id, 'product_qty': line.product_qty, 'product_uom_id': uom.id}
            if line.bom_line_id:
                kept.add(line.bom_line_id.id)
                commands.append([1, line.bom_line_id.id, vals])
            else:
                vals['name'] = line.product_id.display_name
                commands.append([0, 0, vals])
        for old in bom.bom_line_ids.filtered(lambda l: l.id not in kept):
            commands.append([2, old.id, 0])
        proposed['bom_line_ids'] = commands
        original['bom_line_ids'] = [{'id': l.id, 'product_id': l.product_id.id, 'name': l.product_id.display_name,
                                     'qty': l.product_qty, 'uom': l.product_uom_id.display_name} for l in bom.bom_line_ids]
        self.env['mrp.bom.approval.request'].sudo().create({
            'bom_id': bom.id, 'requested_by': self.env.user.id, 'note': self.note,
            'proposed_vals': json.dumps(proposed, default=str), 'original_vals': json.dumps(original, default=str)})
        bom.with_context(bypass_bom_approval=True).sudo().write({'approval_state': 'pending'})
        bom._advmfg_notify_admins(_('A BOM change was requested by %s. Reason: %s', self.env.user.name, self.note or '-'))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Approval Requested'), 'message': _('Your change was sent for approval.'),
                           'type': 'success', 'next': {'type': 'ir.actions.act_window_close'}}}


class MrpBomChangeWizardLine(models.TransientModel):
    """One component line inside the change-request window."""
    _name = 'mrp.bom.change.wizard.line'
    _description = 'BOM Change Wizard Line'

    wizard_id = fields.Many2one('mrp.bom.change.wizard', ondelete='cascade')
    bom_line_id = fields.Many2one('mrp.bom.line', string='Original Line')
    product_id = fields.Many2one('product.product', string='Component', required=True)
    product_qty = fields.Float(string='Quantity', default=1.0)
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
