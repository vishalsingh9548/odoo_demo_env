# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class EpcCommissioning(models.Model):
    _inherit = 'epc.commissioning'

    # Optional rule (switch is off by default): mandatory papers must be done first
    def action_submit(self):
        if self.env['epc.config'].flag('docs_block_commissioning'):
            for commissioning in self:
                pending = commissioning.project_id.epc_document_pending_mandatory
                if pending:
                    raise UserError(
                        "%s mandatory document(s) of this project are not submitted yet. "
                        "Finish the document pack before commissioning." % pending)
        return super().action_submit()
