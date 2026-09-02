# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcQualityCheck(models.Model):
    """Stage 12 of the EPC pipeline: Quality Checks. Standard Odoo Quality app
    assumes every check is tied to a warehouse stock picking, which doesn't fit
    on-site installation/electrical/final checks — so this is a small, purpose-
    built checklist model covering all four QC categories from the process flow.
    """
    _name = 'epc.quality.check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Quality Check'
    _order = 'check_date desc, id desc'

    name = fields.Char(
        string='QC Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this quality check, e.g. QC/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project this quality check was carried out on.",
    )
    category = fields.Selection(
        [
            ('incoming_material', 'Incoming Material QC'),
            ('final', 'Final QC'),
        ],
        string='QC Category', required=True, tracking=True,
        help="Which stage of quality checking this is: material arriving on site, "
             "or the final sign-off before handover.",
    )
    picking_id = fields.Many2one(
        'stock.picking', string='Related Delivery/Receipt',
        help="For Incoming Material checks, the stock receipt this check was done "
             "against. Not applicable to on-site installation/electrical/final checks.",
    )
    inspector_id = fields.Many2one(
        'res.users', string='Inspector', default=lambda self: self.env.user,
        help="The person who carried out this quality check.",
    )
    check_date = fields.Date(
        string='Check Date', default=fields.Date.context_today,
        help="The date this quality check was performed.",
    )
    line_ids = fields.One2many(
        'epc.quality.check.line', 'check_id', string='Checklist Items',
        help="Each individual item inspected and whether it passed.",
    )
    overall_result = fields.Selection(
        [('pending', 'Pending'), ('pass', 'Pass'), ('fail', 'Fail')],
        string='Overall Result', compute='_compute_overall_result', store=True,
        help="Automatically worked out from the checklist items: Fail if any item "
             "failed, Pass if every item passed, otherwise Pending.",
    )
    remarks = fields.Text(
        string='Remarks',
        help="Any additional notes about this quality check.",
    )

    # Fills in the sequence-based reference number the first time a check is saved
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.quality.check') or 'New'
        return super().create(vals_list)

    # Suggests checklist items for whichever QC category is picked, pulled from
    # the configurable list at Solar EPC > Configuration > QC Checkpoints (not
    # hardcoded in Python) so a Project Manager can tailor what gets checked
    # without needing a code change. Re-runs every time the category changes
    # (not just the first time) and replaces whatever checklist was showing
    # before, since the checklist is meant to always match the category
    # currently selected — leaving the old category's items behind after
    # switching would silently check the wrong things (e.g. still showing
    # Incoming Material's items after switching to Installation QC).
    @api.onchange('category')
    def _onchange_category(self):
        if not self.category:
            return
        if self.category == 'incoming_material':
            # Per-product lines depend on which receipt is picked too, so
            # both onchanges share one method that rebuilds the whole list
            self._epc_rebuild_incoming_checklist()
            return
        checkpoints = self.env['epc.quality.checkpoint'].search([('category', '=', self.category)])
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {'name': checkpoint.name}) for checkpoint in checkpoints
        ]

    # Rebuilds Incoming Material QC's checklist from scratch: the generic
    # checkpoints configured for Incoming Material (things that apply to every
    # delivery, e.g. "Packaging Condition"), plus one line per actual product
    # on whichever receipt is currently picked — so the checklist always
    # matches what was really ordered and delivered, never a generic guess
    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        if self.category == 'incoming_material':
            self._epc_rebuild_incoming_checklist()

    def _epc_rebuild_incoming_checklist(self):
        checkpoints = self.env['epc.quality.checkpoint'].search([('category', '=', 'incoming_material')])
        generic_lines = [(0, 0, {'name': checkpoint.name}) for checkpoint in checkpoints]
        product_lines = [
            (0, 0, {'name': move.product_id.display_name})
            for move in self.picking_id.move_ids
        ] if self.picking_id else []
        self.line_ids = [(5, 0, 0)] + generic_lines + product_lines

    # Works out the overall pass/fail result from the individual checklist items:
    # any failure fails the whole check, otherwise it needs everything passed to pass
    @api.depends('line_ids.result')
    def _compute_overall_result(self):
        for check in self:
            results = check.line_ids.mapped('result')
            if 'fail' in results:
                check.overall_result = 'fail'
            elif results and all(result == 'pass' for result in results):
                check.overall_result = 'pass'
            else:
                check.overall_result = 'pending'

    # Once Final QC has passed, moves whatever material is still sitting at
    # this project's site location into "Installed / Consumed" — it has now
    # physically gone into the system being built, so it should stop counting
    # as warehouse stock on hand. This is Stage 8B's last step, "Material
    # Consumption (Against Activity)" — the counterpart to "Issue to Project"
    # on the Material Request, which only ever moves stock as far as the site.
    def action_consume_site_stock(self):
        self.ensure_one()
        if self.category != 'final' or self.overall_result != 'pass':
            raise UserError("Only a Final QC that has Passed can consume the material at site.")
        site_location = self.project_id.site_location_id
        if not site_location:
            raise UserError("This project has no material issued to its site yet — nothing to consume.")
        quants = self.env['stock.quant'].search([
            ('location_id', '=', site_location.id),
            ('quantity', '>', 0),
        ])
        if not quants:
            raise UserError("There is no stock left at this project's site to consume.")

        consumed_location = self.env.ref('csl_solar_epc.epc_location_consumed')
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': site_location.id,
            'location_dest_id': consumed_location.id,
            'origin': self.name,
            'project_id': self.project_id.id,
            'move_ids': [(0, 0, {
                'name': quant.product_id.display_name,
                'product_id': quant.product_id.id,
                'product_uom_qty': quant.quantity,
                'product_uom': quant.product_id.uom_id.id,
                'location_id': site_location.id,
                'location_dest_id': consumed_location.id,
            }) for quant in quants],
        })
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }


class EpcQualityCheckLine(models.Model):
    """One individual item on a Quality Check's checklist, for example
    'Insulation Test' or 'Module QC', with a pass/fail/not-applicable result.
    """
    _name = 'epc.quality.check.line'
    _description = 'Solar Quality Check Line'
    _order = 'id'

    check_id = fields.Many2one(
        'epc.quality.check', string='Quality Check', required=True, ondelete='cascade',
        help="The quality check this checklist item belongs to.",
    )
    name = fields.Char(
        string='Checklist Item', required=True,
        help="What is being checked, e.g. 'Insulation Test' or 'Module QC'.",
    )
    result = fields.Selection(
        [('pending', 'Pending'), ('pass', 'Pass'), ('fail', 'Fail'), ('na', 'Not Applicable')],
        string='Result', default='pending',
        help="Whether this specific item passed inspection.",
    )
    remarks = fields.Char(
        string='Remarks',
        help="Any note about this specific checklist item, especially useful if it failed.",
    )
