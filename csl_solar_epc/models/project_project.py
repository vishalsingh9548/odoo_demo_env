# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectProject(models.Model):
    """Adds the 'Download Today's Report' DPR print action to the Project."""
    _inherit = 'project.project'

    # Instantly downloads today's progress report for this project — who
    # worked on it today, on what tasks, for how many hours — pulled live
    # from Timesheets. No form to fill in and nothing is saved; it's a
    # straight print, so it can be run again any day.
    def action_print_today_dpr(self):
        self.ensure_one()
        return self.env.ref('csl_solar_epc.epc_report_dpr_today_pdf_action').report_action(self)
