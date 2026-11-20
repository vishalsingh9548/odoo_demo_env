# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    epc_require_design = fields.Boolean(
        string='Require Approved Design Before BOQ', config_parameter='csl_epc.require_design',
        help="A BOQ can only be created from a feasibility study that has an "
             "approved System Design. Off by default, so nothing changes until you switch it on.",
    )
