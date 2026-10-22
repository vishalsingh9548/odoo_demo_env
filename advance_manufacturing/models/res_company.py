from odoo import fields, models


class ResCompany(models.Model):
    """Adds the company-level settings: the on/off switch and a few defaults."""
    _inherit = 'res.company'

    # The company-level switch. Off = this company uses plain Odoo manufacturing.
    advmfg_enabled = fields.Boolean(
        string='Advance Manufacturing',
        help='Turn on unit-by-unit manufacturing for this company. Users also need the '
             '"Advance Manufacturing" group.')
    # Text put in front of every serial number, e.g. "EXPO" gives EXPO00001.
    advmfg_serial_prefix = fields.Char(
        string='Serial Prefix',
        help='Letters placed in front of each serial number, e.g. EXPO gives EXPO00001.')
    # Most units that fit on one pallet.
    advmfg_max_pallet_qty = fields.Integer(
        string='Max Units per Pallet', default=28,
        help='A pallet can never hold more than this many units.')
    # Where finished units are stored once the manufacturing order is done (the "packed" area).
    advmfg_packed_location_id = fields.Many2one(
        'stock.location', string='Packed Stock Location',
        domain="[('usage', '=', 'internal')]",
        help='If set, finished units of a done manufacturing order are stored here '
             'instead of the normal finished-goods location.')
