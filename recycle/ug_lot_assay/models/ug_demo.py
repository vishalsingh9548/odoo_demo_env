from odoo import api, models

# spec demo assay of NMC black mass (%)
DEMO_NMC_RESULTS = {'Ni': 20, 'Co': 7, 'Mn': 6, 'Li': 3.5, 'C': 35, 'Al': 1, 'Cu': 1}
# illustrative assay of LFP black mass (%)
DEMO_LFP_RESULTS = {'Li': 2.8, 'Fe': 22, 'P': 12, 'C': 33, 'Al': 1.5, 'Cu': 1}


class UgDemo(models.AbstractModel):
    _inherit = 'ug.demo'

    @api.model
    def _ug_demo_approve_assay(self, lot, results, sample_ref=False):
        assay = lot.ug_assay_ids.filtered(lambda a: a.state == 'draft')[:1] or \
            self.env['ug.lot.assay'].create({'lot_id': lot.id})
        assay.sample_ref = sample_ref or f"LAB-{lot.name}"
        for line in assay.line_ids:
            line.percentage = results.get(line.element_id.code, 0.0)
        assay.action_submit()
        assay.action_approve()
        return assay

    @api.model
    def _ug_demo_assay_flow(self):
        # 1,000 kg NMC black mass with an approved assay (spec demo values)
        lot = self._ug_receive_lot('ug_recycling_base.product_bm_nmc', 'BM-NMC-DEMO-001', 1000)
        self._ug_demo_approve_assay(lot, DEMO_NMC_RESULTS, 'LAB-DEMO-001')
        # black mass produced by the demo shred MOs (NMC and LFP): draft assays for the lab
        black_mass = self.env.ref('ug_recycling_base.product_bm_nmc') | self.env.ref('ug_recycling_base.product_bm_lfp')
        shredded = self.env['stock.lot'].search([('product_id', 'in', black_mass.ids), ('id', '!=', lot.id)])
        self.env['ug.lot.assay']._ug_create_from_production(shredded)
