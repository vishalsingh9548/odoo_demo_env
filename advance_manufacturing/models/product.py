from odoo import fields, models


class ProductTemplate(models.Model):
    """Two product flags: 'finished good' and 'keep its manufacturing orders in Draft'."""
    _inherit = 'product.template'

    # Only finished goods can be chosen on a manufacturing order (when Advance Manufacturing is on).
    is_finished_good = fields.Boolean(string='Is Finished Good')
    # After a sale order is confirmed, manufacturing orders for this product wait in Draft.
    keep_mo_in_draft = fields.Boolean(
        string='Keep Manufacturing Orders in Draft', default=True,
        help='When ticked, manufacturing orders created from a sale order stay in Draft '
             'until the production team confirms them.')


class StockRoute(models.Model):
    """A route-level default for the Draft rule (kept for configuration; products decide)."""
    _inherit = 'stock.route'

    keep_mo_in_draft_by_default = fields.Boolean(
        string='Keep MO in Draft by Default',
        help='Default for products using this route: keep manufacturing orders in Draft.')
