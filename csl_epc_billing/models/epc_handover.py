# -*- coding: utf-8 -*-
from odoo import models


class EpcHandover(models.Model):
    _inherit = 'epc.handover'

    # Approved handover wakes up 'handover approved' stages (e.g. retention release)
    def action_approve(self):
        result = super().action_approve()
        for handover in self.filtered(lambda h: h.approval_state == 'approved'):
            order = handover.project_id.epc_sale_order_id
            if order and order.sudo().milestone_ids:
                order._epc_trigger_milestones('handover_done')
        return result
