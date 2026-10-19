# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcFeasibility(models.Model):
    """Adds the BOQ link, count and buttons to the Feasibility Study."""
    _inherit = 'epc.feasibility'

    boq_count = fields.Integer(
        string='BOQ Count', compute='_compute_boq_count',
        help="How many Bill of Quantities (BOQ) records were created from this study.",
    )
    boq_ids = fields.One2many(
        'epc.boq', 'feasibility_id', string='BOQs',
        help="Bill of Quantities (costing sheets) created from this feasibility study.",
    )

    # Counts the BOQs linked to this study, for the smart button on the form
    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for feasibility in self:
            feasibility.boq_count = len(feasibility.boq_ids)

    # Creates a new BOQ (costing sheet) pre-linked to this feasibility study,
    # called from the "Create BOQ" button
    def action_create_boq(self):
        self.ensure_one()
        boq = self.env['epc.boq'].create({
            'feasibility_id': self.id,
            'lead_id': self.lead_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.boq',
            'view_mode': 'form',
            'res_id': boq.id,
            'target': 'current',
        }

    # Opens the list of BOQs already linked to this study, called from the
    # "BOQs" smart button
    def action_view_boq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'BOQs',
            'res_model': 'epc.boq',
            'view_mode': 'list,form',
            'domain': [('feasibility_id', '=', self.id)],
            'context': {'default_feasibility_id': self.id, 'default_lead_id': self.lead_id.id},
        }
