# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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
    cost_per_kw = fields.Monetary(
        string='Cost per kW', compute='_compute_cost_per_kw', currency_field='currency_id',
        help="Total cost divided by system capacity. Shown in the list so the dashboard's "
             "Avg cost per kW can be compared BOQ by BOQ.",
    )

    @api.depends('total_cost', 'capacity_kw')
    def _compute_cost_per_kw(self):
        for boq in self:
            boq.cost_per_kw = boq.total_cost / boq.capacity_kw if boq.capacity_kw else 0.0

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

    revision_number = fields.Integer(
        string='Revision', default=1, copy=False,
        help="1 for the first version of this BOQ; each time it is revised after approval the new copy gets the next number.",
    )
    revision_of_id = fields.Many2one(
        'epc.boq', string='Revision Of', copy=False, readonly=True,
        help="The earlier version of the BOQ this one was revised from.",
    )
    older_version_count = fields.Integer(
        string='Older Versions', compute='_compute_older_versions',
        help="How many earlier versions this BOQ was revised from (the whole chain back to version 1).",
    )

    def _older_versions(self):
        """The chain of earlier versions of this BOQ, newest first."""
        self.ensure_one()
        chain, current = self.browse(), self.revision_of_id
        while current and current not in chain:
            chain |= current
            current = current.revision_of_id
        return chain

    @api.depends('revision_of_id')
    def _compute_older_versions(self):
        for boq in self:
            boq.older_version_count = len(boq._older_versions())

    superseded = fields.Boolean(
        string='Superseded', copy=False, readonly=True,
        help="Ticked automatically on the old version once a newer revision exists; "
             "no new quotation can be created from it.",
    )
    quotation_state = fields.Selection(
        related='sale_order_id.state', string='Quotation Status',
        help="Status of the linked quotation / sales order.",
    )

    # These stay editable on an approved BOQ even when approved documents are locked
    _epc_lock_whitelist = ('sale_order_id', 'superseded')

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

    # Checks the BOQ is fit to be quoted: approved, not replaced by a newer
    # revision, has lines and (when the Strict BOQ Check switch is on) every
    # line has a product and a unit cost
    def _epc_check_quotation_ready(self):
        self.ensure_one()
        if self.approval_state != 'approved':
            raise UserError("Approve the BOQ before creating a quotation.")
        if self.superseded:
            raise UserError("A newer revision of this BOQ exists - create the quotation from that one.")
        if not self.line_ids:
            raise UserError("This BOQ has no lines yet, so there is nothing to quote.")
        if self.env['epc.config'].flag('strict_boq'):
            service_categories = ('civil_work', 'manpower', 'logistics', 'overheads', 'other')
            problems = []
            for line in self.line_ids:
                name = line.description or line.category
                if not line.product_id and line.category not in service_categories:
                    problems.append("%s: no product" % name)
                if not line.unit_cost and not line.zero_cost_ok:
                    problems.append("%s: no unit cost (tick 'Zero cost is correct' if that is right)" % name)
            if problems:
                raise UserError("Fix these BOQ lines before creating a quotation:\n- " + "\n- ".join(problems))

    # Builds the sale order lines for this BOQ (cost plus margin)
    def _epc_quotation_lines(self):
        self.ensure_one()
        order_lines = []
        for line in self.line_ids:
            unit_sell_price = line.unit_cost * (1 + (self.margin_percent or 0.0) / 100.0)
            order_lines.append((0, 0, {
                'product_id': line.product_id.id if line.product_id else False,
                'name': line.description or (line.product_id.display_name if line.product_id else ''),
                'product_uom_qty': line.quantity,
                # a line without its own unit takes the product's unit, so the order line is complete
                'product_uom': (line.uom_id or line.product_id.uom_id).id or False,
                'price_unit': unit_sell_price,
                # Odoo treats a price that differs from "technical_price_unit" as typed by
                # hand and keeps it; without this, changing the unit of measure or the
                # quantity would reset the BOQ price to the product's list price
                'technical_price_unit': -1.0,
            }))
        return order_lines

    # Turns this approved BOQ into a real Sales Quotation, copying every BOQ line
    # into a sale order line so the customer-facing price matches the costing sheet
    def action_create_quotation(self):
        self.ensure_one()
        self._epc_check_quotation_ready()
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'boq_id': self.id,
            'opportunity_id': self.lead_id.id,
            'is_epc_order': True,
            'order_line': self._epc_quotation_lines(),
        })
        self.sale_order_id = order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': order.id,
            'target': 'current',
        }

    # While the quotation is still a draft, refreshes its lines from the BOQ
    # (after the BOQ was corrected) instead of having to start a new quotation
    def action_sync_quotation(self):
        self.ensure_one()
        order = self.sale_order_id
        if not order or order.state not in ('draft', 'sent'):
            raise UserError("Only a quotation that is still a draft can be refreshed from the BOQ.")
        order.order_line.unlink()
        order.write({'order_line': self._epc_quotation_lines()})
        self.message_post(body="Quotation %s refreshed from this BOQ." % order.name)

    # Makes a new, editable copy of this approved BOQ (revision N+1) and marks
    # this one as superseded, keeping the old version as history
    def action_revise(self):
        self.ensure_one()
        self._epc_check_manager()
        if self.approval_state != 'approved':
            raise UserError("Only an approved BOQ can be revised. Edit it directly while it is still a draft.")
        if self.sale_order_id and self.sale_order_id.state not in ('draft', 'sent', 'cancel'):
            raise UserError("The quotation of this BOQ is already confirmed, so it cannot be revised.")
        new = self.copy({
            'revision_of_id': self.id,
            'revision_number': self.revision_number + 1,
            'line_ids': [(0, 0, {
                'sequence': line.sequence, 'category': line.category,
                'product_id': line.product_id.id, 'description': line.description,
                'quantity': line.quantity, 'uom_id': line.uom_id.id,
                'unit_cost': line.unit_cost, 'zero_cost_ok': line.zero_cost_ok,
            }) for line in self.line_ids],
        })
        self.superseded = True
        self.message_post(body="Revised: new version %s created." % new.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.boq',
            'view_mode': 'form',
            'res_id': new.id,
            'target': 'current',
        }

    # Opens the earlier versions of this BOQ, called from the "Older Versions" smart button
    def action_view_older_versions(self):
        self.ensure_one()
        older = self._older_versions()
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Older Versions of %s' % self.name,
            'res_model': 'epc.boq',
            'target': 'current',
        }
        if len(older) == 1:
            action.update({'view_mode': 'form', 'res_id': older.id})
        else:
            action.update({'view_mode': 'list,form', 'domain': [('id', 'in', older.ids)]})
        return action

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

    zero_cost_ok = fields.Boolean(
        string='Zero Cost Is Correct',
        help="Tick this when a line really has no cost (e.g. supplied free), so the "
             "Strict BOQ Check does not complain about the missing unit cost.",
    )

    # Stops line changes on an approved BOQ when "Lock Approved Documents" is on
    def _epc_check_boq_unlocked(self):
        if not self.env.su and self.env['epc.config'].flag('lock_approved'):
            if any(line.boq_id.approval_state == 'approved' for line in self):
                raise UserError("This BOQ is approved and locked. Use Reopen (Reset to Draft) first.")

    # Picking a product fills the unit cost from the product's own cost
    @api.onchange('product_id')
    def _onchange_product_id_set_cost(self):
        if self.product_id:
            self.unit_cost = self.product_id.standard_price

    @api.model_create_multi
    def create(self, vals_list):
        # A line created with a product but no cost takes the product's cost
        for vals in vals_list:
            if vals.get('product_id') and 'unit_cost' not in vals:
                vals['unit_cost'] = self.env['product.product'].browse(vals['product_id']).standard_price
        if not self.env.su and self.env['epc.config'].flag('lock_approved'):
            boq_ids = [vals.get('boq_id') for vals in vals_list if vals.get('boq_id')]
            if boq_ids and self.env['epc.boq'].browse(boq_ids).filtered(lambda b: b.approval_state == 'approved'):
                raise UserError("This BOQ is approved and locked. Use Reopen (Reset to Draft) first.")
        return super().create(vals_list)

    def write(self, vals):
        self._epc_check_boq_unlocked()
        return super().write(vals)

    def unlink(self):
        self._epc_check_boq_unlocked()
        return super().unlink()

    # Multiplies quantity by unit cost to get this line's total cost
    @api.depends('quantity', 'unit_cost')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_cost
