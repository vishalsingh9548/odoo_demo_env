from odoo import models, fields

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    customer_type = fields.Selection([
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
    ], string="Customer Type")

    solar_capacity = fields.Float(
        string="Required Capacity (KW)"
    )

    monthly_bill = fields.Float(
        string="Monthly Electricity Bill"
    )

    roof_type = fields.Selection([
        ('rcc', 'RCC Roof'),
        ('sheet', 'Sheet Roof'),
        ('ground', 'Ground Mounted')
    ], string="Roof Type")

    survey_count = fields.Integer(
        compute="_compute_survey_count"
    )


    def _compute_survey_count(self):
        for rec in self:
            rec.survey_count = self.env[
                'solar.site.survey'
            ].search_count([
                ('lead_id', '=', rec.id)
            ])


    def action_view_surveys(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Site Surveys',
            'res_model': 'solar.site.survey',
            'view_mode': 'list,form',
            'domain': [
                ('lead_id', '=', self.id)
            ],
            'context': {
                'default_lead_id': self.id,
            }
        }

    def action_create_survey(self):

        self.ensure_one()
        survey = self.env[
            'solar.site.survey'
        ].create({
            'lead_id': self.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.site.survey',
            'res_id': survey.id,
            'view_mode': 'form',
            'target': 'current',
        }
