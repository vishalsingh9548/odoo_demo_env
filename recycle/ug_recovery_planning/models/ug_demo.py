from odoo import api, models

from odoo.addons.ug_lot_assay.models.ug_demo import DEMO_LFP_RESULTS, DEMO_NMC_RESULTS


class UgDemo(models.AbstractModel):
    _inherit = 'ug.demo'

    @api.model
    def _ug_demo_recover_mo(self, lot, qty_kg, bom_xmlid='ug_recycling_base.bom_recover_nmc'):
        production = self._ug_run_mo(bom_xmlid, qty_kg, done=False)
        production.ug_input_lot_line_ids = [(0, 0, {'lot_id': lot.id, 'qty_kg': qty_kg})]
        production.action_ug_compute_expected()
        return production

    @api.model
    def _ug_demo_recovery_flow(self):
        ref = self.env.ref
        # 1. draft recover MO on the spec lot (expected outputs computed)
        spec_lot = self.env['stock.lot'].search([('name', '=', 'BM-NMC-DEMO-001')], limit=1)
        if spec_lot:
            self._ug_demo_recover_mo(spec_lot, 1000)
        # 2. connected chains, stage 3: the black mass from the demo shred MOs is assayed,
        #    then fully recovered into sellable salts
        for chemical in ('h2so4', 'h2o2', 'naoh', 'sx', 'na2co3'):
            self._ug_receive(f'ug_recycling_base.product_{chemical}', 5000)
        chains = [
            ('ug_recycling_base.product_bm_nmc', DEMO_NMC_RESULTS, 'ug_recycling_base.bom_recover_nmc'),
            ('ug_recycling_base.product_bm_lfp', DEMO_LFP_RESULTS, 'ug_recycling_base.bom_recover_lfp'),
        ]
        for product_xmlid, results, bom_xmlid in chains:
            chain_lot = self.env['stock.lot'].search([
                ('product_id', '=', ref(product_xmlid).id), ('id', '!=', spec_lot.id), ('product_qty', '>', 0)], limit=1)
            if not chain_lot:
                continue
            self._ug_demo_approve_assay(chain_lot, results)
            production = self._ug_demo_recover_mo(chain_lot, chain_lot._ug_qty_kg(), bom_xmlid)
            production.action_confirm()
            self._ug_finish_mo(production)
