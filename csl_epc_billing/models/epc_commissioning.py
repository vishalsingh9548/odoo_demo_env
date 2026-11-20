# -*- coding: utf-8 -*-
from odoo import models


class EpcCommissioning(models.Model):
    _inherit = 'epc.commissioning'

    # Approved commissioning wakes up 'commissioning approved' payment stages
    def action_approve(self):
        result = super().action_approve()
        for commissioning in self.filtered(lambda c: c.approval_state == 'approved'):
            order = commissioning.project_id.epc_sale_order_id
            if order and order.sudo().milestone_ids:
                order._epc_trigger_milestones('commissioning_done')
        return result
