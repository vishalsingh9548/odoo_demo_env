from odoo import _, api, fields, models

STAGE_ORDER = {'dismantle': 1, 'shred': 2, 'recover': 3}


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ug_chain_production_ids = fields.Many2many('mrp.production', compute='_compute_ug_chain',
        string='Recycling Chain', help="Manufacturing orders linked to this one through lots: "
                                       "the orders that produced its input lots and the ones that consume its output lots.")
    ug_chain_count = fields.Integer(compute='_compute_ug_chain', string='Chain')

    # -- lots in / out of an order -------------------------------------------------
    def _ug_consumed_lots(self):
        """ Lots consumed (or reserved / selected to be consumed) by these orders. """
        return self.move_raw_ids.filtered(lambda m: m.state != 'cancel').move_line_ids.lot_id

    def _ug_produced_lots(self):
        return self.lot_producing_id | self.move_finished_ids.filtered(
            lambda m: m.state != 'cancel').move_line_ids.lot_id

    @api.model
    def _ug_producers_of(self, lots):
        """ Orders that produced (or are producing) these lots. """
        if not lots:
            return self.browse()
        producing = self.search([('lot_producing_id', 'in', lots.ids), ('state', '!=', 'cancel')])
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', 'in', lots.ids), ('move_id.production_id', '!=', False), ('state', '!=', 'cancel')])
        return producing | move_lines.move_id.production_id

    @api.model
    def _ug_consumers_of(self, lots):
        """ Orders that consume (or are planned to consume) these lots. """
        if not lots:
            return self.browse()
        move_lines = self.env['stock.move.line'].search([
            ('lot_id', 'in', lots.ids), ('move_id.raw_material_production_id', '!=', False), ('state', '!=', 'cancel')])
        return move_lines.move_id.raw_material_production_id

    def _ug_chain(self, max_orders=200):
        """ All orders reachable from self through lots, upstream and downstream. """
        upstream = downstream = self
        chain = self
        while (upstream or downstream) and len(chain) < max_orders:
            new_up = self._ug_producers_of(upstream._ug_consumed_lots()) - chain
            chain |= new_up
            new_down = self._ug_consumers_of(downstream._ug_produced_lots()) - chain
            chain |= new_down
            upstream, downstream = new_up, new_down
        return chain.filtered('ug_is_recycling').sorted(
            lambda p: (STAGE_ORDER.get(p.ug_stage, 9), p.date_finished or p.date_start or p.create_date, p.id))

    @api.depends('state', 'lot_producing_id', 'move_raw_ids.move_line_ids.lot_id',
                 'move_finished_ids.move_line_ids.lot_id')
    def _compute_ug_chain(self):
        for production in self:
            chain = production._origin._ug_chain() if production._origin else self.browse()
            production.ug_chain_production_ids = chain
            production.ug_chain_count = len(chain)

    def action_ug_view_chain(self):
        self.ensure_one()
        return self.env['stock.lot']._ug_chain_action(self.ug_chain_production_ids, self.name)


class StockLot(models.Model):
    _inherit = 'stock.lot'

    ug_chain_production_ids = fields.Many2many('mrp.production', compute='_compute_ug_chain',
        string='Recycling Chain', help="Recycling orders that produced or consumed this lot, "
                                       "and every order linked to them through lots.")
    ug_chain_count = fields.Integer(compute='_compute_ug_chain', string='Chain')

    def _compute_ug_chain(self):
        Production = self.env['mrp.production']
        for lot in self:
            start = Production._ug_producers_of(lot._origin) | Production._ug_consumers_of(lot._origin)
            chain = start._ug_chain() if start else Production
            lot.ug_chain_production_ids = chain
            lot.ug_chain_count = len(chain)

    def action_ug_view_chain(self):
        self.ensure_one()
        return self._ug_chain_action(self.ug_chain_production_ids, self.name)

    @api.model
    def _ug_chain_action(self, productions, label):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Recycling Chain – %s", label),
            'res_model': 'mrp.production',
            'view_mode': 'list,form',
            'views': [(self.env.ref('ug_recycling_base.mrp_production_view_list_ug_chain').id, 'list'), (False, 'form')],
            'domain': [('id', 'in', productions.ids)],
            'context': {'create': False, 'group_by': 'ug_stage'},
        }
