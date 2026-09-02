# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    """Links a Purchase Order back to the Material Request it was raised from,
    so the procurement team can always trace an RFQ back to why it was needed.
    (The link to the Project itself already exists natively via the
    'project_purchase' app that this module depends on.)
    """
    _inherit = 'purchase.order'

    material_request_id = fields.Many2one(
        'epc.material.request', string='Material Request', copy=False,
        help="The Material Request that generated this Purchase Order, if any.",
    )

    # Tags every warehouse receipt created by confirming this order with the
    # same project the order itself is for, so incoming material for a project
    # can always be found and reported on by project, not just by vendor
    def button_confirm(self):
        result = super().button_confirm()
        for order in self.filtered('project_id'):
            order.picking_ids.write({'project_id': order.project_id.id})
        return result
