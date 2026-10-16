from odoo.tests import tagged

from odoo.addons.ug_recovery_planning.tests.common import UgRecoveryCommon


@tagged('post_install', '-at_install')
class TestMassBalanceReports(UgRecoveryCommon):

    def test_mass_balance_and_output_report(self):
        self._receive(self.pack, 1000, 'MB-PACK')
        production = self._produce(self._create_mo(ug_input_qty=1000))
        self.env.flush_all()
        row = self.env['ug.mass.balance.report'].search([('production_id', '=', production.id)])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.stage, 'dismantle')
        self.assertEqual(row.battery_chemistry_id, self.lfp)
        self.assertAlmostEqual(row.input_kg, 1000)
        self.assertAlmostEqual(row.output_kg, 910)
        self.assertAlmostEqual(row.loss_pct, 9)

        outputs = self.env['ug.material.output.report'].search([('production_id', '=', production.id)])
        self.assertEqual(len(outputs), 3)
        by_product = {o.product_id: o for o in outputs}
        self.assertAlmostEqual(by_product[self.cells].qty_kg, 650)
        self.assertEqual(by_product[self.cells].ug_material_type, 'intermediate')
        self.assertTrue(by_product[self.casing].is_byproduct)
        self.assertAlmostEqual(by_product[self.casing].qty_kg, 200)
        for output in outputs:
            move = production.move_finished_ids.filtered(lambda m: m.product_id == output.product_id)
            self.assertAlmostEqual(output.value, sum(move.stock_valuation_layer_ids.mapped('value')), places=2)

    def test_tonne_moves_converted(self):
        self.bom.byproduct_ids[0].write({'product_qty': 0.2, 'product_uom_id': self.ton.id})
        self._receive(self.pack, 1000, 'MB-PACK-T')
        production = self._produce(self._create_mo(ug_input_qty=1000))
        self.env.flush_all()
        casing = self.env['ug.material.output.report'].search([
            ('production_id', '=', production.id), ('product_id', '=', self.casing.id)])
        self.assertAlmostEqual(casing.qty_kg, 200)

    def test_element_balance_report(self):
        lot = self._receive(self.bm, 1000, 'MB-BM')
        self._approved_assay(lot)
        production = self._recover_mo([(lot, 1000)])
        production.action_ug_compute_expected()
        self.env.flush_all()
        self.assertFalse(self.env['ug.element.balance.report'].search([('production_id', '=', production.id)]))
        self._produce(production)
        self.env.flush_all()
        rows = self.env['ug.element.balance.report'].search([('production_id', '=', production.id)])
        self.assertEqual(len(rows), 5)
        ni = rows.filtered(lambda r: r.element_id == self.el['ni'])
        self.assertAlmostEqual(ni.contained_kg, 200)
        self.assertAlmostEqual(ni.efficiency_pct, 95, delta=0.1)

    def test_stock_by_stage_action(self):
        action = self.env.ref('ug_mass_balance.ug_stock_by_stage_action')
        self.assertEqual(action.res_model, 'stock.quant')
        self._receive(self.pack, 10, 'MB-STOCK')
        quants = self.env['stock.quant'].search([('ug_material_type', '=', 'scrap_battery'), ('product_id', '=', self.pack.id)])
        self.assertTrue(quants)
        self.assertEqual(quants.battery_chemistry_id, self.lfp)
