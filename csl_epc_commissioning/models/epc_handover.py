# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class EpcHandover(models.Model):
    """When the "Handover Needs Approved Commissioning" switch is on, a handover can
    only be approved once the project's commissioning has been approved."""
    _inherit = 'epc.handover'

    def action_approve(self):
        if self.env['epc.config'].flag('handover_require_commissioning'):
            for handover in self:
                approved = self.env['epc.commissioning'].sudo().search_count([
                    ('project_id', '=', handover.project_id.id),
                    ('approval_state', '=', 'approved'),
                ])
                if not approved:
                    raise UserError("This project has no approved commissioning yet.")
        return super().action_approve()
