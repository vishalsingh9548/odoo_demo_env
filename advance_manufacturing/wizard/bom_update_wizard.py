from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgBomUpdateWizard(models.TransientModel):
    """The "Update Bill Of Material" window opened from a manufacturing order."""
    _name = 'advmfg.bom.update.wizard'
    _description = 'BOM Revision Window'

    production_id = fields.Many2one('mrp.production', string='Manufacturing Order')
    bom_id = fields.Many2one('mrp.bom', string='Bill of Materials')
    product_tmpl_id = fields.Many2one('product.template', string='Product')
    revision_type = fields.Selection([('bom', 'Bill of Materials'), ('product', 'Product Only')],
                                     default='bom', string='Apply on')
    revision_id = fields.Many2one('advmfg.bom.revision', string='Engineering Change Order')

    def default_get(self, fields_list):
        """Start from the order's current BOM and product."""
        res = super().default_get(fields_list)
        mo = self.env['mrp.production'].browse(self.env.context.get('active_id') or res.get('production_id'))
        if mo:
            res.update({'production_id': mo.id, 'bom_id': mo.bom_id.id, 'product_tmpl_id': mo.product_id.product_tmpl_id.id})
        return res

    def _reopen(self):
        """Show this same window again (so the next button can be pressed)."""
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'name': _('Engineering Change Orders')}

    def create_revision(self):
        """Revise BOM: reuse an open change for this order and BOM, or create one; then make its editable copy."""
        self.ensure_one()
        Rev = self.env['advmfg.bom.revision']
        rev = Rev.search([('production_id', '=', self.production_id.id), ('bom_id', '=', self.bom_id.id),
                          ('revision_type', '=', self.revision_type), ('product_tmpl_id', '=', self.product_tmpl_id.id),
                          ('state', '=', 'draft')], limit=1)
        if not rev:
            rev = Rev.create({'name': '%s%s' % (self.product_tmpl_id.name, self.production_id.name or ''),
                              'production_id': self.production_id.id, 'bom_id': self.bom_id.id,
                              'product_tmpl_id': self.product_tmpl_id.id, 'revision_type': self.revision_type})
        rev.action_new_revision()
        self.revision_id = rev
        return self._reopen()

    def update_bom(self):
        """Update BOM: apply the change and point the manufacturing order at the new BOM."""
        self.ensure_one()
        if not self.revision_id:
            raise UserError(_('Please press "Revise BOM" first.'))
        self.revision_id.action_apply()
        self.production_id.write({'bom_id': self.revision_id.new_bom_id.id})
        return {'type': 'ir.actions.act_window_close'}
