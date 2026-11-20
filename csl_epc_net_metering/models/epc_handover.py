# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class EpcHandover(models.Model):
    _inherit = 'epc.handover'

    # Optional rule (switch off by default): an open net-metering application must be synced first
    def action_approve(self):
        if self.env['epc.config'].flag('handover_require_net_meter'):
            for handover in self:
                open_apps = handover.project_id.net_meter_ids.filtered(lambda a: a.state not in ('synced', 'rejected'))
                if open_apps:
                    raise UserError("The net-metering application of this project is not synced yet "
                                    "(%s). Finish it before approving the handover." % open_apps[0].name)
        return super().action_approve()
