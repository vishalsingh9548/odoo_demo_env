from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Sale-order rules that protect manufacturing."""
    _inherit = 'sale.order'

    def action_cancel(self):
        """An order cannot be cancelled once a delivery has been completed."""
        switch = self.env['advmfg.switch']
        for order in self:
            if switch.is_active(order.company_id) and any(p.state == 'done' for p in order.picking_ids):
                raise UserError(_("Cannot cancel Sale Order '%s' as delivery has already been completed.", order.name))
        return super().action_cancel()


class SaleOrderCancel(models.TransientModel):
    """After the cancel pop-up: also cancel manufacturing orders that have not really started."""
    _inherit = 'sale.order.cancel'

    def action_cancel(self):
        """Cancel the order; then cancel its MOs whose units are all still at the very first stage."""
        res = super().action_cancel()
        switch = self.env['advmfg.switch']
        for order in self.order_id:
            if not switch.is_active(order.company_id):
                continue
            for mo in self.env['mrp.production'].search([('origin', '=', order.name),
                                                         ('state', 'not in', ('done', 'cancel'))]):
                units = mo.advmfg_unit_ids
                if units and all(u.stage_id.sequence == min(units.mapped('stage_id.sequence')) and
                                 u.state in ('yet_to_start', 'draft') for u in units):
                    mo.action_cancel()
        return res
