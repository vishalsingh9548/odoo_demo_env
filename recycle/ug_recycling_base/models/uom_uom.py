import logging

from odoo import models
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class UomUom(models.Model):
    _inherit = 'uom.uom'

    def _ug_is_weight(self):
        """ True when this unit shares its reference unit with the kilogram. """
        self.ensure_one()
        return self.category_id == self.env.ref('uom.product_uom_categ_kgm')

    def _ug_compare(self, value1, value2):
        self.ensure_one()
        return float_compare(value1, value2, precision_rounding=self.rounding)

    def _ug_is_zero(self, value):
        self.ensure_one()
        return float_is_zero(value, precision_rounding=self.rounding)

    def _ug_to_kg(self, qty, warn_label=''):
        """ Convert `qty` expressed in this unit to kg.

        A unit is a weight unit when it belongs to the `Weight` UoM category
        (Odoo 18 still has UoM categories). Non-weight units are
        ignored (0.0 is returned) and a warning is logged.
        """
        if not self or not qty:
            return 0.0
        self.ensure_one()
        if not self._ug_is_weight():
            _logger.warning(
                "Recycling: unit %s is not a weight unit, quantity %s ignored%s",
                self.name, qty, warn_label and f" ({warn_label})" or "",
            )
            return 0.0
        return self._compute_quantity(qty, self.env.ref('uom.product_uom_kgm'), round=False)

    def _ug_from_kg(self, qty_kg):
        """ Convert a kg quantity into this unit (0.0 if not a weight unit). """
        if not self or not qty_kg:
            return 0.0
        self.ensure_one()
        kg = self.env.ref('uom.product_uom_kgm')
        if not self._ug_is_weight():
            _logger.warning("Recycling: unit %s is not a weight unit, cannot convert from kg", self.name)
            return 0.0
        return kg._compute_quantity(qty_kg, self, round=False)
