# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    """Stage 10 of the EPC pipeline: Site Execution. Adds the standard solar
    installation checkpoints as simple tick-boxes on a Field Service task, so
    the site engineer can mark real physical progress (civil work, structure,
    cabling, earthing, testing) directly against the task they're working on.
    """
    _inherit = 'project.task'

    civil_work_done = fields.Boolean(
        string='Civil Work & Foundation Done',
        help="Tick this once the foundation/civil work for the mounting structure is complete.",
    )
    civil_work_date = fields.Date(
        string='Civil Work Date', help="The date civil work was completed.",
    )
    structure_installation_done = fields.Boolean(
        string='Structure Installation Done',
        help="Tick this once the mounting structure has been erected on site.",
    )
    structure_installation_date = fields.Date(
        string='Structure Installation Date', help="The date the mounting structure was installed.",
    )
    module_installation_done = fields.Boolean(
        string='Module Installation Done',
        help="Tick this once the solar panels have been mounted on the structure.",
    )
    module_installation_date = fields.Date(
        string='Module Installation Date', help="The date the solar panels were installed.",
    )
    dc_cabling_done = fields.Boolean(
        string='DC Cabling Done',
        help="Tick this once the DC-side cabling (panels to inverter) is complete.",
    )
    dc_cabling_date = fields.Date(
        string='DC Cabling Date', help="The date DC cabling was completed.",
    )
    ac_cabling_done = fields.Boolean(
        string='AC Cabling Done',
        help="Tick this once the AC-side cabling (inverter to LT panel/grid) is complete.",
    )
    ac_cabling_date = fields.Date(
        string='AC Cabling Date', help="The date AC cabling was completed.",
    )
    lt_panel_installation_done = fields.Boolean(
        string='LT Panel / Inverter Installation Done',
        help="Tick this once the LT panel and inverter have been installed and connected.",
    )
    lt_panel_installation_date = fields.Date(
        string='LT Panel / Inverter Installation Date', help="The date the LT panel/inverter were installed.",
    )
    earthing_done = fields.Boolean(
        string='Earthing Done',
        help="Tick this once the earthing/grounding work is complete, as required for safety.",
    )
    earthing_date = fields.Date(
        string='Earthing Date', help="The date earthing work was completed.",
    )
    testing_precommissioning_done = fields.Boolean(
        string='Testing & Pre-Commissioning Done',
        help="Tick this once the installation has passed its pre-commissioning electrical tests.",
    )
    testing_precommissioning_date = fields.Date(
        string='Testing & Pre-Commissioning Date', help="The date pre-commissioning testing was completed.",
    )
