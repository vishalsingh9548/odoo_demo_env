from odoo import models, fields, api


class SolarDiscomActivation(models.Model):
    _name = 'solar.discom.activation'
    _description = 'DISCOM & Final Activation Process'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="DISCOM Reference",
        required=True,
        copy=False,
        default="New",
    )

    registration_id = fields.Many2one('solar.registration', string='Registration', required=True)
    lead_id = fields.Many2one(related='registration_id.lead_id', store=True, string='Lead')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted to DISCOM'),
        ('meter_installed', 'Meter Installation Completed'),
        ('activated', 'Solar System Activated'),
        ('procedure_explained', 'Procedure Explained to Client'),
        ('completed', 'Project Successfully Completed'),
    ], default='draft', tracking=True, string='DISCOM Stage')

    # Registration Team Submits File to DISCOM
    submitted_date = fields.Datetime(string='Submitted to DISCOM On')

    # Meter Installation Completed
    meter_installed_date = fields.Datetime(string='Meter Installation Date')

    # Sales Rep Activates Solar System
    activated_by_id = fields.Many2one('res.users', string='Activated By (Sales Rep)')
    activation_date = fields.Datetime(string='Activation Date')

    # Explains Procedure to Client
    procedure_explained_date = fields.Datetime(string='Procedure Explained On')

    # Project Successfully Completed
    project_completed_date = fields.Datetime(string='Project Completed On')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('solar.discom.activation')
        return super().create(vals)

    def action_submit_to_discom(self):
        self.write({'state': 'submitted', 'submitted_date': fields.Datetime.now()})

    def action_meter_installed(self):
        self.write({'state': 'meter_installed', 'meter_installed_date': fields.Datetime.now()})

    def action_activate_system(self):
        self.ensure_one()
        self.write({
            'state': 'activated',
            'activation_date': fields.Datetime.now(),
            'activated_by_id': self.activated_by_id.id or self.env.user.id,
        })

    def action_explain_procedure(self):
        self.write({'state': 'procedure_explained', 'procedure_explained_date': fields.Datetime.now()})

    def action_complete_project(self):
        self.write({'state': 'completed', 'project_completed_date': fields.Datetime.now()})
