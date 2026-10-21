# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds the BOQ trail (source BOQ, capacity, budgeted cost / contract revenue) to the Project."""
    _inherit = 'project.project'

    boq_id = fields.Many2one(
        'epc.boq', string='Source BOQ', copy=False,
        help="The Bill of Quantities this project's scope and pricing were based on.",
    )
    capacity_kw = fields.Float(
        string='System Capacity (kW)', related='boq_id.capacity_kw', readonly=False,
        help="The total solar system size being installed under this project, "
             "taken live from its BOQ.",
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
