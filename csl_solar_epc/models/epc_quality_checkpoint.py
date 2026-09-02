# -*- coding: utf-8 -*-
from odoo import fields, models


class EpcQualityCheckpoint(models.Model):
    """A configurable master list of checklist items to suggest for each
    Quality Check category. Previously this list was hardcoded in Python (so
    changing it meant changing code); now a Project Manager can add, rename,
    reorder or switch off checkpoints from Solar EPC > Configuration > QC
    Checkpoints, and every new Quality Check picks up the change immediately.
    """
    _name = 'epc.quality.checkpoint'
    _description = 'Solar Quality Checkpoint'
    _order = 'category, sequence, id'

    name = fields.Char(
        string='Checkpoint', required=True,
        help="What this checklist item actually checks, e.g. 'Earthing QC' "
             "or 'Insulation Test'. Shown as-is on the Quality Check form.",
    )
    category = fields.Selection(
        [
            ('incoming_material', 'Incoming Material QC'),
            ('final', 'Final QC'),
        ],
        string='QC Category', required=True,
        help="Which Quality Check category this checkpoint gets suggested "
             "for. For Incoming Material QC, checkpoints added here appear "
             "on every check alongside a line for each product actually on "
             "the delivery — use it for things that apply to every delivery "
             "regardless of product, e.g. 'Packaging Condition' or "
             "'Delivery Challan Matches PO'.",
    )
    sequence = fields.Integer(
        string='Sequence', default=10,
        help="Controls the order checkpoints appear in within their category.",
    )
    active = fields.Boolean(
        string='Active', default=True,
        help="Untick to stop suggesting this checkpoint on new Quality "
             "Checks, without deleting it (and losing the history of past "
             "checks that already used it).",
    )
