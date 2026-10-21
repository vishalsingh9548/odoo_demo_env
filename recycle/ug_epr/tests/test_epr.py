from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.ug_epr.models.ug_epr_certificate import indian_financial_year
from odoo.addons.ug_recycling_base.tests.common import UgRecyclingCommon


@tagged('post_install', '-at_install')
class TestEpr(UgRecyclingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.ug_epr_basis = 'input_battery_weight'
        cls.category = cls.env.ref('ug_epr.epr_category_ev')
        cls.buyer = cls.env['res.partner'].create({'name': 'Producer'})
        cls._receive(cls.pack, 3000, 'EPR-PACK')
        production = cls.env['mrp.production'].create({
            'product_id': cls.cells.id, 'bom_id': cls.bom.id, 'ug_input_qty': 1000})
        production.action_confirm()
        production.action_assign()
        production.qty_producing = production.product_qty
        production.set_qty_producing()
        production.move_raw_ids.picked = True
        production.with_context(skip_redirection=True, skip_consumption=True).button_mark_done()
        cls.mo = production

    def _certificate(self, qty, **vals):
        return self.env['ug.epr.certificate'].create(dict({
            'epr_category_id': self.category.id,
            'quantity_kg': qty,
            'production_ids': [Command.set(self.mo.ids)],
        }, **vals))

    def test_financial_year(self):
        self.assertEqual(indian_financial_year(date(2026, 3, 31)), '2025-26')
        self.assertEqual(indian_financial_year(date(2026, 4, 1)), '2026-27')
        certificate = self._certificate(10, generation_date='2027-01-15')
        self.assertEqual(certificate.financial_year, '2026-27')
        self.assertTrue(certificate.name.startswith('EPR/'))

    def test_eligible_input_basis(self):
        self.assertEqual(self.mo.state, 'done')
        self.assertAlmostEqual(self.mo.ug_epr_eligible_kg, 1000)
        self.assertAlmostEqual(self.mo.ug_epr_available_kg, 1000)

    def test_eligible_recovered_basis(self):
        self.env.company.ug_epr_basis = 'recovered_material_weight'
        self.assertAlmostEqual(self.mo.ug_epr_eligible_kg, 0)  # dismantle MO no longer counts
        salt = self._product('T Salt', 'recovered_material')
        residue = self._product('T Residue', 'scrap_byproduct')
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': salt.product_tmpl_id.id, 'product_qty': 300, 'product_uom_id': self.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'recover',
            'bom_line_ids': [Command.create({'product_id': self.cells.id, 'product_qty': 1000,
                                             'ug_is_primary_input': True})],
            'byproduct_ids': [Command.create({'product_id': residue.id, 'product_qty': 100,
                                              'product_uom_id': self.kg.id, 'cost_share': 1})],
        })
        production = self._produce(self._create_mo(bom, ug_input_qty=650))
        self.assertAlmostEqual(production.ug_epr_eligible_kg, 195)  # recovered material only

    def test_no_double_claiming(self):
        first = self._certificate(600)
        self.assertAlmostEqual(self.mo.ug_epr_claimed_kg, 600)
        self.assertAlmostEqual(self.mo.ug_epr_available_kg, 400)
        with self.assertRaises(ValidationError):
            self._certificate(500)
        second = self._certificate(400)
        self.assertAlmostEqual(self.mo.ug_epr_available_kg, 0)
        with self.assertRaises(ValidationError):
            second.quantity_kg = 401
        first.action_cancel()
        self.assertAlmostEqual(self.mo.ug_epr_claimed_kg, 400)
        second.quantity_kg = 1000
        self.assertAlmostEqual(self.mo.ug_epr_available_kg, 0)
        with self.assertRaises(ValidationError):  # reactivating would over-claim
            first.action_reset_draft()

    def test_workflow_and_sale(self):
        certificate = self._certificate(500, partner_id=self.buyer.id, price_per_kg=20)
        self.assertAlmostEqual(certificate.amount, 10000)
        with self.assertRaises(UserError):
            certificate.action_generate()  # CPCB number missing
        certificate.portal_certificate_no = 'CPCB-1'
        certificate.action_generate()
        with self.assertRaises(ValidationError):
            certificate.portal_certificate_no = False
        with self.assertRaises(UserError):
            certificate.action_create_quotation()  # not listed yet
        certificate.action_list()
        certificate.action_create_quotation()
        order = certificate.sale_order_id
        self.assertEqual(order.partner_id, self.buyer)
        self.assertEqual(order.order_line.product_id, self.env.ref('ug_epr.product_epr_certificate'))
        self.assertAlmostEqual(order.order_line.product_uom_qty, 500)
        self.assertAlmostEqual(order.order_line.price_unit, 20)

        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(certificate.invoice_ids, invoice)
        self.assertEqual(certificate.state, 'listed')
        invoice.action_post()
        self.assertEqual(certificate.state, 'sold')

        with self.assertRaises(UserError):
            certificate.action_mark_transferred()
        certificate.transfer_ref = 'TRF-001'
        certificate.action_mark_transferred()
        self.assertEqual(certificate.state, 'transferred')
        self.assertTrue(certificate.transfer_date)
        with self.assertRaises(UserError):
            certificate.action_cancel()

    def test_state_restricted_to_epr_officer(self):
        user = self.env['res.users'].create({
            'name': 'Recycler', 'login': 'ug_epr_plain',
            'groups_id': [Command.set([self.env.ref('ug_recycling_base.group_ug_user').id])],
        })
        certificate = self._certificate(10, portal_certificate_no='CPCB-2')
        with self.assertRaises(UserError):
            certificate.with_user(user).action_generate()
        officer = self.env['res.users'].create({
            'name': 'Officer', 'login': 'ug_epr_officer',
            'groups_id': [Command.set([self.env.ref('ug_recycling_base.group_ug_user').id])],
        })
        certificate.with_user(officer).action_generate()
        self.assertEqual(certificate.state, 'generated')

    def test_waste_manifest(self):
        manifest = self.env['ug.waste.manifest'].create({'waste_description': 'Filter cake', 'quantity_kg': 100})
        self.assertTrue(manifest.name.startswith('HWM/'))
        manifest.action_dispatch()
        manifest.action_acknowledge()
        self.assertEqual(manifest.state, 'acknowledged')

    def test_certificate_from_the_order(self):
        action = self.mo.action_ug_create_epr_certificate()
        self.assertEqual(action['res_model'], 'ug.epr.certificate')
        form = Form(self.env['ug.epr.certificate'].with_context(action['context']))
        self.assertAlmostEqual(form.quantity_kg, 1000)
        self.assertEqual(form.battery_chemistry_id, self.lfp)
        form.epr_category_id = self.category
        certificate = form.save()
        self.assertEqual(certificate.production_ids, self.mo)
        self.assertEqual(self.mo.ug_epr_certificate_count, 1)
        self.assertEqual(self.mo.action_ug_view_epr_certificates()['res_id'], certificate.id)
        self.assertAlmostEqual(self.mo.ug_epr_available_kg, 0)
        with self.assertRaises(UserError):
            self.mo.action_ug_create_epr_certificate()
