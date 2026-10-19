# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcMaterialRequest(models.Model):
    """Stage 8A of the EPC pipeline: the bridge between 'what the BOQ says we
    need' and 'what we actually have to buy'. A site engineer or project
    manager lists what's needed, the sheet is approved, and whatever isn't
    already in stock is turned into real Purchase Orders (Requests for Quote).
    """
    _name = 'epc.material.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'epc.approval.mixin']
    _description = 'Solar Material Request'
    _order = 'id desc'

    name = fields.Char(
        string='Request Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this material request, e.g. MR/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project this material is needed for.",
    )
    requested_by = fields.Many2one(
        'res.users', string='Requested By', default=lambda self: self.env.user,
        help="The person raising this material request.",
    )
    request_date = fields.Date(
        string='Request Date', default=fields.Date.context_today,
        help="The date this material request was raised.",
    )
    line_ids = fields.One2many(
        'epc.material.request.line', 'request_id', string='Lines',
        help="Each material needed, how much is needed, and how much is already in stock.",
    )
    purchase_order_ids = fields.One2many(
        'purchase.order', 'material_request_id', string='Purchase Orders',
        help="The Purchase Orders raised from this material request's shortfall.",
    )
    epc_has_shortfall = fields.Boolean(
        string='Has Shortfall', compute='_compute_epc_flags',
        help="True while some line is still short of stock and not yet covered by a purchase order.",
    )
    epc_has_issuable = fields.Boolean(
        string='Has Issuable Stock', compute='_compute_epc_flags',
        help="True while some line still has stock on hand that has not been issued to the project.",
    )
    issue_status = fields.Selection(
        [('none', 'Nothing Issued'), ('partial', 'Partly Issued'), ('full', 'Fully Issued')],
        string='Issue Status', compute='_compute_issue_status',
        help="How much of the request has been moved out to the project site.",
    )
    purchase_order_count = fields.Integer(
        string='Purchase Order Count', compute='_compute_purchase_order_count',
        help="How many Purchase Orders have been created from this request.",
    )

    # Fills in the sequence-based reference number the first time a request is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.material.request') or 'New'
        return super().create(vals_list)

    # Counts the Purchase Orders linked to this request, for the smart button on the form
    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for request in self:
            request.purchase_order_count = len(request.purchase_order_ids)

    # Whether anything is still left to buy / to issue, for the buttons on the form
    @api.depends('line_ids.quantity_remaining_to_order', 'line_ids.quantity_issuable')
    def _compute_epc_flags(self):
        for request in self:
            request.epc_has_shortfall = any(line.quantity_remaining_to_order > 0 for line in request.line_ids)
            request.epc_has_issuable = any(line.quantity_issuable > 0 for line in request.line_ids)

    # Where this request stands on moving material to site: nothing / part / all issued
    @api.depends('line_ids.quantity_issued', 'line_ids.quantity_required')
    def _compute_issue_status(self):
        for request in self:
            lines = request.line_ids
            if not lines or not any(line.quantity_issued > 0 for line in lines):
                request.issue_status = 'none'
            elif all(line.quantity_issued >= line.quantity_required for line in lines):
                request.issue_status = 'full'
            else:
                request.issue_status = 'partial'

    # Creates one draft RFQ per preferred vendor for whatever is still short of
    # stock and not yet on an order, and links each to this request. Lines with
    # no preferred vendor cannot be put on an RFQ automatically (a vendor is
    # required), so they open as a pre-filled new RFQ for the buyer to complete,
    # exactly as before. Can be clicked again while some shortfall remains.
    def action_create_purchase_orders(self):
        self.ensure_one()
        shortfall_lines = self.line_ids.filtered(lambda line: line.quantity_remaining_to_order > 0)
        if not shortfall_lines:
            raise UserError("Every line on this request is already covered by stock on hand or "
                            "by a purchase order - there is nothing left to purchase.")

        def order_line_vals(lines):
            return [(0, 0, {
                'product_id': line.product_id.id,
                'name': line.description or line.product_id.display_name,
                'product_qty': line.quantity_remaining_to_order,
                'product_uom': line.uom_id.id if line.uom_id else line.product_id.uom_po_id.id,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }) for line in lines]

        created = self.env['purchase.order']
        with_vendor = shortfall_lines.filtered('vendor_id')
        for vendor in with_vendor.mapped('vendor_id'):
            created |= self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'project_id': self.project_id.id,
                'material_request_id': self.id,
                'order_line': order_line_vals(with_vendor.filtered(lambda line: line.vendor_id == vendor)),
            })
        no_vendor = shortfall_lines - with_vendor
        if created:
            self.message_post(body="Draft RFQs created: %s" % ", ".join(created.mapped('name')))
        if not no_vendor:
            if len(created) == 1:
                return {
                    'type': 'ir.actions.act_window', 'res_model': 'purchase.order',
                    'view_mode': 'form', 'res_id': created.id, 'target': 'current',
                }
            return {
                'type': 'ir.actions.act_window', 'name': 'Purchase Orders',
                'res_model': 'purchase.order', 'view_mode': 'list,form',
                'domain': [('id', 'in', created.ids)],
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_material_request_id': self.id,
                'default_order_line': order_line_vals(no_vendor),
            },
        }

    # Moves whatever's already sitting in the warehouse straight out to this
    # project's site as a real, trackable stock transfer - this is Stage 8B's
    # "Material Issue (To Project)" step. Only what has not already been issued
    # is moved, so pressing it twice never sends the same material twice.
    def action_issue_to_project(self):
        self.ensure_one()
        lines_to_issue = self.line_ids.filtered(lambda line: line.quantity_issuable > 0)
        if not lines_to_issue:
            if self.line_ids and all(line.quantity_issued >= line.quantity_required for line in self.line_ids):
                raise UserError("Everything on this request has already been issued to the project.")
            raise UserError("None of these lines have any stock on hand yet to issue.")
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        site_location = self.project_id._epc_ensure_site_location()
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': site_location.id,
            'origin': self.name,
            'project_id': self.project_id.id,
            'move_ids': [(0, 0, {
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity_issuable,
                'product_uom': line.uom_id.id if line.uom_id else line.product_id.uom_id.id,
                'location_id': warehouse.lot_stock_id.id,
                'location_dest_id': site_location.id,
            }) for line in lines_to_issue],
        })
        picking.action_confirm()
        picking.action_assign()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }

    # Checks the request does not ask for more of a product than the project's
    # BOQ allows (across all this project's open requests): a warning in the
    # chatter, or a hard stop when the "Block Over-BOQ Requests" switch is on
    def _epc_check_boq_limits(self):
        self.ensure_one()
        boq = self.project_id.sudo().boq_id
        if not boq:
            return
        allowed = {}
        for boq_line in boq.line_ids.filtered('product_id'):
            allowed[boq_line.product_id.id] = allowed.get(boq_line.product_id.id, 0.0) + boq_line.quantity
        others = self.sudo().search([
            ('project_id', '=', self.project_id.id), ('id', '!=', self.id),
            ('approval_state', 'in', ('submitted', 'approved')),
        ])
        requested = {}
        for line in (others | self.sudo()).mapped('line_ids'):
            requested[line.product_id.id] = requested.get(line.product_id.id, 0.0) + line.quantity_required
        over = [
            "%s: requested %s, BOQ allows %s" % (
                self.env['product.product'].browse(pid).display_name, qty, allowed[pid])
            for pid, qty in requested.items()
            if pid in allowed and qty > allowed[pid] + 1e-6 and pid in self.line_ids.mapped('product_id').ids
        ]
        if not over:
            return
        if self.env['epc.config'].flag('mr_block_over_boq'):
            raise UserError("This request goes beyond the project's BOQ:\n- " + "\n- ".join(over))
        self.message_post(body=Markup("Warning - more than the BOQ allows:<br/>") +
                          Markup("<br/>").join(escape(line) for line in over))

    # Submitting also checks the BOQ limits
    def action_submit(self):
        for request in self:
            request._epc_check_boq_limits()
        return super().action_submit()

    # Opens the Purchase Orders linked to this request, called from the
    # "Purchase Orders" smart button
    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('material_request_id', '=', self.id)],
        }


class EpcMaterialRequestLine(models.Model):
    """One material line on a Material Request — how much of a product is
    needed, how much is already in stock, and therefore how much still needs
    to be purchased.
    """
    _name = 'epc.material.request.line'
    _description = 'Solar Material Request Line'
    _order = 'id'

    request_id = fields.Many2one(
        'epc.material.request', string='Material Request', required=True, ondelete='cascade',
        help="The material request this line belongs to.",
    )
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        help="The material or equipment needed.",
    )
    description = fields.Char(
        string='Description',
        help="A short note about this line, shown on the Purchase Order if one is raised.",
    )
    quantity_required = fields.Float(
        string='Quantity Required', default=1.0,
        help="How much of this product the project needs in total.",
    )
    uom_id = fields.Many2one(
        'uom.uom', string='Unit of Measure',
        help="The unit this quantity is measured in.",
    )
    quantity_on_hand = fields.Float(
        string='Quantity On Hand', compute='_compute_quantity_on_hand',
        help="Stock that is free right now (on hand minus what is already reserved for other transfers).",
    )
    quantity_to_purchase = fields.Float(
        string='Quantity To Purchase', compute='_compute_quantity_on_hand',
        help="How much more has to be bought to cover what this line requires.",
    )
    quantity_ordered = fields.Float(
        string='Quantity Ordered', compute='_compute_quantity_ordered',
        help="How much of this product is already on this request's purchase orders.",
    )
    quantity_remaining_to_order = fields.Float(
        string='Still To Order', compute='_compute_quantity_ordered',
        help="Shortfall not yet covered by a purchase order.",
    )
    quantity_issued = fields.Float(
        string='Quantity Issued', compute='_compute_quantity_issued',
        help="How much has already been moved out to the project site for this request.",
    )
    quantity_issuable = fields.Float(
        string='Can Issue Now', compute='_compute_quantity_issued',
        help="How much could be issued to the project right now.",
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Preferred Vendor',
        help="Who to buy this from. If left blank, the product's default vendor is used.",
    )

    # Looks up how much stock is free (on hand minus reserved) for this product,
    # and works out how much more needs to be purchased to cover what is required
    @api.depends('product_id', 'quantity_required')
    def _compute_quantity_on_hand(self):
        for line in self:
            line.quantity_on_hand = line.product_id.free_qty if line.product_id else 0.0
            line.quantity_to_purchase = max(line.quantity_required - line.quantity_on_hand, 0.0)

    # How much is already on this request's purchase orders, and so how much
    # of the shortfall is still left to order
    @api.depends('product_id', 'quantity_required', 'request_id.purchase_order_ids.state',
                 'request_id.purchase_order_ids.order_line.product_qty')
    def _compute_quantity_ordered(self):
        for line in self:
            ordered = 0.0
            if line.product_id:
                order_lines = line.request_id.purchase_order_ids.filtered(
                    lambda order: order.state != 'cancel').mapped('order_line')
                ordered = sum(order_lines.filtered(
                    lambda order_line: order_line.product_id == line.product_id).mapped('product_qty'))
            shortfall = max(line.quantity_required - (line.product_id.free_qty if line.product_id else 0.0), 0.0)
            line.quantity_ordered = ordered
            line.quantity_remaining_to_order = max(shortfall - ordered, 0.0)

    # How much of this line has already been moved to the project site (from
    # the transfers this request created) and how much more could go right now
    @api.depends('product_id', 'quantity_required', 'request_id.name', 'request_id.project_id')
    def _compute_quantity_issued(self):
        for line in self:
            issued = 0.0
            if line.product_id and line.request_id.name:
                moves = self.env['stock.move'].search([
                    ('picking_id.origin', '=', line.request_id.name),
                    ('picking_id.project_id', '=', line.request_id.project_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('state', '!=', 'cancel'),
                ])
                issued = sum(moves.mapped('product_uom_qty'))
            free = line.product_id.free_qty if line.product_id else 0.0
            line.quantity_issued = issued
            line.quantity_issuable = max(min(line.quantity_required - issued, free), 0.0)
