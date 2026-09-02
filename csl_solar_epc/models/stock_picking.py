# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    """Stage 8B of the process diagram shows 'Vendor Delivery -> Goods Receipt
    (GRN) -> Quality Check Incoming QC -> Store in Warehouse' as one straight
    line — meaning material is only supposed to reach the warehouse shelf
    after it has passed an Incoming Material Quality Check. Nothing enforced
    that ordering before this: a receipt could be validated (and its stock
    made available to the project) with no quality check done at all. This
    file adds that one guard rail, for a project's incoming receipts only.
    """
    _inherit = 'stock.picking'

    # Stops a project's incoming receipt from being validated (and its stock
    # becoming available) until an Incoming Material Quality Check for it has
    # been logged and has actually passed
    def button_validate(self):
        for picking in self:
            if picking.project_id and picking.picking_type_id.code == 'incoming':
                checks = self.env['epc.quality.check'].search([
                    ('picking_id', '=', picking.id),
                    ('category', '=', 'incoming_material'),
                ])
                if not checks:
                    raise UserError(
                        "This receipt has no Incoming Material Quality Check logged "
                        "against it yet. Go to Solar EPC > Quality Checks, log one "
                        "for this delivery (Related Delivery/Receipt = %s), and pass "
                        "it before receiving this material into stock." % picking.name
                    )
                if not any(check.overall_result == 'pass' for check in checks):
                    raise UserError(
                        "The Incoming Material Quality Check for this receipt has not "
                        "passed yet (it's still Pending or has Failed). Resolve it "
                        "before receiving this material into stock."
                    )
        return super().button_validate()
