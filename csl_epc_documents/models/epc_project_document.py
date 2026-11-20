# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from .epc_document_template import DOCUMENT_CATEGORIES


class EpcProjectDocument(models.Model):
    """One paper to collect or file for one project, with its status and the
    signed scan attached."""
    _name = 'epc.project.document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Project Document'
    _order = 'project_id, sequence, id'

    name = fields.Char(string='Document', required=True, help="Name of the paper.")
    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, ondelete='cascade', index=True, tracking=True,
        help="The project this paper belongs to.",
    )
    partner_id = fields.Many2one('res.partner', string='Customer', related='project_id.partner_id', store=True,
                                 help="The customer of the project.")
    template_id = fields.Many2one('epc.document.template', string='Template', ondelete='set null',
                                  help="The template this document was created from.")
    category = fields.Selection(DOCUMENT_CATEGORIES, string='Category', required=True, default='other',
                                help="Which group of papers this belongs to.")
    mandatory = fields.Boolean(string='Mandatory', default=True, help="Must be done before the project can move on.")
    state = fields.Selection(
        [('pending', 'Pending'), ('ready', 'Ready'), ('submitted', 'Submitted'),
         ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        string='Status', default='pending', required=True, tracking=True, copy=False,
        help="Pending: not collected. Ready: collected and signed. Submitted: filed with the authority. "
             "Accepted: authority accepted it. Rejected: authority sent it back.",
    )
    due_date = fields.Date(string='Due Date', help="Date by which this paper should be filed.")
    scan = fields.Binary(string='Signed Scan', attachment=True, help="Scan of the signed paper.")
    scan_filename = fields.Char(string='Scan Filename')
    submitted_date = fields.Date(string='Submitted On', copy=False, help="Date the paper was filed.")
    remarks = fields.Text(string='Remarks', help="Notes, or the reason the authority rejected it.")
    is_overdue = fields.Boolean(string='Overdue', compute='_compute_is_overdue',
                                help="Past its due date and not yet submitted.")

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.is_overdue = bool(doc.due_date and doc.due_date < today and doc.state in ('pending', 'ready', 'rejected'))

    # Marks the paper as collected and signed
    def action_mark_ready(self):
        self._require(('pending', 'rejected'), 'marked Ready')
        self.write({'state': 'ready'})

    # Marks the paper as filed; a signed scan must be attached first
    def action_submit(self):
        self._require(('pending', 'ready', 'rejected'), 'submitted')
        for doc in self:
            if not doc.scan:
                raise UserError("Attach the signed scan of '%s' before marking it Submitted." % doc.name)
        self.write({'state': 'submitted', 'submitted_date': fields.Date.context_today(self)})

    # The authority accepted the paper
    def action_accept(self):
        self._require(('submitted',), 'accepted')
        self.write({'state': 'accepted'})

    # The authority sent the paper back; the reason goes in Remarks
    def action_reject(self):
        self._require(('submitted',), 'rejected')
        for doc in self:
            if not doc.remarks:
                raise UserError("Write the reason in Remarks before marking '%s' Rejected." % doc.name)
        self.write({'state': 'rejected'})

    # Back to the start
    def action_reset(self):
        self.write({'state': 'pending', 'submitted_date': False})

    def _require(self, states, action):
        for doc in self:
            if doc.state not in states:
                raise UserError("'%s' cannot be %s while it is %s." % (
                    doc.name, action, dict(self._fields['state'].selection).get(doc.state)))

    # Prints the auto-filled form
    def action_print_form(self):
        self.ensure_one()
        return self.env.ref('csl_epc_documents.action_report_epc_document').report_action(self)
