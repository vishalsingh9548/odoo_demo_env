# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    net_meter_ids = fields.One2many('epc.net.meter', 'project_id', string='Net Metering', help="Net-metering applications of this project.")
    net_meter_count = fields.Integer(string='Net Metering', compute='_compute_net_meter_count', help="How many net-metering applications this project has.")

    @api.depends('net_meter_ids')
    def _compute_net_meter_count(self):
        for project in self:
            project.net_meter_count = len(project.net_meter_ids)

    # Opens (or starts) the net-metering application of this project
    def action_view_net_meter(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Net Metering', 'res_model': 'epc.net.meter',
            'view_mode': 'list,form', 'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
