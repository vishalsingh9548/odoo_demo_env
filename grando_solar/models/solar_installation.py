from odoo import models, fields, api
from odoo.exceptions import UserError


class SolarInstallation(models.Model):
    _name = 'solar.installation'
    _description = 'Solar Installation Department Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Installation Reference",
        required=True,
        copy=False,
        default="New",
    )

    registration_id = fields.Many2one('solar.registration', string='Registration', required=True)
    lead_id = fields.Many2one(related='registration_id.lead_id', store=True, string='Lead')

    installation_manager_id = fields.Many2one(
        'res.users',
        string='Installation Manager',
        help="e.g. Praful Lakhani",
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('site_survey', 'Site Survey'),
        ('boq_bom', 'BOQ / BOM Creation'),
        ('material_dispatch', 'Material Dispatch Coordination'),
        ('structure_work', 'Structure Work'),
        ('wiring_work', 'Wiring Work'),
        ('solar_installation', 'Solar Installation'),
        ('work_inspection', 'Work Inspection'),
        ('completed', 'Completed'),
    ], default='draft', tracking=True, string='Installation Stage')

    # Site Survey
    site_survey_done = fields.Boolean(string='Site Survey Done')
    site_survey_date = fields.Datetime(string='Site Survey Date')

    # BOQ / BOM Creation
    boq_bom_done = fields.Boolean(string='BOQ/BOM Created')
    boq_bom_date = fields.Datetime(string='BOQ/BOM Date')
    bom_file = fields.Binary(string='BOQ/BOM File')
    bom_filename = fields.Char()

    # Material Dispatch Coordination
    material_dispatch_done = fields.Boolean(string='Material Dispatched')
    material_dispatch_date = fields.Datetime(string='Material Dispatch Date')

    # Structure Work Completion
    structure_work_done = fields.Boolean(string='Structure Work Done')
    structure_work_date = fields.Datetime(string='Structure Work Date')

    # Wiring Work Completion
    wiring_work_done = fields.Boolean(string='Wiring Work Done')
    wiring_work_date = fields.Datetime(string='Wiring Work Date')

    # Solar Installation Completion
    solar_installation_done = fields.Boolean(string='Solar Installation Done')
    solar_installation_date = fields.Datetime(string='Solar Installation Date')

    # Work Inspection
    work_inspection_done = fields.Boolean(string='Work Inspection Done')
    work_inspection_date = fields.Datetime(string='Work Inspection Date')
    inspected_by_id = fields.Many2one('res.users', string='Inspected By')

    # Completion Report Generated
    completion_report_generated = fields.Boolean(string='Completion Report Generated')
    completion_report_file = fields.Binary(string='Completion Report')
    completion_report_filename = fields.Char()
    completion_report_date = fields.Datetime(string='Completion Report Date')

    files_returned_to_registration = fields.Boolean(string='Files Returned to Registration Dept')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('solar.installation')
        return super().create(vals)

    def action_mark_site_survey_done(self):
        self.write({
            'site_survey_done': True,
            'site_survey_date': fields.Datetime.now(),
            'state': 'boq_bom',
        })

    def action_mark_boq_bom_done(self):
        self.write({
            'boq_bom_done': True,
            'boq_bom_date': fields.Datetime.now(),
            'state': 'material_dispatch',
        })

    def action_mark_material_dispatch_done(self):
        self.write({
            'material_dispatch_done': True,
            'material_dispatch_date': fields.Datetime.now(),
            'state': 'structure_work',
        })

    def action_mark_structure_work_done(self):
        self.write({
            'structure_work_done': True,
            'structure_work_date': fields.Datetime.now(),
            'state': 'wiring_work',
        })

    def action_mark_wiring_work_done(self):
        self.write({
            'wiring_work_done': True,
            'wiring_work_date': fields.Datetime.now(),
            'state': 'solar_installation',
        })

    def action_mark_solar_installation_done(self):
        self.write({
            'solar_installation_done': True,
            'solar_installation_date': fields.Datetime.now(),
            'state': 'work_inspection',
        })

    def action_mark_work_inspection_done(self):
        self.ensure_one()
        self.write({
            'work_inspection_done': True,
            'work_inspection_date': fields.Datetime.now(),
            'inspected_by_id': self.inspected_by_id.id or self.env.user.id,
            'completion_report_generated': True,
            'completion_report_date': fields.Datetime.now(),
            'state': 'completed',
        })

    def action_return_files_to_registration(self):
        """Stage 9: hand completed installation files back to the Registration Dept."""
        self.ensure_one()
        if self.state != 'completed':
            raise UserError("Installation must be Completed before files can be returned to Registration.")
        self.registration_id.action_receive_installation_files()
        self.write({'files_returned_to_registration': True})

    def action_view_registration(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.registration',
            'res_id': self.registration_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
