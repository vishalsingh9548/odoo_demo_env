from odoo.fields import Command
from odoo.tests import TransactionCase


class UgRecyclingCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg = cls.env.ref('uom.product_uom_kgm')
        cls.ton = cls.env.ref('uom.product_uom_ton')
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.stock = cls.env.ref('stock.warehouse0').lot_stock_id
        cls.lfp = cls.env.ref('ug_recycling_base.chemistry_lfp')
        cls.nmc = cls.env.ref('ug_recycling_base.chemistry_nmc')

        def product(name, mtype, tracking='lot', chem=False, uom=None):
            return cls.env['product.product'].create({
                'name': name, 'type': 'consu', 'is_storable': True,
                'tracking': tracking, 'uom_id': (uom or cls.kg).id,
                'ug_material_type': mtype,
                'battery_chemistry_id': chem and chem.id,
            })
        cls._product = staticmethod(product)
        cls.pack = product('T Pack LFP', 'scrap_battery', chem=cls.lfp)
        cls.cells = product('T Cells LFP', 'intermediate', chem=cls.lfp)
        cls.casing = product('T Casing', 'scrap_byproduct')
        cls.plastic = product('T Plastic', 'scrap_byproduct')

        cls.bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.cells.product_tmpl_id.id,
            'product_qty': 650, 'product_uom_id': cls.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'dismantle', 'ug_max_loss_pct': 5.0,
            'battery_chemistry_id': cls.lfp.id,
            'bom_line_ids': [Command.create({'product_id': cls.pack.id, 'product_qty': 1000,
                                             'product_uom_id': cls.kg.id, 'ug_is_primary_input': True})],
            'byproduct_ids': [
                Command.create({'product_id': cls.casing.id, 'product_qty': 200, 'product_uom_id': cls.kg.id, 'cost_share': 8}),
                Command.create({'product_id': cls.plastic.id, 'product_qty': 60, 'product_uom_id': cls.kg.id, 'cost_share': 2}),
            ],
        })

    @classmethod
    def _receive(cls, product, qty, lot_name):
        lot = cls.env['stock.lot'].create({'name': lot_name, 'product_id': product.id})
        cls.env['stock.quant']._update_available_quantity(product, cls.stock, qty, lot_id=lot)
        return lot

    def _create_mo(self, bom=None, **vals):
        bom = bom or self.bom
        return self.env['mrp.production'].create(dict({
            'product_id': bom.product_tmpl_id.product_variant_id.id,
            'bom_id': bom.id,
        }, **vals))

    def _produce(self, production, finished_qty=None, byproduct_qtys=None, consumed_qty=None):
        """ Confirm and mark done with optional actual quantities (in move units). """
        production.action_confirm()
        production.action_assign()
        production.qty_producing = finished_qty or production.product_qty
        production.set_qty_producing()
        for product, qty in (byproduct_qtys or {}).items():
            move = production.move_byproduct_ids.filtered(lambda m: m.product_id == product)
            move.quantity = qty
        if consumed_qty is not None:
            production.move_raw_ids.filtered(lambda m: m.bom_line_id.ug_is_primary_input).quantity = consumed_qty
        production.move_raw_ids.picked = True
        production.with_context(skip_redirection=True, skip_consumption=True).button_mark_done()
        return production
