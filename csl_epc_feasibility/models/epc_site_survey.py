# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcSiteSurvey(models.Model):
    """Adds the Feasibility Study link, count and buttons to the Site Survey."""
    _inherit = 'epc.site.survey'

    feasibility_count = fields.Integer(
        string='Feasibility Study Count', compute='_compute_feasibility_count',
        help="How many Technical Feasibility studies were created from this survey.",
    )
    feasibility_ids = fields.One2many(
        'epc.feasibility', 'site_survey_id', string='Feasibility Studies',
        help="Technical Feasibility studies created from this survey.",
    )

    # Counts the Feasibility studies linked to this survey, for the smart button on the form
    @api.depends('feasibility_ids')
    def _compute_feasibility_count(self):
        for survey in self:
            survey.feasibility_count = len(survey.feasibility_ids)

    # Creates a new Technical Feasibility study pre-linked to this survey, called
    # from the "Create Feasibility Study" button
    def action_create_feasibility(self):
        self.ensure_one()
        self._epc_check_ready_for_next_stage()
        feasibility = self.env['epc.feasibility'].create({
            'site_survey_id': self.id,
            'lead_id': self.lead_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.feasibility',
            'view_mode': 'form',
            'res_id': feasibility.id,
            'target': 'current',
        }

    # Opens the list of Feasibility studies already linked to this survey, called
    # from the "Feasibility Studies" smart button
    def action_view_feasibility(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feasibility Studies',
            'res_model': 'epc.feasibility',
            'view_mode': 'list,form',
            'domain': [('site_survey_id', '=', self.id)],
            'context': {'default_site_survey_id': self.id, 'default_lead_id': self.lead_id.id},
        }
