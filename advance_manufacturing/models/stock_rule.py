from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _should_auto_confirm_procurement_mo(self, p):
        """Standard Odoo starts a manufacturing order the moment a sale order is confirmed.

        In Advance Manufacturing mode, products ticked "Keep Manufacturing Orders in Draft"
        (the default) are left in Draft so the production team decides when to start them.
        Everyone else, and products without the tick, behave as standard Odoo.
        """
        if self.env['advmfg.switch'].is_active(p.company_id) and p.product_id.product_tmpl_id.keep_mo_in_draft:
            return False
        return super()._should_auto_confirm_procurement_mo(p)
