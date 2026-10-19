# -*- coding: utf-8 -*-
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

    # Opens a brand-new Purchase Order with every short-of-stock line's Product
    # and Quantity already filled in — the only thing left blank is the Vendor,
    # since a shortfall list can legitimately need splitting across more than
    # one supplier and this app has no way to guess that on its own. This is
    # what turns an approved BOQ shortage list into a real RFQ ready to send.
    def action_create_purchase_orders(self):
        self.ensure_one()
        shortfall_lines = self.line_ids.filtered(lambda line: line.quantity_to_purchase > 0)
        if not shortfall_lines:
            raise UserError("Every line on this request is already covered by stock on hand — "
                             "there is nothing left to purchase.")

        order_line_vals = [(0, 0, {
            'product_id': line.product_id.id,
            'name': line.description or line.product_id.display_name,
            'product_qty': line.quantity_to_purchase,
            'product_uom': line.uom_id.id if line.uom_id else line.product_id.uom_po_id.id,
            'price_unit': line.product_id.standard_price,
            'date_planned': fields.Datetime.now(),
        }) for line in shortfall_lines]

        # If every shortfall line happens to name the same preferred vendor,
        # pre-fill it too — one less click when there's nothing to choose between
        vendors = shortfall_lines.mapped('vendor_id')
        default_vendor = vendors.id if len(vendors) == 1 else False

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id,
                'default_material_request_id': self.id,
                'default_order_line': order_line_vals,
                'default_partner_id': default_vendor,
            },
        }

    # Moves whatever's already sitting in the warehouse straight out to this
    # project's site as a real, trackable stock transfer — this is Stage 8B's
    # "Material Issue (To Project)" step: the counterpart to Purchase Orders,
    # which only ever cover the shortfall, never what's already in stock
    def action_issue_to_project(self):
        self.ensure_one()
        lines_to_issue = self.line_ids.filtered(lambda line: line.quantity_on_hand > 0)
        if not lines_to_issue:
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
                'product_uom_qty': min(line.quantity_required, line.quantity_on_hand),
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
        help="How much of this product is currently available in stock, company-wide.",
    )
    quantity_to_purchase = fields.Float(
        string='Quantity To Purchase', compute='_compute_quantity_on_hand',
        help="How much still needs to be bought: quantity required minus what's already in stock.",
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Preferred Vendor',
        help="Who to buy this from. If left blank, the product's default vendor is used.",
    )

    # Looks up how much stock is already on hand for this product, and works out
    # how much more needs to be purchased to cover what the project requires
    @api.depends('product_id', 'quantity_required')
    def _compute_quantity_on_hand(self):
        for line in self:
            line.quantity_on_hand = line.product_id.qty_available if line.product_id else 0.0
            line.quantity_to_purchase = max(line.quantity_required - line.quantity_on_hand, 0.0)
