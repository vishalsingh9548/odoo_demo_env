# -*- coding: utf-8 -*-
from odoo import fields, models


class EpcBoq(models.Model):
    """Remembers which System Design a BOQ was made from."""
    _inherit = 'epc.boq'

    design_id = fields.Many2one(
        'epc.design', string='System Design', copy=False,
        help="The approved System Design this BOQ was created from, if any.",
    )
