# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcHandover(models.Model):
    """When the "Handover Needs Approved Commissioning" switch is on, a handover can
    only be approved once the project's commissioning has been approved."""
    _inherit = 'epc.handover'

    commissioning_date = fields.Date(
        string='Commissioned On', compute='_compute_days_from_commissioning',
        help="Date of the project's commissioning.",
    )
    days_from_commissioning = fields.Float(
        string='Days After Commissioning', compute='_compute_days_from_commissioning', digits=(16, 1),
        help="Days between the project's commissioning and this handover's closure date. Shown in "
             "the list so the dashboard's 'Commissioning to handover' can be checked.",
    )

    @api.depends('project_id', 'closure_date')
    def _compute_days_from_commissioning(self):
        Commissioning = self.env['epc.commissioning'].sudo()
        for handover in self:
            comm = Commissioning.search([
                ('project_id', '=', handover.project_id.id), ('commissioning_date', '!=', False),
            ], limit=1)
            handover.commissioning_date = comm.commissioning_date
            handover.days_from_commissioning = (
                (handover.closure_date - comm.commissioning_date).days
                if comm and handover.closure_date else 0.0)

    def action_approve(self):
        if self.env['epc.config'].flag('handover_require_commissioning'):
            for handover in self:
                approved = self.env['epc.commissioning'].sudo().search_count([
                    ('project_id', '=', handover.project_id.id),
                    ('approval_state', '=', 'approved'),
                ])
                if not approved:
                    raise UserError("This project has no approved commissioning yet.")
        return super().action_approve()
