from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ProductCategory(models.Model):
    """Mark categories whose purchases need a manager's approval."""
    _inherit = 'product.category'

    advmfg_po_approval = fields.Boolean(
        string='Purchase Needs Approval',
        help='Purchase orders with products of this category wait for a purchase manager to approve.')


class PurchaseOrder(models.Model):
    """Purchase approval for restricted categories, plus a free-text label."""
    _inherit = 'purchase.order'

    advmfg_label = fields.Char(string='Purchase Label', copy=False)
    advmfg_active = fields.Boolean(compute='_compute_advmfg_active')

    @api.depends('company_id')
    @api.depends_context('uid', 'company')
    def _compute_advmfg_active(self):
        """Is the special behaviour on for this order's company and the current user?"""
        switch = self.env['advmfg.switch']
        for po in self:
            po.advmfg_active = switch.is_active(po.company_id or self.env.company)

    def _approval_allowed(self):
        """Orders holding a restricted category need a purchase manager, whatever the amount."""
        self.ensure_one()
        if (self.env['advmfg.switch'].is_active(self.company_id)
                and self.order_line.product_id.categ_id.filtered('advmfg_po_approval')
                and not self.env.user.has_group('purchase.group_purchase_manager')):
            return False
        return super()._approval_allowed()

    def button_confirm(self):
        """Confirm; when approval is needed, leave a to-do for the purchase managers."""
        res = super().button_confirm()
        for po in self.filtered(lambda o: o.state == 'to approve'):
            managers = self.env.ref('purchase.group_purchase_manager').users.filtered(
                lambda u: po.company_id in u.company_ids)
            for manager in managers[:3]:
                po.activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                     note=_('Purchase order %s needs your approval.', po.name))
        return res


class ProductTemplate(models.Model):
    """Only people with the 'Product Creation' right may create products (when the mode is on)."""
    _inherit = 'product.template'

    @api.model_create_multi
    def create(self, vals_list):
        """Block product creation for switched-on users who lack the right (administrators are exempt)."""
        user = self.env.user
        if (not self.env.su and self.env['advmfg.switch'].is_active()
                and not user.has_group('advance_manufacturing.group_advmfg_manager')
                and not user.has_group('base.group_system')):
            raise AccessError(_('You are not allowed to create products. Ask an administrator for the '
                                '"Product Creation" access.'))
        return super().create(vals_list)


class SaleOrderLine(models.Model):
    """Combo products: show one shared HSN/SAC code on the line."""
    _inherit = 'sale.order.line'

    is_combo = fields.Boolean(string='Is Combo')
    display_hsn_code = fields.Char(string='HSN/SAC Code', compute='_compute_display_hsn_code')

    @api.depends('is_combo', 'product_id', 'company_id')
    def _compute_display_hsn_code(self):
        """Combo lines show the company's combo code; other lines show the product's own code."""
        for line in self:
            combo = line.company_id.advmfg_combo_hsn_code
            if line.is_combo and combo:
                line.display_hsn_code = combo
            else:
                line.display_hsn_code = line.product_id.l10n_in_hsn_code if 'l10n_in_hsn_code' in line.product_id._fields else False


class ResCompany(models.Model):
    """The company-wide HSN/SAC code used for combo products."""
    _inherit = 'res.company'

    advmfg_combo_hsn_code = fields.Char(string='Combo HSN/SAC Code')
