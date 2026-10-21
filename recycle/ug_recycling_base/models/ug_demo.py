from odoo import api, models


class UgDemo(models.AbstractModel):
    """ Helpers used by the demo data of the ug_* modules (never called otherwise). """
    _name = 'ug.demo'
    _description = 'Recycling demo helpers'

    @api.model
    def _ug_stock_location(self):
        return self.env.ref('stock.warehouse0').lot_stock_id

    @api.model
    def _ug_receive_lot(self, product_xmlid, lot_name, qty_kg):
        """ Put `qty_kg` of a product in stock under a new lot (inventory adjustment). """
        product = self.env.ref(product_xmlid)
        lot = self.env['stock.lot'].search([('name', '=', lot_name), ('product_id', '=', product.id)], limit=1)
        if not lot:
            lot = self.env['stock.lot'].create({'name': lot_name, 'product_id': product.id,
                                                'company_id': self.env.company.id})
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': self._ug_stock_location().id,
            'lot_id': lot.id,
            'inventory_quantity': qty_kg,
        }).action_apply_inventory()
        return lot

    @api.model
    def _ug_receive(self, product_xmlid, qty):
        """ Untracked stock (process chemicals). """
        product = self.env.ref(product_xmlid)
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': self._ug_stock_location().id,
            'inventory_quantity': qty,
        }).action_apply_inventory()

    @api.model
    def _ug_run_mo(self, bom_xmlid, input_kg, done=True):
        bom = self.env.ref(bom_xmlid)
        production = self.env['mrp.production'].create({
            'product_id': bom.product_tmpl_id.product_variant_id.id,
            'bom_id': bom.id,
            'ug_input_qty': input_kg,
        })
        if done:
            production.action_confirm()
            self._ug_finish_mo(production)
        return production

    @api.model
    def _ug_finish_mo(self, production):
        production.action_assign()
        if production.product_id.tracking == 'lot' and not production.lot_producing_id:
            # readable lot names so the demo chain is easy to follow: <code>-<MO number>
            code = production.product_id.default_code or 'LOT'
            production.lot_producing_id = self.env['stock.lot'].create({
                'name': f"{code}-{production.name.split('/')[-1]}",
                'product_id': production.product_id.id,
                'company_id': production.company_id.id,
            })
        production.qty_producing = production.product_qty
        production.set_qty_producing()
        production.move_raw_ids.picked = True
        production.with_context(skip_redirection=True, skip_consumption=True).button_mark_done()
        return production

    @api.model
    def _ug_demo_base_flow(self):
        self._ug_receive_lot('ug_recycling_base.product_pack_lfp', 'BP-LFP-DEMO-001', 2000)
        self._ug_receive_lot('ug_recycling_base.product_pack_nmc', 'BP-NMC-DEMO-001', 1000)
        # connected LFP chain, stage 1: 1,000 kg packs -> 650 kg cells
        self._ug_run_mo('ug_recycling_base.bom_dismantle_lfp', 1000)
        # connected NMC chain, stage 1 and 2: 1,000 kg packs -> 650 kg cells -> 487.5 kg black mass
        # (stage 3, recover, runs in the ug_recovery_planning demo once the black mass is assayed)
        self._ug_run_mo('ug_recycling_base.bom_dismantle_nmc', 1000)
        self._ug_run_mo('ug_recycling_base.bom_shred_nmc', 650)
        # connected LFP chain, stage 2: the 650 kg of LFP cells from the dismantle above
        self._ug_run_mo('ug_recycling_base.bom_shred_lfp', 650)
        # a draft order planned by input weight
        self._ug_run_mo('ug_recycling_base.bom_dismantle_lfp', 500, done=False)
