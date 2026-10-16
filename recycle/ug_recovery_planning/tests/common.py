from odoo.fields import Command

from odoo.addons.ug_lot_assay.tests.common import UgAssayCommon


class UgRecoveryCommon(UgAssayCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        el = cls.el
        cls.niso4.write({'ug_metal_element_id': el['ni'].id, 'ug_metal_content_pct': 22.3})
        cls.coso4 = cls._product('T Cobalt sulphate', 'recovered_material')
        cls.coso4.write({'ug_metal_element_id': el['co'].id, 'ug_metal_content_pct': 21.0})
        cls.li2co3 = cls._product('T Lithium carbonate', 'recovered_material')
        cls.li2co3.write({'ug_metal_element_id': el['li'].id, 'ug_metal_content_pct': 18.8})
        cls.mnso4 = cls._product('T Manganese sulphate', 'recovered_material')
        cls.mnso4.write({'ug_metal_element_id': el['mn'].id, 'ug_metal_content_pct': 32.5})
        cls.graphite = cls._product('T Graphite', 'recovered_material')
        cls.graphite.write({'ug_metal_element_id': el['c'].id, 'ug_metal_content_pct': 95.0})
        cls.na2so4 = cls._product('T Sodium sulphate', 'recovered_material')
        cls.acid = cls._product('T Sulphuric acid', 'chemical', tracking='none')

        def byp(product, qty, share):
            return Command.create({'product_id': product.id, 'product_qty': qty, 'product_uom_id': cls.kg.id, 'cost_share': share})

        def rate(element, product, pct, seq):
            return Command.create({'element_id': el[element].id, 'output_product_id': product.id,
                                   'recovery_pct': pct, 'sequence': seq})

        cls.recover_bom.write({
            'bom_line_ids': [Command.create({'product_id': cls.acid.id, 'product_qty': 1500, 'product_uom_id': cls.kg.id})],
            'byproduct_ids': [byp(cls.coso4, 315, 25), byp(cls.li2co3, 165, 30), byp(cls.mnso4, 175, 3),
                              byp(cls.graphite, 315, 2), byp(cls.na2so4, 1, 1)],
        })
        cls.recover_bom.ug_recovery_line_ids = [
            rate('ni', cls.niso4, 95, 10), rate('co', cls.coso4, 95, 20), rate('mn', cls.mnso4, 95, 30),
            rate('li', cls.li2co3, 88, 40), rate('c', cls.graphite, 90, 50),
        ]
        cls.env['stock.quant']._update_available_quantity(cls.acid, cls.stock, 100000)

        # NMC dismantle feeding the shred BoM, for full-chain tests
        cls.pack_nmc = cls._product('T Pack NMC', 'scrap_battery', chem=cls.nmc)
        cls.dismantle_nmc_bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.cells_nmc.product_tmpl_id.id, 'product_qty': 650, 'product_uom_id': cls.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'dismantle', 'ug_max_loss_pct': 50,
            'bom_line_ids': [Command.create({'product_id': cls.pack_nmc.id, 'product_qty': 1000,
                                             'ug_is_primary_input': True})],
            'byproduct_ids': [byp(cls.cu_foil, 200, 5)],
        })

    def _recover_mo(self, lots_qty):
        production = self._create_mo(self.recover_bom)
        production.ug_input_lot_line_ids = [Command.create({'lot_id': lot.id, 'qty_kg': qty}) for lot, qty in lots_qty]
        return production

    def _byproduct_qty(self, production, product):
        return sum(production.move_byproduct_ids.filtered(lambda m: m.product_id == product).mapped('product_uom_qty'))
