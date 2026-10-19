# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    """Solar EPC orders do not create a customer delivery: the material reaches
    the customer through the project (Material Request -> issue to site ->
    consumed at site), so a separate warehouse delivery would take the same
    stock out twice. Ordinary sales orders are completely untouched."""
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        epc_lines = self.filtered(lambda line: line.order_id._epc_should_create_project())
        return super(SaleOrderLine, self - epc_lines)._action_launch_stock_rule(previous_product_uom_qty)
