# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds Material Requests (count, smart button, BOQ-prefilled creation) to the Project."""
    _inherit = 'project.project'

    material_request_count = fields.Integer(
        string='Material Request Count', compute='_compute_material_request_count',
        help="How many Material Requests have been raised for this project.",
    )
    # Counts Material Requests linked to this project, for the smart button on the project form
    def _compute_material_request_count(self):
        for project in self:
            project.material_request_count = self.env['epc.material.request'].search_count([('project_id', '=', project.id)])

    # Creates a new Material Request for this project and, like ibsolar's own
    # material requisition screen, automatically lists every material the BOQ
    # says is needed — so Procurement (Stage 8A) starts pre-filled with what to
    # buy instead of a blank form the user has to rebuild from the BOQ by hand
    def action_create_material_request(self):
        self.ensure_one()
        line_vals = [
            (0, 0, {
                'product_id': line.product_id.id,
                'description': line.description,
                'quantity_required': line.quantity,
                'uom_id': line.uom_id.id,
            })
            for line in self.boq_id.line_ids if line.product_id
        ]
        request = self.env['epc.material.request'].create({
            'project_id': self.id,
            'line_ids': line_vals,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.material.request',
            'view_mode': 'form',
            'res_id': request.id,
            'target': 'current',
        }

    # Opens the Material Requests for this project, called from the smart button
    def action_view_material_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Material Requests',
            'res_model': 'epc.material.request',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
