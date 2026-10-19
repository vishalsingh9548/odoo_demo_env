# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcBoq(models.Model):
    """Stage 4 of the EPC pipeline: the Bill of Quantities — a detailed,
    itemised costing sheet (modules, inverters, structures, cabling, civil
    work, labour, logistics, overheads) that adds up to the price that will
    be quoted to the customer.
    """
    _name = 'epc.boq'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Bill of Quantities & Costing'
    _order = 'id desc'

    name = fields.Char(
        string='BOQ Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this costing sheet, e.g. BOQ/2026/00001.",
    )
    feasibility_id = fields.Many2one(
        'epc.feasibility', string='Feasibility Study', tracking=True,
        help="The Technical Feasibility study this costing is based on.",
    )
    lead_id = fields.Many2one(
        'crm.lead', string='Lead / Opportunity', tracking=True,
        help="The CRM lead this BOQ belongs to.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer', related='lead_id.partner_id', store=True,
        help="The customer this costing sheet is being prepared for.",
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', default=lambda self: self.env.company.currency_id,
        help="The currency all amounts on this BOQ are expressed in.",
    )
    capacity_kw = fields.Float(
        string='System Capacity (kW)', related='feasibility_id.proposed_capacity_kw', readonly=False,
        help="The solar system size this costing sheet is for.",
    )

    line_ids = fields.One2many(
        'epc.boq.line', 'boq_id', string='BOQ Lines',
        help="The itemised list of every material, service and cost that makes up this quote.",
    )
    total_cost = fields.Monetary(
        string='Total Cost', compute='_compute_totals', store=True, currency_field='currency_id',
        help="The sum of every line's cost — what this project costs the company to deliver.",
    )
    margin_percent = fields.Float(
        string='Margin (%)', default=15.0,
        help="The profit margin to add on top of the total cost to arrive at the "
             "customer-facing sell price.",
    )
    total_sell_price = fields.Monetary(
        string='Total Sell Price', compute='_compute_totals', store=True, currency_field='currency_id',
        help="The final price to quote the customer: total cost plus margin.",
    )

    sale_order_id = fields.Many2one(
        'sale.order', string='Quotation', copy=False, readonly=True,
        help="The Sales Quotation generated from this BOQ, once approved.",
    )

    # Fills in the sequence-based reference number the first time a BOQ is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.boq') or 'New'
        return super().create(vals_list)

    # Adds up every BOQ line's cost, then applies the margin to work out the sell price
    @api.depends('line_ids.subtotal', 'margin_percent')
    def _compute_totals(self):
        for boq in self:
            boq.total_cost = sum(boq.line_ids.mapped('subtotal'))
            boq.total_sell_price = boq.total_cost * (1 + (boq.margin_percent or 0.0) / 100.0)

    # Turns this approved BOQ into a real Sales Quotation, copying every BOQ line
    # into a sale order line so the customer-facing price matches the costing sheet
    def action_create_quotation(self):
        self.ensure_one()
        order_lines = []
        for line in self.line_ids:
            unit_sell_price = line.unit_cost * (1 + (self.margin_percent or 0.0) / 100.0)
            order_lines.append((0, 0, {
                'product_id': line.product_id.id if line.product_id else False,
                'name': line.description or (line.product_id.display_name if line.product_id else ''),
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id if line.uom_id else False,
                'price_unit': unit_sell_price,
            }))
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'boq_id': self.id,
            'opportunity_id': self.lead_id.id,
            'order_line': order_lines,
        })
        self.sale_order_id = order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': order.id,
            'target': 'current',
        }

    # Opens the Quotation generated from this BOQ, called from the "View Quotation" button
    def action_view_quotation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
            'target': 'current',
        }


class EpcBoqLine(models.Model):
    """One priced item on a Bill of Quantities — for example '10 solar modules
    of 540W' or '200 metres of DC cable'.
    """
    _name = 'epc.boq.line'
    _description = 'Solar BOQ Line'
    _order = 'sequence, id'

    sequence = fields.Integer(
        string='Sequence', default=10,
        help="Controls the display order of lines on the BOQ.",
    )
    boq_id = fields.Many2one(
        'epc.boq', string='BOQ', required=True, ondelete='cascade',
        help="The BOQ this line belongs to.",
    )
    category = fields.Selection(
        [
            ('solar_module', 'Solar Modules'),
            ('inverter', 'Inverters'),
            ('mounting_structure', 'Mounting Structures'),
            ('dc_cable', 'DC Cables'),
            ('ac_cable', 'AC Cables'),
            ('lt_panel_db', 'LT Panels / DB'),
            ('earthing_material', 'Earthing Material'),
            ('civil_work', 'Civil Work'),
            ('manpower', 'Manpower / Labour'),
            ('logistics', 'Logistics'),
            ('overheads', 'Overheads'),
            ('other', 'Other'),
        ],
        string='Category', required=True,
        help="What kind of material or cost this line represents — used to group "
             "and report BOQ costs by type.",
    )
    product_id = fields.Many2one(
        'product.product', string='Product',
        help="The specific product this line refers to, if it maps to one in "
             "the product catalogue (optional for pure cost lines like Civil Work).",
    )
    description = fields.Char(
        string='Description',
        help="A short description of this line item, shown to the team preparing "
             "the quotation.",
    )
    quantity = fields.Float(
        string='Quantity', default=1.0,
        help="How many units of this item are needed.",
    )
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure',
        help="The unit this quantity is measured in (pieces, metres, kilograms, etc.).",
    )
    unit_cost = fields.Float(
        string='Unit Cost',
        help="What one unit of this item costs the company (before margin).",
    )
    subtotal = fields.Float(
        string='Subtotal', compute='_compute_subtotal', store=True,
        help="Quantity multiplied by unit cost — this line's total cost.",
    )

    # Multiplies quantity by unit cost to get this line's total cost
    @api.depends('quantity', 'unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost
