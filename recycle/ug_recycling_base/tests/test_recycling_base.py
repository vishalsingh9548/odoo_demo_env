from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged

from .common import UgRecyclingCommon


@tagged('post_install', '-at_install')
class TestRecyclingBase(UgRecyclingCommon):

    # ---------------------------------------------------------------- BoM
    def test_bom_requires_one_primary_input(self):
        with self.assertRaises(ValidationError):
            self.env['mrp.bom'].create({
                'product_tmpl_id': self.cells.product_tmpl_id.id, 'product_qty': 1,
                'ug_is_recycling': True, 'ug_stage': 'recover',
                'bom_line_ids': [Command.create({'product_id': self.pack.id, 'product_qty': 1})],
            })
        with self.assertRaises(ValidationError):
            self.bom.bom_line_ids = [Command.create({'product_id': self.casing.id, 'product_qty': 1,
                                                     'ug_is_primary_input': True})]

    def test_bom_dismantle_requires_byproduct(self):
        with self.assertRaises(ValidationError):
            self.env['mrp.bom'].create({
                'product_tmpl_id': self.cells.product_tmpl_id.id, 'product_qty': 1,
                'ug_is_recycling': True, 'ug_stage': 'shred',
                'bom_line_ids': [Command.create({'product_id': self.pack.id, 'product_qty': 1,
                                                 'ug_is_primary_input': True})],
            })

    def test_bom_cost_share_below_100(self):
        with self.assertRaises(ValidationError):
            self.bom.byproduct_ids[0].cost_share = 98  # 98 + 2 = 100

    def test_non_recycling_bom_not_checked(self):
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.cells.product_tmpl_id.id, 'product_qty': 1,
            'bom_line_ids': [Command.create({'product_id': self.pack.id, 'product_qty': 1})],
        })
        self.assertFalse(bom.ug_is_recycling)

    # ------------------------------------------------- related fields
    def test_chemistry_related(self):
        production = self._create_mo()
        self.assertEqual(production.battery_chemistry_id, self.lfp)
        lot = self.env['stock.lot'].create({'name': 'CHEM-1', 'product_id': self.pack.id})
        self.assertEqual(lot.battery_chemistry_id, self.lfp)
        self.assertEqual(lot.ug_material_type, 'scrap_battery')

    # ------------------------------------------------- 1.4 input weight
    def test_input_qty_sets_product_qty(self):
        production = self._create_mo(ug_input_qty=2000)
        self.assertAlmostEqual(production.product_qty, 1300)
        primary = production.move_raw_ids.filtered(lambda m: m.bom_line_id.ug_is_primary_input)
        self.assertAlmostEqual(primary.product_uom_qty, 2000)
        casing = production.move_byproduct_ids.filtered(lambda m: m.product_id == self.casing)
        self.assertAlmostEqual(casing.product_uom_qty, 400)

    def test_product_qty_syncs_input_qty(self):
        production = self._create_mo()
        self.assertAlmostEqual(production.ug_input_qty, 1000)
        production.product_qty = 325
        self.assertAlmostEqual(production.ug_input_qty, 500)

    def test_input_qty_onchange(self):
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = self.cells
        mo_form.bom_id = self.bom
        mo_form.ug_input_qty = 1500
        self.assertAlmostEqual(mo_form.product_qty, 975)
        production = mo_form.save()
        self.assertAlmostEqual(production.ug_input_qty, 1500)

    def test_input_qty_uom_conversion(self):
        """ Primary line in tonnes, BoM in kg. """
        self.bom.bom_line_ids.write({'product_qty': 1, 'product_uom_id': self.ton.id})
        production = self._create_mo(ug_input_qty=500)
        self.assertAlmostEqual(production.product_qty, 325)

    def test_input_qty_confirmed_uses_wizard(self):
        production = self._create_mo(ug_input_qty=1000)
        production.action_confirm()
        action = production.action_ug_change_input_qty()
        self.assertEqual(action['res_model'], 'change.production.qty')
        wizard_form = Form(self.env['change.production.qty'].with_context(action['context']))
        self.assertAlmostEqual(wizard_form.ug_input_qty, 1000)
        wizard_form.ug_input_qty = 2000
        self.assertAlmostEqual(wizard_form.product_qty, 1300)
        wizard_form.save().change_prod_qty()
        self.assertAlmostEqual(production.product_qty, 1300)
        self.assertAlmostEqual(production.ug_input_qty, 2000)

    # ------------------------------------------------- 1.5 mass balance
    def test_mass_balance_values(self):
        self._receive(self.pack, 1000, 'PACK-1')
        production = self._produce(self._create_mo(ug_input_qty=1000))
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(production.ug_input_weight_kg, 1000)
        self.assertAlmostEqual(production.ug_output_weight_kg, 910)  # 650 + 200 + 60
        self.assertAlmostEqual(production.ug_loss_kg, 90)
        self.assertAlmostEqual(production.ug_loss_pct, 9.0)
        self.assertTrue(production.ug_loss_exceeded)  # 9% > 5%

    def test_mass_balance_alert(self):
        self._receive(self.pack, 1000, 'PACK-2')
        self.bom.ug_max_loss_pct = 10
        ok = self._produce(self._create_mo(ug_input_qty=1000))
        self.assertFalse(ok.ug_loss_exceeded)
        self.assertFalse(ok.activity_ids)

        self.bom.ug_max_loss_pct = 5
        self._receive(self.pack, 1000, 'PACK-3')
        production = self._create_mo(ug_input_qty=1000)
        self._produce(production, byproduct_qtys={self.casing: 150})
        self.assertAlmostEqual(production.ug_loss_pct, 14.0)
        self.assertTrue(production.ug_loss_exceeded)
        self.assertTrue(production.activity_ids)
        self.assertIn(self.env.ref('base.user_admin'), production.activity_ids.user_id)
        self.assertTrue(any('exceeds the maximum' in (m.body or '') for m in production.message_ids))

    def test_byproduct_lots_autocreated(self):
        self._receive(self.pack, 1000, 'PACK-4')
        production = self._produce(self._create_mo(ug_input_qty=1000))
        for move in production.move_byproduct_ids:
            self.assertTrue(move.move_line_ids.lot_id)

    def test_non_weight_uom_ignored(self):
        self.assertEqual(self.unit._ug_to_kg(10), 0.0)
        self.assertAlmostEqual(self.ton._ug_to_kg(2), 2000)
        self.assertTrue(self.kg._ug_is_weight())
        self.assertFalse(self.unit._ug_is_weight())

    # ------------------------------------------------- recycling chain
    def test_recycling_chain(self):
        black_mass = self._product('T Black mass LFP', 'intermediate', chem=self.lfp)
        foil = self._product('T Foil', 'scrap_byproduct')
        shred_bom = self.env['mrp.bom'].create({
            'product_tmpl_id': black_mass.product_tmpl_id.id, 'product_qty': 750, 'product_uom_id': self.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'shred', 'ug_max_loss_pct': 20,
            'bom_line_ids': [Command.create({'product_id': self.cells.id, 'product_qty': 1000,
                                             'ug_is_primary_input': True})],
            'byproduct_ids': [Command.create({'product_id': foil.id, 'product_qty': 100,
                                              'product_uom_id': self.kg.id, 'cost_share': 5})],
        })
        self._receive(self.pack, 1000, 'CHAIN-PACK')
        dismantle = self._produce(self._create_mo(ug_input_qty=1000))
        cells_lot = dismantle.lot_producing_id
        shred = self._produce(self._create_mo(shred_bom, ug_input_qty=650))
        self.assertEqual(shred.move_raw_ids.move_line_ids.lot_id, cells_lot)
        unrelated = self._create_mo(ug_input_qty=100)

        self.assertEqual(dismantle.ug_chain_production_ids, dismantle | shred)
        self.assertEqual(shred.ug_chain_production_ids.ids, [dismantle.id, shred.id])  # stage order
        self.assertNotIn(unrelated, shred.ug_chain_production_ids)
        self.assertEqual(cells_lot.ug_chain_count, 2)
        self.assertEqual(shred.lot_producing_id.ug_chain_production_ids, dismantle | shred)
        action = shred.action_ug_view_chain()
        self.assertEqual(action['domain'], [('id', 'in', (dismantle | shred).ids)])
