# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    epc_handover_require_net_meter = fields.Boolean(
        string='Handover Needs Net-Meter Sync', config_parameter='csl_epc.handover_require_net_meter',
        help="A handover can only be approved once any open net-metering application of the project is synced.",
    )
    epc_netmeter_stuck_days = fields.Integer(
        string='Net-Metering Stuck After (days)', config_parameter='csl_epc.netmeter_stuck_days', default=15,
        help="A to-do is created when a net-metering application does not move for this many days.",
    )
