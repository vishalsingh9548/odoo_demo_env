# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # After the order is confirmed (and the core module made the project), create
    # the document pack. A problem here never stops the order from confirming.
    def action_confirm(self):
        result = super().action_confirm()
        for order in self.filtered('epc_project_id'):
            try:
                with self.env.cr.savepoint():
                    order.epc_project_id.sudo()._epc_create_documents()
            except Exception:  # pylint: disable=broad-except
                _logger.exception("Could not create the document pack for %s", order.name)
        return result
