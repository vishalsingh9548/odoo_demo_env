# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcFeasibility(models.Model):
    """Adds the Design link, count and button to the Feasibility Study. The
    existing 'Create BOQ' button keeps working."""
    _inherit = 'epc.feasibility'

    design_ids = fields.One2many('epc.design', 'feasibility_id', string='Designs', help="System designs made from this study.")
    design_count = fields.Integer(string='Design Count', compute='_compute_design_count', help="How many system designs were made from this study.")

    @api.depends('design_ids')
    def _compute_design_count(self):
        for study in self:
            study.design_count = len(study.design_ids)

    # Optional extra rule: with the switch on, a BOQ needs an approved design first
    def _epc_check_ready_for_next_stage(self):
        super()._epc_check_ready_for_next_stage()
        if self.env['epc.config'].flag('require_design') and not self.env.context.get('epc_from_design'):
            for study in self:
                if not study.design_ids.filtered(lambda d: d.approval_state == 'approved'):
                    raise UserError("Create and approve a System Design before creating a BOQ.")

    # Creates a System Design pre-linked to this study
    def action_create_design(self):
        self.ensure_one()
        if self.approval_state != 'approved':
            raise UserError("Approve the feasibility study before creating a design.")
        design = self.env['epc.design'].create({
            'feasibility_id': self.id,
            'lead_id': self.lead_id.id,
            'specific_yield': self.specific_yield or 1400.0,
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': 'epc.design',
            'view_mode': 'form', 'res_id': design.id, 'target': 'current',
        }

    # Opens the designs made from this study
    def action_view_design(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'System Designs', 'res_model': 'epc.design',
            'view_mode': 'list,form', 'domain': [('feasibility_id', '=', self.id)],
        }
