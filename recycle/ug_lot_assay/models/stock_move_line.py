from odoo import _, models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _action_done(self):
        self._ug_check_unassayed_lots()
        return super()._action_done()

    def _ug_check_unassayed_lots(self):
        """ With the company option on, a lot whose assay is pending can be
        neither consumed in a recover-stage MO nor delivered to a customer. """
        for ml in self:
            if not ml.lot_id or ml.lot_id.ug_assay_state != 'pending':
                continue
            if not ml.company_id.ug_block_unassayed_lots or ml.product_uom_id._ug_compare(ml.quantity, 0) <= 0:
                continue
            production = ml.move_id.raw_material_production_id
            if production and production.ug_stage == 'recover':
                raise UserError(_(
                    "Lot %(lot)s (%(product)s) has no approved assay and cannot be consumed in %(mo)s.",
                    lot=ml.lot_id.name, product=ml.product_id.display_name, mo=production.name))
            if ml.location_dest_id.usage == 'customer':
                raise UserError(_(
                    "Lot %(lot)s (%(product)s) has no approved assay and cannot be delivered to a customer.",
                    lot=ml.lot_id.name, product=ml.product_id.display_name))
