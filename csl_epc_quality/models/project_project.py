# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds DPR and Quality Check counts and smart-button actions to the Project."""
    _inherit = 'project.project'

    dpr_count = fields.Integer(
        string='DPR Count', compute='_compute_dpr_count',
        help="How many Daily Progress Reports have been logged for this project.",
    )
    quality_check_count = fields.Integer(
        string='Quality Check Count', compute='_compute_quality_check_count',
        help="How many Quality Checks have been carried out on this project.",
    )
    # Counts DPRs linked to this project, for the smart button on the project form
    def _compute_dpr_count(self):
        for project in self:
            project.dpr_count = self.env['epc.dpr'].search_count([('project_id', '=', project.id)])

    # Counts Quality Checks linked to this project, for the smart button on the project form
    def _compute_quality_check_count(self):
        for project in self:
            project.quality_check_count = self.env['epc.quality.check'].search_count([('project_id', '=', project.id)])

    # Opens the Daily Progress Reports for this project, called from the smart button
    def action_view_dprs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Progress Reports',
            'res_model': 'epc.dpr',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    # Opens the Quality Checks for this project, called from the smart button
    def action_view_quality_checks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quality Checks',
            'res_model': 'epc.quality.check',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
