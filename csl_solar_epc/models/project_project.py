# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Stage 7 of the EPC pipeline: the Project record is the hub that everything
    downstream (Procurement, Site Execution, DPRs, Quality Checks, Commissioning,
    Handover, AMC) attaches itself to. This file adds the solar-specific context
    fields and the trail back to where the project came from (Lead, BOQ, Order).
    """
    _inherit = 'project.project'

    lead_id = fields.Many2one(
        'crm.lead', string='Source Lead', copy=False,
        help="The original CRM lead that this solar project was won from.",
    )
    boq_id = fields.Many2one(
        'epc.boq', string='Source BOQ', copy=False,
        help="The Bill of Quantities this project's scope and pricing were based on.",
    )
    epc_sale_order_id = fields.Many2one(
        'sale.order', string='EPC Sales Order', copy=False,
        help="The confirmed Sales Order that created this project.",
    )
    capacity_kw = fields.Float(
        string='System Capacity (kW)', related='boq_id.capacity_kw', readonly=False,
        help="The total solar system size being installed under this project, "
             "taken live from its BOQ.",
    )
    site_address = fields.Text(
        string='Site Address', related='lead_id.site_address', readonly=False,
        help="The physical address where the solar system is being installed.",
    )
    scope_of_work = fields.Html(
        string='Scope of Work',
        help="A written description of exactly what is included in this project "
             "(supply, installation, testing, commissioning, etc.).",
    )
    boq_total_cost = fields.Monetary(
        string='Budgeted Cost', related='boq_id.total_cost', currency_field='currency_id',
        help="The total cost budgeted for this project, taken from its BOQ. Used "
             "for profitability and budget-vs-actual reporting.",
    )
    boq_total_sell_price = fields.Monetary(
        string='Contract Revenue', related='boq_id.total_sell_price', currency_field='currency_id',
        help="The total price the customer is being charged, taken from the BOQ. "
             "Used for revenue-vs-cost reporting.",
    )
    dpr_count = fields.Integer(
        string='DPR Count', compute='_compute_epc_related_counts',
        help="How many Daily Progress Reports have been logged for this project.",
    )
    quality_check_count = fields.Integer(
        string='Quality Check Count', compute='_compute_epc_related_counts',
        help="How many Quality Checks have been carried out on this project.",
    )
    material_request_count = fields.Integer(
        string='Material Request Count', compute='_compute_epc_related_counts',
        help="How many Material Requests have been raised for this project.",
    )
    site_location_id = fields.Many2one(
        'stock.location', string='Project Site Location', readonly=True, copy=False,
        help="The warehouse location representing this project's physical site. "
             "Created automatically the first time material is issued out to site, "
             "so incoming (Purchase Orders) and outgoing (site issues) stock moves "
             "for this project can both be tracked and reported on separately.",
    )

    # Opens the Sales Order this project was created from, called from the
    # "Sales Order" smart button — the reverse direction of the "EPC Project"
    # smart button already on the Sales Order form
    def action_view_epc_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.epc_sale_order_id.id,
            'target': 'current',
        }

    # Counts DPRs, Quality Checks and Material Requests linked to this project,
    # for the smart buttons on the project form
    def _compute_epc_related_counts(self):
        for project in self:
            project.dpr_count = self.env['epc.dpr'].search_count([('project_id', '=', project.id)])
            project.quality_check_count = self.env['epc.quality.check'].search_count(
                [('project_id', '=', project.id)])
            project.material_request_count = self.env['epc.material.request'].search_count(
                [('project_id', '=', project.id)])

    # Opens a new, blank Daily Progress Report pre-filled with this project,
    # so Stage 11 can be started directly from the project screen — the only
    # way in now that Daily Progress Reports has no top-level menu of its own
    def action_create_dpr(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.dpr',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    # Opens the Daily Progress Reports for this project, called from the smart button
    def action_view_dprs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Progress Reports',
            'res_model': 'epc.dpr',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    # Opens the Quality Checks for this project, called from the smart button
    def action_view_quality_checks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quality Checks',
            'res_model': 'epc.quality.check',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
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

    # Creates (or reuses) a dedicated stock location standing in for this
    # project's physical site, so material issued out of the warehouse to this
    # site can be tracked as a real, separate stock move instead of just
    # disappearing from the warehouse with no record of where it went
    def _epc_ensure_site_location(self):
        self.ensure_one()
        if self.site_location_id:
            return self.site_location_id
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id or self.env.company.id)], limit=1)
        parent_location = warehouse.lot_stock_id if warehouse else self.env.ref('stock.stock_location_stock')
        location = self.env['stock.location'].create({
            'name': f"{self.name} (Site)",
            'usage': 'internal',
            'location_id': parent_location.id,
        })
        self.site_location_id = location.id
        return location

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

    # Creates the standard set of milestones every solar project goes through, so
    # the project manager has a ready-made checklist instead of a blank project
    def _epc_seed_default_milestones(self):
        self.ensure_one()
        milestone_names = [
            'Material Procured',
            'Structure & Module Installation Complete',
            'Electrical Wiring & Testing Complete',
            'Commissioning & Handover Complete',
        ]
        self.env['project.milestone'].create([
            {'name': name, 'project_id': self.id} for name in milestone_names
        ])
