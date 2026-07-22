from odoo import models, fields, api

class SolarSiteSurvey(models.Model):
    _name = 'solar.site.survey'
    _description = 'Solar Site Survey'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Survey Reference",
        required=True,
        copy=False,
        default="New"
    )

    lead_id = fields.Many2one(
        'crm.lead',
        string="Lead"
    )

    survey_date = fields.Date(
        string="Survey Date"
    )

    engineer_id = fields.Many2one(
        'res.users',
        string="Survey Engineer"
    )

    roof_area = fields.Float(
        string="Roof Area (sqft)"
    )

    roof_type = fields.Selection([
        ('rcc','RCC'),
        ('sheet','Sheet'),
        ('ground','Ground Mounted')
    ])

    monthly_consumption = fields.Float(
        string="Monthly Consumption"
    )

    shadow_analysis = fields.Text()

    latitude = fields.Char()

    longitude = fields.Char()

    state = fields.Selection([
        ('draft','Draft'),
        ('done','Completed')
    ], default='draft')

    design_count = fields.Integer(
        compute="_compute_design_count"
    )
    
    def _compute_design_count(self):

        for rec in self:

            rec.design_count = self.env[
                'solar.design'
            ].search_count([
                ('survey_id','=',rec.id)
            ])


    @api.model
    def create(self, vals):

        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env[
                'ir.sequence'
            ].next_by_code(
                'solar.site.survey'
            )

        return super().create(vals)


    def action_create_design(self):

        self.ensure_one()
        design = self.env[
            'solar.design'
        ].create({
            'survey_id': self.id
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.design',
            'res_id': design.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_designs(self):

        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Designs',
            'res_model': 'solar.design',
            'view_mode': 'list,form',
            'domain': [
                ('survey_id', '=', self.id)
            ],
            'context': {
                'default_survey_id': self.id,
            },
        }
