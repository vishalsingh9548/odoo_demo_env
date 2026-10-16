from odoo.fields import Command

from odoo.addons.ug_recycling_base.tests.common import UgRecyclingCommon


class UgAssayCommon(UgRecyclingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.el = {code: ref(f'ug_lot_assay.element_{code}') for code in ('ni', 'co', 'mn', 'li', 'c', 'al', 'cu', 'fe')}
        cls.template = cls.env['ug.assay.template'].create({
            'name': 'T NMC black mass',
            'element_ids': [Command.set([cls.el[c].id for c in ('ni', 'co', 'mn', 'li', 'c', 'al', 'cu')])],
        })
        cls.bm = cls._product('T Black mass NMC', 'intermediate', chem=cls.nmc)
        cls.bm.write({'ug_requires_assay': True, 'ug_assay_template_id': cls.template.id})
        cls.cells_nmc = cls._product('T Cells NMC', 'intermediate', chem=cls.nmc)
        cls.cu_foil = cls._product('T Cu foil', 'scrap_byproduct')
        cls.niso4 = cls._product('T Nickel sulphate', 'recovered_material')
        cls.shred_bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.bm.product_tmpl_id.id, 'product_qty': 750, 'product_uom_id': cls.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'shred', 'ug_max_loss_pct': 20,
            'bom_line_ids': [Command.create({'product_id': cls.cells_nmc.id, 'product_qty': 1000,
                                             'ug_is_primary_input': True})],
            'byproduct_ids': [Command.create({'product_id': cls.cu_foil.id, 'product_qty': 90,
                                              'product_uom_id': cls.kg.id, 'cost_share': 6})],
        })
        cls.recover_bom = cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.niso4.product_tmpl_id.id, 'product_qty': 850, 'product_uom_id': cls.kg.id,
            'ug_is_recycling': True, 'ug_stage': 'recover',
            'bom_line_ids': [Command.create({'product_id': cls.bm.id, 'product_qty': 1000,
                                             'ug_is_primary_input': True})],
        })
        cls.spec_results = {'ni': 20, 'co': 7, 'mn': 6, 'li': 3.5, 'c': 35, 'al': 1, 'cu': 1}

    def _approved_assay(self, lot, results=None):
        results = results or self.spec_results
        assay = self.env['ug.lot.assay'].create({'lot_id': lot.id})
        for line in assay.line_ids:
            code = next(c for c, el in self.el.items() if el == line.element_id)
            line.percentage = results.get(code, 0.0)
        assay.action_submit()
        assay.action_approve()
        return assay
