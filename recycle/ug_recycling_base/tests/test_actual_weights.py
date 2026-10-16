from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import Form, tagged

from .common import UgRecyclingCommon


@tagged('post_install', '-at_install')
class TestActualWeights(UgRecyclingCommon):
    """ BoM: 1,000 kg packs -> 650 kg cells (standard yield 65 %, accepted 58.5–71.5 %)
    + 200 kg casing + 60 kg plastic, max loss 5 %. """

    def _confirmed_mo(self, input_kg=1000, lot_name=None):
        self._receive(self.pack, input_kg, lot_name or f'W-{self._testMethodName[-20:]}')
        production = self._create_mo(ug_input_qty=input_kg)
        production.action_confirm()
        production.action_assign()
        return production

    def _weights(self, production, main_kg, byproducts=None, inputs=None, override=False, user=None):
        """ Fill the Record Weights screen; returns the form (not yet confirmed). """
        model = self.env['ug.record.weights']
        if user:
            model = model.with_user(user)
        form = Form(model.with_context(default_production_id=production.id))
        form.main_qty_kg = main_kg
        for index, qty in enumerate(inputs or []):
            with form.input_line_ids.edit(index) as line:
                line.qty_kg = qty
        for index in range(len(form.byproduct_line_ids)):
            with form.byproduct_line_ids.edit(index) as line:
                if byproducts and line.product_id in byproducts:
                    line.qty_kg = byproducts[line.product_id]
        if override:
            form.override_weights = True
        return form

    def _activity_summaries(self, production):
        return production.activity_ids.mapped('summary')

    # ------------------------------------------------------------- BoM band
    def test_bom_yield_band(self):
        self.assertAlmostEqual(self.bom.ug_standard_yield_pct, 65)
        self.assertAlmostEqual(self.bom.ug_yield_min_pct, 58.5)
        self.assertAlmostEqual(self.bom.ug_yield_max_pct, 71.5)
        self.bom.ug_yield_tolerance_pct = 20
        self.assertAlmostEqual(self.bom.ug_yield_min_pct, 52)
        self.bom.ug_yield_tolerance_pct = 0
        self.assertFalse(self.bom._ug_check_yield())

    # ------------------------------------------- scenario 1: less output (standard Produce button)
    def test_less_output_standard_produce_keeps_input(self):
        production = self._confirmed_mo()
        production.qty_producing = 550
        production.set_qty_producing()
        primary = production.move_raw_ids
        self.assertAlmostEqual(primary.quantity, 1000, msg="input must not shrink to 846 kg")
        self.assertAlmostEqual(production.move_byproduct_ids.filtered(lambda m: m.product_id == self.casing).quantity, 200)
        res = production.button_mark_done()
        self.assertIs(res, True, "no backorder / consumption wizard for recycling orders")
        self.assertEqual(production.state, 'done')
        self.assertFalse(self.env['mrp.production'].search([('name', 'like', production.name + '-0')]),
                         "no backorder created")
        self.assertAlmostEqual(production.ug_input_weight_kg, 1000)
        self.assertAlmostEqual(production.ug_output_weight_kg, 810)
        self.assertAlmostEqual(production.ug_yield_pct, 55)
        self.assertTrue(production.ug_yield_out_of_band)
        self.assertTrue(production.ug_loss_exceeded)
        self.assertIn('Yield out of range', self._activity_summaries(production))
        self.assertIn('Process loss exceeded', self._activity_summaries(production))

    # ------------------------------------------- scenario 2: less output, inside the band (Record Weights)
    def test_less_output_record_weights(self):
        self.bom.ug_max_loss_pct = 20
        production = self._confirmed_mo()
        form = self._weights(production, 600, {self.casing: 210, self.plastic: 65})
        self.assertAlmostEqual(form.input_kg, 1000)
        self.assertAlmostEqual(form.output_kg, 875)
        self.assertAlmostEqual(form.loss_pct, 12.5)
        self.assertAlmostEqual(form.yield_pct, 60)
        self.assertEqual(form.status, 'ok')
        form.save().action_confirm()
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(production.ug_input_weight_kg, 1000)
        self.assertAlmostEqual(production.ug_output_weight_kg, 875)
        self.assertFalse(production.ug_yield_out_of_band)
        self.assertFalse(production.ug_loss_exceeded)
        self.assertFalse(production.activity_ids)
        self.assertAlmostEqual(production.lot_producing_id.product_qty, 600)

    def test_less_output_warning_loss(self):
        production = self._confirmed_mo()
        form = self._weights(production, 600, {self.casing: 210, self.plastic: 65})
        self.assertEqual(form.status, 'warning')
        self.assertIn('Loss above', form.status_message)
        form.save().action_confirm()
        self.assertTrue(production.ug_loss_exceeded)
        self.assertEqual(self._activity_summaries(production), ['Process loss exceeded'])

    # ------------------------------------------- scenario 3: more output, inside the band
    def test_more_output_within_band(self):
        production = self._confirmed_mo()
        form = self._weights(production, 700, {self.casing: 200, self.plastic: 60})
        self.assertEqual(form.status, 'ok')
        self.assertAlmostEqual(form.loss_pct, 4)
        form.save().action_confirm()
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(production.ug_yield_pct, 70)
        self.assertFalse(production.ug_yield_out_of_band)
        self.assertFalse(production.activity_ids)
        finished = production.move_finished_ids.filtered(lambda m: m.product_id == self.cells)
        self.assertAlmostEqual(finished.quantity, 700)

    # ------------------------------------------- scenario 4: more output, above the band
    def test_more_output_above_band(self):
        production = self._confirmed_mo()
        form = self._weights(production, 760, {self.casing: 180, self.plastic: 50})
        self.assertEqual(form.status, 'warning')
        self.assertIn('Yield outside', form.status_message)
        form.save().action_confirm()
        self.assertAlmostEqual(production.ug_yield_pct, 76)
        self.assertTrue(production.ug_yield_out_of_band)
        self.assertFalse(production.ug_loss_exceeded)
        self.assertEqual(self._activity_summaries(production), ['Yield out of range'])

    # ------------------------------------------- scenario 5: output above input
    def test_output_above_input_blocked(self):
        production = self._confirmed_mo()
        form = self._weights(production, 800, {self.casing: 200, self.plastic: 60})
        self.assertEqual(form.status, 'blocked')
        wizard = form.save()
        with self.assertRaisesRegex(UserError, 'more than the input'):
            wizard.action_confirm()
        self.assertNotEqual(production.state, 'done')

    def test_output_above_input_standard_produce_blocked(self):
        production = self._confirmed_mo()
        production.qty_producing = 800
        production.set_qty_producing()
        with self.assertRaisesRegex(UserError, 'more than the input'):
            production.button_mark_done()

    def test_output_above_input_manager_override(self):
        user = self.env['res.users'].create({
            'name': 'Operator', 'login': 'ug_weights_operator',
            'groups_id': [Command.set([self.env.ref('ug_recycling_base.group_ug_user').id])],
        })
        production = self._confirmed_mo()
        wizard = self._weights(production, 800, {self.casing: 200, self.plastic: 60}, override=True).save()
        with self.assertRaisesRegex(UserError, 'Only a Recycling Manager'):
            wizard.with_user(user).action_confirm()
        wizard.action_confirm()  # admin = Recycling Manager
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(production.ug_loss_kg, -60)

    # ------------------------------------------- operator-entered input is respected
    def test_operator_input_kept(self):
        production = self._confirmed_mo()
        primary = production.move_raw_ids
        primary.quantity = 980
        primary.picked = True
        production.qty_producing = 600
        production.set_qty_producing()
        self.assertAlmostEqual(primary.quantity, 980)
        production.button_mark_done()
        self.assertAlmostEqual(production.ug_input_weight_kg, 980)

    # ------------------------------------------- several input lots
    def test_record_weights_per_lot(self):
        lot_a = self._receive(self.pack, 600, 'W-LOT-A')
        lot_b = self._receive(self.pack, 400, 'W-LOT-B')
        production = self._create_mo(ug_input_qty=1000)
        production.action_confirm()
        production.action_assign()
        form = self._weights(production, 640, {self.casing: 200, self.plastic: 60}, inputs=[590, 400])
        self.assertEqual(len(form.input_line_ids), 2)
        self.assertAlmostEqual(form.input_kg, 990)
        form.save().action_confirm()
        consumed = {ml.lot_id: ml.quantity for ml in production.move_raw_ids.move_line_ids}
        self.assertEqual(set(consumed), {lot_a, lot_b})
        self.assertAlmostEqual(sum(consumed.values()), 990)
        self.assertAlmostEqual(production.ug_input_weight_kg, 990)

    # ------------------------------------------- guards
    def test_record_weights_guards(self):
        draft = self._create_mo(ug_input_qty=1000)
        with self.assertRaises(UserError):
            Form(self.env['ug.record.weights'].with_context(default_production_id=draft.id))
        production = self._confirmed_mo()
        with self.assertRaisesRegex(UserError, 'Enter the weight'):
            self._weights(production, 0).save().action_confirm()

    # ------------------------------------------- non-recycling orders keep standard Odoo behaviour
    def test_non_recycling_order_unchanged(self):
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.plastic.product_tmpl_id.id, 'product_qty': 100, 'product_uom_id': self.kg.id,
            'bom_line_ids': [Command.create({'product_id': self.pack.id, 'product_qty': 100, 'product_uom_id': self.kg.id})],
        })
        self._receive(self.pack, 100, 'W-STD')
        production = self._create_mo(bom, product_qty=100)
        production.action_confirm()
        production.action_assign()
        production.qty_producing = 50
        production.set_qty_producing()
        self.assertAlmostEqual(production.move_raw_ids.quantity, 50, msg="standard rescaling kept")
        res = production.button_mark_done()
        self.assertIsInstance(res, dict, "standard backorder wizard kept")

    # ------------------------------------------- recover stage: chemicals add weight, no block
    def test_recover_stage_not_blocked(self):
        salt = self._product('T Salt', 'recovered_material')
        acid = self._product('T Acid', 'chemical', tracking='none')
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': salt.product_tmpl_id.id, 'product_qty': 900, 'product_uom_id': self.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'recover',
            'bom_line_ids': [
                Command.create({'product_id': self.cells.id, 'product_qty': 1000, 'ug_is_primary_input': True}),
                Command.create({'product_id': acid.id, 'product_qty': 1500}),
            ],
        })
        self.assertFalse(bom._ug_check_yield())
        self._receive(self.cells, 1000, 'W-CELLS')
        self.env['stock.quant']._update_available_quantity(acid, self.stock, 2000)
        production = self._create_mo(bom, ug_input_qty=1000)
        production.action_confirm()
        production.action_assign()
        self._weights(production, 1200).save().action_confirm()
        self.assertEqual(production.state, 'done')
        self.assertAlmostEqual(production.ug_loss_kg, -200)
        self.assertFalse(production.ug_yield_out_of_band)

    # ------------------------------------------- Produce hidden, Record Weights shown on recycling orders
    def test_produce_button_hidden_for_recycling(self):
        from lxml import etree
        arch = self.env['mrp.production'].get_view(self.env.ref('mrp.mrp_production_form_view').id, 'form')['arch']
        doc = etree.fromstring(arch)
        produce = doc.xpath("//header/button[@name='button_mark_done']")
        self.assertEqual(len(produce), 4)
        for button in produce:
            self.assertIn('ug_is_recycling', button.get('invisible'))
        record = doc.xpath("//header/button[@name='action_ug_record_weights']")
        self.assertEqual(len(record), 1)
        self.assertIn('not ug_is_recycling', record[0].get('invisible'))
