from odoo import api, models


class UgDemo(models.AbstractModel):
    _inherit = 'ug.demo'

    @api.model
    def _ug_demo_epr_flow(self):
        ref = self.env.ref
        dismantle = self.env['mrp.production'].search([
            ('state', '=', 'done'), ('ug_stage', '=', 'dismantle'), ('ug_epr_available_kg', '>', 0),
        ], limit=1)
        if not dismantle:
            return
        Certificate = self.env['ug.epr.certificate']
        listed = Certificate.create({
            'epr_category_id': ref('ug_epr.epr_category_ev').id,
            'battery_chemistry_id': ref('ug_recycling_base.chemistry_lfp').id,
            'quantity_kg': 600,
            'production_ids': [(6, 0, dismantle.ids)],
            'portal_certificate_no': 'CPCB/EPR/BWM/2026/000123',
            'partner_id': ref('ug_epr.partner_demo_producer').id,
            'price_per_kg': 18.0,
        })
        listed.action_generate()
        listed.action_list()
        listed.action_create_quotation()
        Certificate.create({
            'epr_category_id': ref('ug_epr.epr_category_ev').id,
            'battery_chemistry_id': ref('ug_recycling_base.chemistry_lfp').id,
            'quantity_kg': 400,
            'production_ids': [(6, 0, dismantle.ids)],
        })
