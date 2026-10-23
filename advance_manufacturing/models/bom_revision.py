from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgBomRevision(models.Model):
    """A new version of a Bill of Materials, started from a manufacturing order.

    Lightweight replacement for the Enterprise "Engineering Change Order": it keeps a copy of the
    BOM to edit, and when applied the order switches to the new version.
    """
    _name = 'advmfg.bom.revision'
    _description = 'BOM Revision (Engineering Change)'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    production_id = fields.Many2one('mrp.production', string='Production #')
    bom_id = fields.Many2one('mrp.bom', string='Current Bill of Materials', required=True)
    new_bom_id = fields.Many2one('mrp.bom', string='New Bill of Materials', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product', required=True)
    revision_type = fields.Selection([('bom', 'Bill of Materials'), ('product', 'Product Only')],
                                     default='bom', string='Apply on')
    state = fields.Selection([('draft', 'In Progress'), ('applied', 'Applied')], default='draft', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    def action_new_revision(self):
        """Make the editable copy of the current BOM (once)."""
        for rev in self:
            if not rev.new_bom_id:
                rev.new_bom_id = rev.bom_id.with_context(bypass_bom_approval=True).copy({
                    'production_id': rev.production_id.id, 'code': _('%s (revision)', rev.bom_id.code or rev.bom_id.display_name)})
        return True

    def action_apply(self):
        """Apply: the order (and anyone using the BOM) moves to the new version; the old one stays available."""
        for rev in self:
            if not rev.new_bom_id:
                raise UserError(_('Create the revision first.'))
            rev.state = 'applied'
            rev.bom_id.sudo().active = True
        return True
