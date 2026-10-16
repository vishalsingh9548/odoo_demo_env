from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from .common import UgRecoveryCommon


@tagged('post_install', '-at_install')
class TestProcessQueue(UgRecoveryCommon):

    def _queue(self, lots):
        self.env.flush_all()
        return self.env['ug.process.queue'].search([('lot_id', 'in', lots.ids)])

    def _create_from_queue(self, rows):
        action = rows.action_create_production()
        return self.env['mrp.production'].browse(action['res_id'])

    def test_full_flow_through_queue(self):
        cells_lot = self._receive(self.cells_nmc, 1000, 'Q-CELLS')
        row = self._queue(cells_lot)
        self.assertEqual(row.stage, 'shred')
        self.assertEqual(row.bom_id, self.shred_bom)
        self.assertTrue(row.ready)
        self.assertAlmostEqual(row.available_kg, 1000)

        # shred MO from the queue: draft, input lot and weight filled, lot leaves the queue
        shred = self._create_from_queue(row)
        self.assertEqual(shred.state, 'draft')
        self.assertEqual(shred.bom_id, self.shred_bom)
        self.assertEqual(shred.ug_input_lot_line_ids.lot_id, cells_lot)
        self.assertAlmostEqual(shred.ug_input_qty, 1000)
        self.assertAlmostEqual(shred.product_qty, 750)
        self.assertFalse(self._queue(cells_lot))

        # confirmation reserves the selected lot; it stays out of the queue
        shred.action_confirm()
        self.assertEqual(shred.move_raw_ids.move_line_ids.lot_id, cells_lot)
        self.assertFalse(self._queue(cells_lot))
        self._produce(shred)

        # black mass waits for the lab, then goes to recover
        bm_lot = shred.lot_producing_id
        row = self._queue(bm_lot)
        self.assertEqual(row.stage, 'recover')
        self.assertFalse(row.ready)
        with self.assertRaises(UserError):
            row.action_create_production()
        self._approved_assay(bm_lot)
        row = self._queue(bm_lot)
        self.assertTrue(row.ready)
        recover = self._create_from_queue(row)
        self.assertEqual(recover.bom_id, self.recover_bom)
        self.assertAlmostEqual(recover.ug_input_lots_kg, 750)
        self.assertTrue(recover.ug_recovery_line_ids)
        self.assertAlmostEqual(recover.product_qty, 852.02 * 0.75, delta=1)
        self.assertEqual(recover.ug_chain_production_ids, shred | recover)

    def test_several_lots_in_one_order(self):
        lot_a = self._receive(self.cells_nmc, 300, 'Q-A')
        lot_b = self._receive(self.cells_nmc, 200, 'Q-B')
        shred = self._create_from_queue(self._queue(lot_a | lot_b))
        self.assertEqual(shred.ug_input_lot_line_ids.lot_id, lot_a | lot_b)
        self.assertAlmostEqual(shred.ug_input_qty, 500)
        shred.action_confirm()
        primary = shred.move_raw_ids.filtered(lambda m: m.product_id == self.cells_nmc)
        self.assertEqual(primary.move_line_ids.lot_id, lot_a | lot_b)

    def test_partial_planning_and_dismantle_stage(self):
        pack_lot = self._receive(self.pack, 1000, 'Q-PACK')
        row = self._queue(pack_lot)
        self.assertEqual(row.stage, 'dismantle')
        production = self._create_mo(self.bom)
        production.ug_input_lot_line_ids = [Command.create({'lot_id': pack_lot.id, 'qty_kg': 400})]
        self.assertAlmostEqual(production.ug_input_qty, 400)
        self.assertAlmostEqual(self._queue(pack_lot).available_kg, 600)

    def test_mixed_selection_refused(self):
        rows = self._queue(self._receive(self.pack, 10, 'Q-MIX1') | self._receive(self.cells_nmc, 10, 'Q-MIX2'))
        self.assertEqual(len(rows), 2)
        with self.assertRaises(UserError):
            rows.action_create_production()

    def test_lot_without_next_stage_not_queued(self):
        lot = self._receive(self.cu_foil, 50, 'Q-FOIL')
        self.assertFalse(self._queue(lot))

    def test_next_stage_from_the_order(self):
        """ Dismantle -> shred -> recover, each created from the previous order's form. """
        self._receive(self.pack_nmc, 1000, 'N-PACK')
        dismantle = self._produce(self._create_mo(self.dismantle_nmc_bom, ug_input_qty=1000))
        cells_lot = dismantle.lot_producing_id
        self.assertEqual(dismantle.ug_next_queue_ids.lot_id, cells_lot)
        self.assertTrue(dismantle.ug_next_ready)

        shred = self.env['mrp.production'].browse(dismantle.action_ug_create_next_mo()['res_id'])
        self.assertEqual(shred.bom_id, self.shred_bom)
        self.assertEqual(shred.ug_input_lot_line_ids.source_production_id, dismantle)
        self.assertAlmostEqual(shred.ug_input_qty, 650)
        # the draft next order is already part of the chain; nothing left to plan
        self.assertEqual(dismantle.ug_chain_production_ids, dismantle | shred)
        dismantle.invalidate_recordset(['ug_next_queue_ids'])
        self.assertFalse(dismantle.ug_next_queue_ids)
        with self.assertRaises(UserError):
            dismantle.action_ug_create_next_mo()

        shred.action_confirm()
        self._produce(shred)
        self.assertTrue(shred.ug_next_waiting_lab)
        with self.assertRaisesRegex(UserError, 'waiting for the lab'):
            shred.action_ug_create_next_mo()
        self._approved_assay(shred.lot_producing_id)
        shred.invalidate_recordset(['ug_next_queue_ids', 'ug_next_ready', 'ug_next_waiting_lab'])
        recover = self.env['mrp.production'].browse(shred.action_ug_create_next_mo()['res_id'])
        self.assertEqual(recover.bom_id, self.recover_bom)
        self.assertTrue(recover.ug_recovery_line_ids)
        self.assertEqual(recover.ug_chain_production_ids.ids, [dismantle.id, shred.id, recover.id])
