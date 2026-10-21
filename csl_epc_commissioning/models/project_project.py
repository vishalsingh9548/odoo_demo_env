# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds the Commissioning count, 'all tasks done' flag and 'Proceed to Commissioning' action to the Project."""
    _inherit = 'project.project'

    commissioning_count = fields.Integer(
        string='Commissioning Count', compute='_compute_commissioning_count',
        help="How many Commissioning records exist for this project.",
    )
    epc_all_tasks_done = fields.Boolean(
        string='All Tasks Done', compute='_compute_epc_all_tasks_done',
        help="True once this project has at least one task and every one of "
             "them is closed (done or cancelled) — drives the 'Proceed to "
             "Commissioning' button, so Commissioning only gets suggested "
             "once site execution is actually finished.",
    )
    # Counts Commissioning records linked to this project, for the smart button on the project form
    def _compute_commissioning_count(self):
        for project in self:
            project.commissioning_count = self.env['epc.commissioning'].search_count([('project_id', '=', project.id)])

    # Works out whether every task on this project has actually been
    # finished (or cancelled) — a project with no tasks at all doesn't count
    # as "done", it just hasn't started. Deliberately searches project.task
    # directly rather than using the project's own task_ids field: that
    # field's own domain excludes closed tasks, so it goes empty the moment
    # everything is actually done — exactly the case this needs to detect.
    def _compute_epc_all_tasks_done(self):
        for project in self:
            tasks = self.env['project.task'].search([('project_id', '=', project.id)])
            project.epc_all_tasks_done = bool(tasks) and all(tasks.mapped('is_closed'))

    # Opens a new, blank Commissioning record pre-filled with this project,
    # so Stage 13 can be started directly from the project screen the moment
    # site execution actually finishes — called from the "Proceed to
    # Commissioning" header button, which only shows once every task is done
    def action_create_commissioning(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.commissioning',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    # Opens the Commissioning record(s) of this project, called from the smart
    # button: straight into the record when there is only one
    def action_view_commissionings(self):
        self.ensure_one()
        records = self.env['epc.commissioning'].search([('project_id', '=', self.id)])
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Commissioning',
            'res_model': 'epc.commissioning',
            'context': {'default_project_id': self.id},
        }
        if len(records) == 1:
            action.update({'view_mode': 'form', 'res_id': records.id})
        else:
            action.update({'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)]})
        return action

