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
