# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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

    epc_material_to_issue = fields.Boolean(
        string='Material To Issue', compute='_compute_epc_material_to_issue',
        help="True while an approved material request of this project still has stock "
             "in the warehouse that has not been issued to the site - drives the "
             "'Issue Material to Site' button on the project.",
    )

    # Works out whether any approved request of this project still has material
    # that could be issued to the site right now
    def _compute_epc_material_to_issue(self):
        for project in self:
            requests = self.env['epc.material.request'].search([
                ('project_id', '=', project.id), ('approval_state', '=', 'approved')])
            project.epc_material_to_issue = any(requests.mapped('epc_has_issuable'))

    # Issues, in one click, the material of every approved request of this
    # project that can be issued now (so it is not forgotten on the request itself)
    def action_issue_material_to_site(self):
        self.ensure_one()
        requests = self.env['epc.material.request'].search([
            ('project_id', '=', self.id), ('approval_state', '=', 'approved')]).filtered('epc_has_issuable')
        if not requests:
            raise UserError(
                "There is nothing to issue to the site: either no material request of this "
                "project is approved, everything has already been issued, or the warehouse "
                "has no stock of the requested products yet.")
        picking_ids = []
        for request in requests:
            picking_ids.append(request.action_issue_to_project()['res_id'])
        if len(picking_ids) == 1:
            return {
                'type': 'ir.actions.act_window', 'res_model': 'stock.picking',
                'view_mode': 'form', 'res_id': picking_ids[0], 'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window', 'name': 'Material Issued to Site',
            'res_model': 'stock.picking', 'view_mode': 'list,form',
            'domain': [('id', 'in', picking_ids)],
        }

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
            for line in self.sudo().boq_id.line_ids if line.product_id
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
