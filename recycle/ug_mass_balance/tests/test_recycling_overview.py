from odoo.tests import tagged

from odoo.addons.ug_recovery_planning.tests.common import UgRecoveryCommon


@tagged('post_install', '-at_install')
class TestRecyclingOverview(UgRecoveryCommon):

    def _card(self, xmlid):
        card = self.env.ref(f'ug_mass_balance.overview_{xmlid}')
        card.invalidate_recordset()
        return card

    def test_overview_cards(self):
        base = {c: self._card(c) for c in ('dismantle', 'shred', 'recover', 'lab', 'epr')}
        before = {c: (card.queue_count, card.mo_draft_count, card.assay_submitted_count, card.epr_available_kg)
                  for c, card in base.items()}

        # packs waiting for dismantle, one draft dismantle order
        self._receive(self.pack_nmc, 1000, 'OV-PACK')
        dismantle = self._card('dismantle')
        self.assertEqual(dismantle.queue_count, before['dismantle'][0] + 1)
        self._create_mo(self.dismantle_nmc_bom, ug_input_qty=100)
        self.assertEqual(self._card('dismantle').mo_draft_count, before['dismantle'][1] + 1)

        # dismantle done -> cells waiting for shred, EPR to claim
        self._receive(self.pack_nmc, 1000, 'OV-PACK2')
        mo = self._produce(self._create_mo(self.dismantle_nmc_bom, ug_input_qty=1000))
        self.assertEqual(self._card('shred').queue_count, before['shred'][0] + 1)
        self.assertGreaterEqual(self._card('dismantle').month_input_kg, 1000)
        self.assertAlmostEqual(self._card('epr').epr_available_kg, before['epr'][3] + mo.ug_epr_eligible_kg)

        # shred done -> black mass waiting for lab, then to approve
        shred = self._produce(self._create_mo(self.shred_bom, ug_input_qty=650))
        recover = self._card('recover')
        self.assertGreaterEqual(recover.waiting_lab_count, 1)
        assay = shred.lot_producing_id.ug_assay_ids
        for line in assay.line_ids:
            line.percentage = 10
        assay.action_submit()
        self.assertEqual(self._card('lab').assay_submitted_count, before['lab'][2] + 1)
        assay.action_approve()
        self.assertEqual(self._card('recover').queue_count, before['recover'][0] + 1)

        # every card link opens an action
        for card in base.values():
            for view in (None, 'queue', 'waiting_lab', 'draft', 'open', 'late', 'loss', 'month',
                         'submitted', 'lots', 'approved', 'available', 'listed', 'sold'):
                action = card.with_context(ug_view=view).action_open()
                self.assertIn(action['type'], ('ir.actions.act_window',))
        queue_action = self._card('recover').with_context(ug_view='queue').action_open()
        self.assertEqual(queue_action['res_model'], 'ug.process.queue')
