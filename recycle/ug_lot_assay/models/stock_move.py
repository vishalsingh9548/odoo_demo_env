from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    ug_has_assay = fields.Boolean(compute='_compute_ug_has_assay', string='Has Assayed Lot')

    @api.depends('move_line_ids.lot_id.ug_current_assay_id')
    def _compute_ug_has_assay(self):
        for move in self:
            move.ug_has_assay = bool(move.move_line_ids.lot_id.ug_current_assay_id)

    def action_ug_print_coa(self):
        lots = self.move_line_ids.lot_id.filtered('ug_current_assay_id')
        if not lots:
            raise UserError(_("No approved assay on the lots of these lines."))
        return lots.action_ug_print_coa()


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ug_has_assay = fields.Boolean(compute='_compute_ug_has_assay', string='Has Assayed Lot')

    @api.depends('move_ids.ug_has_assay')
    def _compute_ug_has_assay(self):
        for picking in self:
            picking.ug_has_assay = any(picking.move_ids.mapped('ug_has_assay'))

    def action_ug_print_coa(self):
        return self.move_ids.action_ug_print_coa()
