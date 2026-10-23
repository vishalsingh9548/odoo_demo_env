from odoo import api, models


class AdvmfgSwitch(models.AbstractModel):
    """The "master switch" checker.

    Every special rule in this module first asks this one question:
    "Is Advance Manufacturing ON for this company AND is the current user in the group?"
    If the answer is No, the rule steps aside and standard Odoo carries on.
    """
    _name = 'advmfg.switch'
    _description = 'Advance Manufacturing on/off check'

    @api.model
    def is_active(self, company=None):
        """Return True only when the company has it switched on AND the user is in the group."""
        company = company or self.env.company
        if not company.advmfg_enabled:
            return False
        return self.env.user.has_group('advance_manufacturing.group_advmfg_manager')


class ResUsersAdvmfgCleanup(models.Model):
    """When a user loses the one Advance Manufacturing setting, the hidden helper roles go with it."""
    _inherit = 'res.users'

    def write(self, vals):
        """After any change, anyone without 'Administrator' is stripped of the hidden Advance Manufacturing roles."""
        res = super().write(vals)
        if 'groups_id' in vals or any(k.startswith('in_group_') or k.startswith('sel_groups_') for k in vals):
            main = self.env.ref('advance_manufacturing.group_advmfg_manager', raise_if_not_found=False)
            if main:
                hidden = self.env['res.groups']
                for xid in ('group_advmfg_user', 'group_advmfg_serial_update', 'group_material_requisition_user',
                            'group_advmfg_quality_user', 'group_advmfg_tab_access', 'group_advmfg_bom_approver',
                            'group_advmfg_product_create'):
                    hidden |= self.env.ref('advance_manufacturing.' + xid, raise_if_not_found=False) or hidden
                for user in self.filtered(lambda u: main not in u.groups_id and (u.groups_id & hidden)):
                    super(ResUsersAdvmfgCleanup, user).write({'groups_id': [(3, g.id) for g in (user.groups_id & hidden)]})
        return res
