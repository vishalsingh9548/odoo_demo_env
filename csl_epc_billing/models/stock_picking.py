# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # After a delivery is done, if the whole order is delivered, wake up 'material delivered' stages
    def _action_done(self):
        result = super()._action_done()
        orders = self.filtered(lambda p: p.picking_type_code == 'outgoing' and p.sale_id).mapped('sale_id')
        for order in orders.filtered('milestone_ids'):
            order.invalidate_recordset(['delivery_status'])
            if order.delivery_status == 'full':
                order._epc_trigger_milestones('material_delivered')
        return result
