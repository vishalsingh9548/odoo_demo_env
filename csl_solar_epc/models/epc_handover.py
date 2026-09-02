# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcHandover(models.Model):
    """Stage 14 of the EPC pipeline: Handover & Project Closure — the final
    paperwork step where documents are handed to the customer and the project
    is formally closed on the EPC company's side.
    """
    _name = 'epc.handover'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Handover & Project Closure'
    _order = 'id desc'

    name = fields.Char(
        string='Handover Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this handover record, e.g. HO/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project being handed over to the customer.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='project_id.partner_id', store=True,
        help="The customer receiving the handover.",
    )
    closure_date = fields.Date(
        string='Closure Date', default=fields.Date.context_today,
        help="The date the project was formally closed.",
    )

    as_built_drawing = fields.Binary(
        string='As-Built Drawings', help="The final drawings showing exactly what was built on site.",
    )
    as_built_drawing_filename = fields.Char(help="Original filename of the uploaded as-built drawings.")
    test_reports = fields.Binary(
        string='Test Reports', help="The electrical/performance test reports handed over to the customer.",
    )
    test_reports_filename = fields.Char(help="Original filename of the uploaded test reports.")
    om_manual = fields.Binary(
        string='O&M Manual', help="The Operations & Maintenance manual explaining how to look after the system.",
    )
    om_manual_filename = fields.Char(help="Original filename of the uploaded O&M manual.")
    warranty_certificate = fields.Binary(
        string='Warranty Certificate', help="The equipment/workmanship warranty certificate.",
    )
    warranty_certificate_filename = fields.Char(help="Original filename of the uploaded warranty certificate.")

    customer_training_done = fields.Boolean(
        string='Customer Training Done',
        help="Tick this once the customer has been trained on how to operate and monitor the system.",
    )
    customer_training_date = fields.Date(
        string='Customer Training Date', help="The date customer training took place.",
    )
    project_closure_report = fields.Html(
        string='Project Closure Report',
        help="A written summary of the completed project, for internal records.",
    )

    # Fills in the sequence-based reference number the first time a record is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.handover') or 'New'
        return super().create(vals_list)
