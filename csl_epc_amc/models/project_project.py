# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    """Adds the AMC contract count and smart button to the Project."""
    _inherit = 'project.project'

    amc_count = fields.Integer(
        string='AMC Count', compute='_compute_amc_count',
        help="How many AMC contracts exist for this project.",
    )

    # Counts the AMC contracts linked to this project, for the smart button
    def _compute_amc_count(self):
        for project in self:
            project.amc_count = self.env['epc.amc.contract'].search_count([('project_id', '=', project.id)])

    # Opens the project's AMC contract(s): straight into the record when there is one
    def action_view_amc_contracts(self):
        self.ensure_one()
        records = self.env['epc.amc.contract'].search([('project_id', '=', self.id)])
        action = {
            'type': 'ir.actions.act_window',
            'name': 'AMC Contracts',
            'res_model': 'epc.amc.contract',
            'context': {'default_project_id': self.id},
        }
        if len(records) == 1:
            action.update({'view_mode': 'form', 'res_id': records.id})
        else:
            action.update({'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)]})
        return action
