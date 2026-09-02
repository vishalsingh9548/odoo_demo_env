# -*- coding: utf-8 -*-
from odoo import api, fields, models
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

    epc_needs_incoming_qc = fields.Boolean(
        string='Needs Incoming QC', compute='_compute_epc_needs_incoming_qc',
        help="True while this is a project's incoming receipt that still has "
             "no passed Incoming Material Quality Check logged against it — "
             "drives the 'Log Quality Check' button on the receipt.",
    )

    # Works out whether this receipt is still missing a passed Incoming
    # Material Quality Check, so the "Log Quality Check" button only shows up
    # exactly when it's actually needed
    @api.depends('project_id', 'picking_type_id.code', 'state')
    def _compute_epc_needs_incoming_qc(self):
        for picking in self:
            if not (picking.project_id and picking.picking_type_id.code == 'incoming'
                    and picking.state not in ('done', 'cancel')):
                picking.epc_needs_incoming_qc = False
                continue
            passed_check = self.env['epc.quality.check'].search_count([
                ('picking_id', '=', picking.id),
                ('category', '=', 'incoming_material'),
                ('overall_result', '=', 'pass'),
            ])
            picking.epc_needs_incoming_qc = not passed_check

    # Opens a blank, pre-filled Incoming Material Quality Check form as a
    # wizard-style dialog right on top of this receipt (target 'new', not a
    # page navigation) — called from the "Log Quality Check" header button
    def action_log_quality_check(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.quality.check',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.project_id.id,
                'default_picking_id': self.id,
                'default_category': 'incoming_material',
            },
        }

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
