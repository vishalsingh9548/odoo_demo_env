# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    epc_docs_block_commissioning = fields.Boolean(
        string='Documents Block Commissioning', config_parameter='csl_epc.docs_block_commissioning',
        help="Commissioning cannot be submitted while mandatory project documents are still pending. "
             "Off by default.",
    )
