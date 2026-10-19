# -*- coding: utf-8 -*-
from odoo import fields, models


class EpcRejectWizard(models.TransientModel):
    """Small pop-up that asks the manager why a document is being sent back,
    then rejects it with that reason."""
    _name = 'epc.reject.wizard'
    _description = 'Reject a Solar EPC document'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    reason = fields.Text(
        string='Rejection Reason', required=True,
        help="Tell the person who submitted it what has to be corrected.",
    )

    # Writes the reason on the document and rejects it
    def action_confirm(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        record.write({'rejection_reason': self.reason})
        record.action_reject()
        return {'type': 'ir.actions.act_window_close'}
