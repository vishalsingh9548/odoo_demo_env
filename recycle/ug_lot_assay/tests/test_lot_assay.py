from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import tagged

from .common import UgAssayCommon


@tagged('post_install', '-at_install')
class TestLotAssay(UgAssayCommon):

    def test_assay_defaults_from_lot(self):
        lot = self._receive(self.bm, 1000, 'BM-A1')
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id})
        self.assertTrue(assay.name.startswith('ASSAY/'))
        self.assertAlmostEqual(assay.basis_weight_kg, 1000)
        self.assertEqual(assay.line_ids.element_id, self.template.element_ids)
        self.assertEqual(assay.product_id, self.bm)
        self.assertEqual(assay.battery_chemistry_id, self.nmc)

    def test_contained_and_others(self):
        lot = self._receive(self.bm, 1000, 'BM-A2')
        assay = self._approved_assay(lot)
        ni = assay.line_ids.filtered(lambda l: l.element_id == self.el['ni'])
        self.assertAlmostEqual(ni.contained_kg_basis, 200)
        self.assertAlmostEqual(ni.contained_kg_current, 200)
        self.assertAlmostEqual(assay.others_pct, 100 - 73.5)
        # current follows on-hand quantity, basis does not
        self.env['stock.quant']._update_available_quantity(self.bm, self.stock, -500, lot_id=lot)
        ni.invalidate_recordset(['contained_kg_current'])
        self.assertAlmostEqual(ni.contained_kg_current, 100)
        self.assertAlmostEqual(ni.contained_kg_basis, 200)

    def test_percentage_constraints(self):
        lot = self._receive(self.bm, 100, 'BM-A3')
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id})
        with self.assertRaises(ValidationError):
            assay.line_ids[0].percentage = 101
        with self.assertRaises(ValidationError):
            assay.line_ids[0].percentage = -1
        with self.assertRaises(ValidationError):
            assay.line_ids[:2].percentage = 50.3  # 100.6 > 100.5
        assay.line_ids[:2].percentage = 50.2  # 100.4 tolerated
        with self.assertRaises(ValidationError):
            assay.line_ids = [Command.create({'element_id': assay.line_ids[0].element_id.id, 'percentage': 0})]

    def test_external_lab(self):
        lot = self._receive(self.bm, 100, 'BM-A4')
        with self.assertRaises(ValidationError):
            self.env['ug.lot.assay'].create({'lot_id': lot.id, 'lab_type': 'external'})
        lab = self.env['res.partner'].create({'name': 'Ext Lab'})
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id, 'lab_type': 'external', 'lab_partner_id': lab.id})
        assay.line_ids[0].percentage = 20
        assay.action_submit()
        with self.assertRaises(UserError):
            assay.action_approve()
        assay.certificate_attachment_ids = [Command.create({'name': 'cert.pdf', 'raw': b'%PDF-1.4'})]
        assay.action_approve()
        self.assertEqual(assay.state, 'approved')

    def test_current_assay_switch(self):
        lot = self._receive(self.bm, 1000, 'BM-A5')
        self.assertEqual(lot.ug_assay_state, 'pending')
        first = self._approved_assay(lot)
        self.assertTrue(first.is_current)
        self.assertEqual(lot.ug_current_assay_id, first)
        self.assertEqual(lot.ug_assay_state, 'approved')
        second = self._approved_assay(lot, dict(self.spec_results, ni=21))
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(lot.ug_current_assay_id, second)
        self.assertTrue(any('Replaces assay' in (m.body or '') for m in lot.message_ids))
        with self.assertRaises(UserError):
            second.basis_weight_kg = 5
        self.assertIn(lot, self.env['stock.lot'].search([('ug_assay_state', '=', 'approved')]))

    def test_assay_state_not_required(self):
        lot = self._receive(self.cu_foil, 10, 'CU-A1')
        self.assertEqual(lot.ug_assay_state, 'not_required')

    def test_group_restrictions(self):
        user = self.env['res.users'].create({
            'name': 'Plain recycler', 'login': 'ug_plain_user',
            'groups_id': [Command.set([self.env.ref('ug_recycling_base.group_ug_user').id,
                                        self.env.ref('stock.group_stock_user').id])],
        })
        lab = self.env['res.users'].create({
            'name': 'Lab tech', 'login': 'ug_lab_user',
            'groups_id': [Command.set([self.env.ref('ug_recycling_base.group_ug_lab').id])],
        })
        lot = self._receive(self.bm, 10, 'BM-A6')
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id})
        assay.line_ids[0].percentage = 10
        with self.assertRaises(UserError):
            assay.with_user(user).action_submit()
        assay.with_user(lab).action_submit()
        with self.assertRaises(UserError):
            assay.with_user(lab).action_approve()
        assay.action_approve()

    def test_auto_assay_on_production(self):
        self._receive(self.cells_nmc, 1000, 'CELLS-A1')
        production = self._produce(self._create_mo(self.shred_bom, ug_input_qty=1000))
        lot = production.lot_producing_id
        self.assertTrue(lot)
        assay = lot.ug_assay_ids
        self.assertEqual(len(assay), 1)
        self.assertEqual(assay.state, 'draft')
        self.assertEqual(len(assay.line_ids), 7)
        self.assertAlmostEqual(assay.basis_weight_kg, 750)
        self.assertTrue(assay.activity_ids)
        # by-product without assay requirement gets nothing
        self.assertFalse(production.move_byproduct_ids.move_line_ids.lot_id.ug_assay_ids)
        # assay <-> MO links (smart buttons)
        self.assertEqual(assay.production_id, production)
        self.assertEqual(assay.production_ids, production)
        self.assertEqual(production.ug_assay_ids, assay)
        self.assertEqual(production.action_ug_view_assays()['res_id'], assay.id)
        self.assertEqual(assay.action_view_productions()['res_id'], production.id)
        self.assertIn(assay, self.env['ug.lot.assay'].search([('production_id', '=', production.id)]))

    def test_block_recover_consumption(self):
        self.env.company.ug_block_unassayed_lots = True
        lot = self._receive(self.bm, 1000, 'BM-A7')
        production = self._create_mo(self.recover_bom, ug_input_qty=1000)
        with self.assertRaisesRegex(UserError, 'BM-A7'):
            self._produce(production)
        # approved -> allowed
        self._approved_assay(lot)
        production = self._create_mo(self.recover_bom, ug_input_qty=1000)
        self._produce(production)
        self.assertEqual(production.state, 'done')

    def test_block_disabled(self):
        self.env.company.ug_block_unassayed_lots = False
        self._receive(self.bm, 1000, 'BM-A8')
        production = self._produce(self._create_mo(self.recover_bom, ug_input_qty=1000))
        self.assertEqual(production.state, 'done')

    def _deliver(self, product, lot, qty):
        picking_type = self.env.ref('stock.picking_type_out')
        customer = self.env['res.partner'].create({'name': 'Buyer'})
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': customer.id,
            'location_id': self.stock.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [Command.create({
                'name': product.name, 'product_id': product.id, 'product_uom_qty': qty,
                'location_id': self.stock.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, lot)
        picking.move_ids.picked = True
        return picking

    def test_block_delivery(self):
        self.env.company.ug_block_unassayed_lots = True
        lot = self._receive(self.bm, 100, 'BM-A9')
        picking = self._deliver(self.bm, lot, 100)
        with self.assertRaisesRegex(UserError, 'BM-A9'):
            picking._action_done()
        self._approved_assay(lot)
        self.assertTrue(picking.ug_has_assay)
        picking._action_done()
        self.assertEqual(picking.state, 'done')
        self.env.company.external_report_layout_id = self.env.ref('web.external_layout_standard')
        action = picking.action_ug_print_coa()
        self.assertEqual(action['report_name'], 'ug_lot_assay.report_ug_coa')

    def test_metal_value_estimate(self):
        lot = self._receive(self.bm, 1000, 'BM-A10')
        self._approved_assay(lot)
        Price = self.env['ug.metal.price']
        Price.search([]).unlink()
        currency = self.env.company.currency_id
        Price.create({'element_id': self.el['ni'].id, 'price_per_kg': 10, 'date': '2020-01-01', 'currency_id': currency.id})
        Price.create({'element_id': self.el['ni'].id, 'price_per_kg': 15, 'date': '2021-01-01', 'currency_id': currency.id})
        Price.create({'element_id': self.el['co'].id, 'price_per_kg': 20, 'date': '2020-06-01', 'currency_id': currency.id})
        # 200 kg Ni x 15 + 70 kg Co x 20
        self.assertAlmostEqual(lot.ug_estimated_metal_value, 200 * 15 + 70 * 20)

    def test_coa_report_renders(self):
        lot = self._receive(self.bm, 1000, 'BM-A11')
        self._approved_assay(lot)
        html = self.env['ir.actions.report']._render_qweb_html('ug_lot_assay.report_ug_coa', lot.ids)[0]
        self.assertIn(b'Certificate of Analysis', html)
        self.assertIn(b'BM-A11', html)
        with self.assertRaises(UserError):
            self._receive(self.bm, 1, 'BM-A12').action_ug_print_coa()

    def test_cannot_submit_all_zero_results(self):
        lot = self._receive(self.bm, 100, 'BM-ZERO')
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id})
        with self.assertRaisesRegex(UserError, 'are 0'):
            assay.action_submit()
        assay.line_ids[0].percentage = 5
        assay.action_submit()
        self.assertEqual(assay.state, 'submitted')
