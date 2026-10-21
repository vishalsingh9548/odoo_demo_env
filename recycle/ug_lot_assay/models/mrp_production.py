from odoo import _, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ug_assay_ids = fields.Many2many('ug.lot.assay', compute='_compute_ug_assay_ids', string='Assays',
        help="Assays of the lots produced by this order and of the lots it consumes.")
    ug_assay_count = fields.Integer(compute='_compute_ug_assay_ids', string='Assay Count')

    def _compute_ug_assay_ids(self):
        Assay = self.env['ug.lot.assay']
        for production in self:
            lots = production._origin._ug_produced_lots() | production._origin._ug_consumed_lots() \
                if production._origin else self.env['stock.lot']
            assays = Assay.search([('lot_id', 'in', lots.ids)]) if lots else Assay
            production.ug_assay_ids = assays
            production.ug_assay_count = len(assays)

    def action_ug_view_assays(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ug_lot_assay.ug_lot_assay_action')
        action.update({
            'name': _("Assays – %s", self.name),
            'domain': [('id', 'in', self.ug_assay_ids.ids)],
            'context': {'create': False, 'search_default_groupby_product': 1},
        })
        if len(self.ug_assay_ids) == 1:
            action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': self.ug_assay_ids.id})
        return action

    def _ug_on_done(self):
        super()._ug_on_done()
        lots = self.move_finished_ids.filtered(lambda m: m.state == 'done').move_line_ids.lot_id
        self.env['ug.lot.assay'].sudo()._ug_create_from_production(
            lots.filtered(lambda lot: lot.product_id.ug_requires_assay))
