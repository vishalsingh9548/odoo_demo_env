# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds the document pack to the Project."""
    _inherit = 'project.project'

    epc_document_ids = fields.One2many('epc.project.document', 'project_id', string='Documents',
                                   help="The government / compliance papers of this project.")
    epc_document_count = fields.Integer(string='Documents', compute='_compute_epc_documents',
                                    help="How many papers this project has.")
    epc_document_done_count = fields.Integer(string='Documents Done', compute='_compute_epc_documents',
                                         help="Papers already submitted or accepted.")
    epc_document_pending_mandatory = fields.Integer(string='Mandatory Pending', compute='_compute_epc_documents',
                                                help="Mandatory papers not yet submitted or accepted.")
    epc_document_progress = fields.Float(string='Document Progress', compute='_compute_epc_documents',
                                     help="Percentage of papers submitted or accepted.")

    @api.depends('epc_document_ids.state', 'epc_document_ids.mandatory')
    def _compute_epc_documents(self):
        for project in self:
            docs = project.epc_document_ids
            done = docs.filtered(lambda d: d.state in ('submitted', 'accepted'))
            project.epc_document_count = len(docs)
            project.epc_document_done_count = len(done)
            project.epc_document_pending_mandatory = len((docs - done).filtered('mandatory'))
            project.epc_document_progress = 100.0 * len(done) / len(docs) if docs else 0.0

    # Creates the missing documents from the templates that match this project
    def _epc_create_documents(self, templates=None):
        self.ensure_one()
        segment = self.lead_id.customer_segment
        if templates is None:
            templates = self.env['epc.document.template'].search([('auto_create', '=', True)])
            templates = templates.filtered(lambda t: t.segment == 'all' or t.segment == segment)
        existing = self.epc_document_ids.mapped('template_id')
        vals = [{
            'project_id': self.id, 'template_id': t.id, 'name': t.name, 'sequence': t.sequence,
            'category': t.category, 'mandatory': t.mandatory,
        } for t in templates if t not in existing]
        return self.env['epc.project.document'].create(vals) if vals else self.env['epc.project.document']

    # Opens this project's documents
    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Documents', 'res_model': 'epc.project.document',
            'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
