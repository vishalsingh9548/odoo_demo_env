# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    """Links a Quotation / Sales Order back to the BOQ it was generated from."""
    _inherit = 'sale.order'

    boq_id = fields.Many2one(
        'epc.boq', string='Source BOQ', copy=False,
        help="The Bill of Quantities this quotation was generated from, if any.",
    )

    # Makes the project created from this order start with its source BOQ
    def _epc_project_vals(self):
        vals = super()._epc_project_vals()
        vals['boq_id'] = self.boq_id.id if self.boq_id else False
        return vals

    # A BOQ quotation is always an EPC order
    def _epc_should_create_project(self):
        return super()._epc_should_create_project() or bool(self.boq_id)

    # When the quotation is cancelled, the BOQ can produce a fresh quotation again
    def _action_cancel(self):
        result = super()._action_cancel()
        boqs = self.env['epc.boq'].sudo().search([('sale_order_id', 'in', self.ids)])
        for boq in boqs:
            boq.message_post(body="Quotation %s was cancelled; a new quotation can be created from this BOQ." % boq.sale_order_id.name)
        boqs.write({'sale_order_id': False})
        return result
