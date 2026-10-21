from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import tagged

from .common import UgRecoveryCommon


@tagged('post_install', '-at_install')
class TestRecoveryPlanning(UgRecoveryCommon):

    def _spec_mo(self, lot_name='BM-R1'):
        lot = self._receive(self.bm, 1000, lot_name)
        self._approved_assay(lot)
        production = self._recover_mo([(lot, 1000)])
        production.action_ug_compute_expected()
        return production, lot

    def _assert_spec_outputs(self, production):
        self.assertAlmostEqual(production.product_qty, 852, delta=1)
        self.assertAlmostEqual(self._byproduct_qty(production, self.coso4), 317, delta=1)
        self.assertAlmostEqual(self._byproduct_qty(production, self.mnso4), 175, delta=1)
        self.assertAlmostEqual(self._byproduct_qty(production, self.li2co3), 164, delta=1)
        self.assertAlmostEqual(self._byproduct_qty(production, self.graphite), 332, delta=1)

    def test_expected_outputs_from_spec_assay(self):
        production, _lot = self._spec_mo()
        self._assert_spec_outputs(production)
        lines = {l.output_product_id: l for l in production.ug_recovery_line_ids}
        self.assertAlmostEqual(lines[self.niso4].contained_kg, 200)
        self.assertAlmostEqual(lines[self.niso4].expected_qty_kg, 852, delta=1)
        self.assertAlmostEqual(lines[self.graphite].expected_qty_kg, 332, delta=1)
        # input set to the selected lots, chemicals scale with input
        primary = production.move_raw_ids.filtered(lambda m: m.product_id == self.bm)
        self.assertAlmostEqual(primary.product_uom_qty, 1000)
        acid = production.move_raw_ids.filtered(lambda m: m.product_id == self.acid)
        self.assertAlmostEqual(acid.product_uom_qty, 1500)
        # by-product without recovery line keeps the BoM scaling
        self.assertTrue(self._byproduct_qty(production, self.na2so4) > 0)

    def test_expected_outputs_survive_recompute_and_confirm(self):
        production, _lot = self._spec_mo('BM-R2')
        production.date_start = '2030-01-01 08:00:00'  # draft moves get rebuilt
        self._assert_spec_outputs(production)
        production.action_confirm()
        self._assert_spec_outputs(production)

    def test_multiple_input_lots(self):
        lot_a = self._receive(self.bm, 600, 'BM-R3A')
        lot_b = self._receive(self.bm, 400, 'BM-R3B')
        self._approved_assay(lot_a, dict(self.spec_results, ni=20))
        self._approved_assay(lot_b, dict(self.spec_results, ni=10))
        production = self._recover_mo([(lot_a, 600), (lot_b, 400)])
        production.action_ug_compute_expected()
        ni = production.ug_recovery_line_ids.filtered(lambda l: l.element_id == self.el['ni'])
        self.assertAlmostEqual(ni.contained_kg, 120 + 40)
        self.assertAlmostEqual(production.product_qty, 160 * 0.95 / 0.223, delta=0.01)
        primary = production.move_raw_ids.filtered(lambda m: m.product_id == self.bm)
        self.assertAlmostEqual(primary.product_uom_qty, 1000)

    def test_input_lots_reserved_on_confirm(self):
        older = self._receive(self.bm, 1000, 'BM-R4-OLD')  # FIFO would take this one
        lot = self._receive(self.bm, 1000, 'BM-R4')
        self._approved_assay(older)
        self._approved_assay(lot)
        production = self._recover_mo([(lot, 1000)])
        production.action_ug_compute_expected()
        production.action_confirm()
        primary = production.move_raw_ids.filtered(lambda m: m.product_id == self.bm)
        self.assertEqual(primary.move_line_ids.lot_id, lot)
        self.assertAlmostEqual(sum(primary.move_line_ids.mapped('quantity')), 1000)

    def test_actual_and_efficiency(self):
        production, _lot = self._spec_mo('BM-R5')
        self._produce(production, byproduct_qtys={self.coso4: 300})
        self.assertEqual(production.state, 'done')
        lines = {l.output_product_id: l for l in production.ug_recovery_line_ids}
        ni = lines[self.niso4]
        self.assertAlmostEqual(ni.actual_qty_kg, production.product_qty, delta=0.01)
        self.assertAlmostEqual(ni.efficiency_pct, 95, delta=0.1)
        co = lines[self.coso4]
        self.assertAlmostEqual(co.actual_qty_kg, 300)
        self.assertAlmostEqual(co.actual_metal_kg, 63)
        self.assertAlmostEqual(co.efficiency_pct, 90)

    def test_requires_approved_assay(self):
        lot = self._receive(self.bm, 1000, 'BM-R6')
        production = self._recover_mo([(lot, 1000)])
        with self.assertRaises(UserError):
            production.action_ug_compute_expected()

    def test_snapshot_cleared_when_lots_change(self):
        production, lot = self._spec_mo('BM-R7')
        self.assertTrue(production.ug_recovery_line_ids)
        production.ug_input_lot_line_ids[0].qty_kg = 500  # direct line write: still current snapshot
        production.ug_input_lot_line_ids = [Command.update(production.ug_input_lot_line_ids[0].id, {'qty_kg': 400})]
        self.assertFalse(production.ug_recovery_line_ids)
        production.action_ug_compute_expected()
        self.assertAlmostEqual(production.product_qty, 852 * 0.4, delta=1)

    def test_recovery_line_constraints(self):
        with self.assertRaises(ValidationError):  # element mismatch
            self.recover_bom.ug_recovery_line_ids = [Command.create({
                'element_id': self.el['co'].id, 'output_product_id': self.niso4.id, 'recovery_pct': 90})]
        with self.assertRaises(ValidationError):  # not an output of the BoM
            stranger = self._product('T Stranger', 'recovered_material')
            stranger.ug_metal_element_id = self.el['fe']
            self.recover_bom.ug_recovery_line_ids = [Command.create({
                'element_id': self.el['fe'].id, 'output_product_id': stranger.id, 'recovery_pct': 90})]

    def test_input_lot_must_match_primary(self):
        lot = self._receive(self.cu_foil, 10, 'CU-R1')
        production = self._create_mo(self.recover_bom)
        with self.assertRaises(ValidationError):
            production.ug_input_lot_line_ids = [Command.create({'lot_id': lot.id, 'qty_kg': 10})]

    def test_chain_through_draft_input_lots(self):
        self._receive(self.cells_nmc, 1000, 'CHAIN-CELLS')
        shred = self._produce(self._create_mo(self.shred_bom, ug_input_qty=1000))
        bm_lot = shred.lot_producing_id
        self._approved_assay(bm_lot)
        recover = self._recover_mo([(bm_lot, 750)])
        self.assertEqual(recover.state, 'draft')
        self.assertEqual(shred.ug_chain_production_ids, shred | recover)
        self.assertEqual(recover.ug_chain_production_ids.ids, [shred.id, recover.id])
        self.assertEqual(bm_lot.ug_chain_count, 2)
        # the black mass assay is visible from the shred MO (output) and the recover MO (input)
        assay = bm_lot.ug_current_assay_id
        self.assertIn(assay, shred.ug_assay_ids)
        self.assertIn(assay, recover.ug_assay_ids)
        self.assertEqual(assay.production_id, shred)
        self.assertEqual(assay.production_ids, shred | recover)
        action = assay.action_view_productions()
        self.assertEqual(action['domain'], [('id', 'in', (shred | recover).ids)])

    def test_zero_main_element_clear_error(self):
        lot = self._receive(self.bm, 1000, 'BM-NO-NI')
        self._approved_assay(lot, dict(self.spec_results, ni=0))
        production = self._recover_mo([(lot, 1000)])
        with self.assertRaisesRegex(UserError, 'BM-NO-NI'):
            production.action_ug_compute_expected()
