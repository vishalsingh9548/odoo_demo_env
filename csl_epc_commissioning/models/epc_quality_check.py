# -*- coding: utf-8 -*-
from odoo import models


class EpcQualityCheck(models.Model):
    """A failed Final QC is also written on the project's Commissioning record(s)."""
    _inherit = 'epc.quality.check'

    def _epc_failure_documents(self):
        documents = super()._epc_failure_documents()
        if self.category == 'final':
            documents.extend(self.env['epc.commissioning'].sudo().search([('project_id', '=', self.project_id.id)]))
        return documents
