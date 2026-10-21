# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CrmLead(models.Model):
    """Adds the Site Survey link, count and buttons to the CRM Lead/Opportunity."""
    _inherit = 'crm.lead'

    site_survey_count = fields.Integer(
        string='Site Survey Count', compute='_compute_site_survey_count',
        help="How many Site Survey records exist for this lead.",
    )
    # Counts the Site Survey records linked to this lead, for the smart button on the form
    @api.depends('site_survey_ids')
    def _compute_site_survey_count(self):
        for lead in self:
            lead.site_survey_count = len(lead.site_survey_ids)

    site_survey_ids = fields.One2many(
        'epc.site.survey', 'lead_id', string='Site Surveys',
        help="All Site Survey visits scheduled or completed for this lead.",
    )
    # Opens (or creates, if none exist yet) a Site Survey for this lead, called from
    # the "Schedule Site Survey" button on the Lead form
    def action_create_site_survey(self):
        self.ensure_one()
        survey = self.env['epc.site.survey'].create({'lead_id': self.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.site.survey',
            'view_mode': 'form',
            'res_id': survey.id,
            'target': 'current',
        }

    # Opens the list of Site Surveys already linked to this lead, called from the
    # "Site Surveys" smart button
    def action_view_site_surveys(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Site Surveys',
            'res_model': 'epc.site.survey',
            'view_mode': 'list,form',
            'domain': [('lead_id', '=', self.id)],
            'context': {'default_lead_id': self.id},
        }
