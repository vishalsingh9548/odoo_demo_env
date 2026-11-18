# -*- coding: utf-8 -*-
from odoo import models

INSTALLATION_MILESTONE = 'Structure & Module Installation'


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    # When the seeded "Structure & Module Installation Complete" milestone is
    # reached, wake up 'installation complete' payment stages
    def write(self, vals):
        result = super().write(vals)
        if vals.get('is_reached'):
            for milestone in self.filtered(lambda m: m.name and m.name.startswith(INSTALLATION_MILESTONE)):
                order = milestone.project_id.epc_sale_order_id
                if order and order.sudo().milestone_ids:
                    order._epc_trigger_milestones('installation_done')
        return result
