# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Stage 7: the Project is the hub every downstream EPC document attaches to. Core part: the trail back to the source Lead / Sales Order, site address, scope and site stock location."""
    _inherit = 'project.project'

    lead_id = fields.Many2one(
        'crm.lead', string='Source Lead', copy=False,
        help="The original CRM lead that this solar project was won from.",
    )
    epc_sale_order_id = fields.Many2one(
        'sale.order', string='EPC Sales Order', copy=False,
        help="The confirmed Sales Order that created this project.",
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
