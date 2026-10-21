from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ug_block_unassayed_lots = fields.Boolean(related='company_id.ug_block_unassayed_lots', readonly=False)
