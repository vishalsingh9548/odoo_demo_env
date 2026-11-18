# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    subsidy_ids = fields.One2many('epc.subsidy.application', 'project_id', string='Subsidy Applications',
                                  help="Subsidy applications of this project.")
    subsidy_count = fields.Integer(string='Subsidy Applications', compute='_compute_subsidy_count',
                                   help="How many subsidy applications this project has.")

    @api.depends('subsidy_ids')
    def _compute_subsidy_count(self):
        for project in self:
            project.subsidy_count = len(project.subsidy_ids)

    # Opens this project's subsidy applications
    def action_view_subsidies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Subsidy Applications', 'res_model': 'epc.subsidy.application',
            'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
