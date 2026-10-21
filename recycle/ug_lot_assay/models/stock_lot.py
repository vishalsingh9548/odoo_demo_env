from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = 'stock.lot'

    ug_assay_ids = fields.One2many('ug.lot.assay', 'lot_id', string='Assays')
    ug_assay_count = fields.Integer(compute='_compute_ug_assay_count', string='Assay Count')
    ug_current_assay_id = fields.Many2one('ug.lot.assay', string='Current Assay',
        compute='_compute_ug_current_assay_id', store=True, index=True)
    ug_current_assay_line_ids = fields.One2many(related='ug_current_assay_id.line_ids', string='Composition')
    ug_requires_assay = fields.Boolean(related='product_id.ug_requires_assay')
    ug_assay_state = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ], string='Assay Status', compute='_compute_ug_assay_state', store=True, index=True)
    ug_currency_id = fields.Many2one('res.currency', compute='_compute_ug_estimated_metal_value')
    ug_estimated_metal_value = fields.Monetary('Estimated Metal Value', currency_field='ug_currency_id',
        compute='_compute_ug_estimated_metal_value',
        help="Estimate only – not accounting valuation. Contained metal (current quantity × current "
             "assay) priced at the latest metal price of each element.")

    def _compute_ug_assay_count(self):
        counts = dict(self.env['ug.lot.assay']._read_group(
            [('lot_id', 'in', self.ids)], ['lot_id'], ['__count']))
        for lot in self:
            lot.ug_assay_count = counts.get(lot, 0)

    @api.depends('ug_assay_ids.is_current', 'ug_assay_ids.state')
    def _compute_ug_current_assay_id(self):
        for lot in self:
            lot.ug_current_assay_id = lot.ug_assay_ids.filtered(
                lambda a: a.is_current and a.state == 'approved')[:1]

    @api.depends('product_id.ug_requires_assay', 'ug_current_assay_id')
    def _compute_ug_assay_state(self):
        for lot in self:
            if not lot.product_id.ug_requires_assay:
                lot.ug_assay_state = 'not_required'
            elif lot.ug_current_assay_id:
                lot.ug_assay_state = 'approved'
            else:
                lot.ug_assay_state = 'pending'

    def _ug_qty_kg(self):
        """ Current on-hand quantity of the lot in kg (0 for non-weight units). """
        self.ensure_one()
        if not self.product_id:
            return 0.0
        return self.product_id.uom_id._ug_to_kg(self.product_qty, warn_label=self.display_name)

    def _compute_ug_estimated_metal_value(self):
        for lot in self:
            company = lot.company_id or self.env.company
            lot.ug_currency_id = company.currency_id
            value = 0.0
            if lot.ug_current_assay_id:
                prices = self.env['ug.metal.price']._ug_latest_prices(company)
                for line in lot.ug_current_assay_id.line_ids:
                    value += line.contained_kg_current * prices.get(line.element_id, 0.0)
            lot.ug_estimated_metal_value = value

    def action_ug_view_assays(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ug_lot_assay.ug_lot_assay_action')
        action['domain'] = [('lot_id', '=', self.id)]
        action['context'] = {'default_lot_id': self.id, 'default_company_id': (self.company_id or self.env.company).id}
        return action

    def action_ug_print_coa(self):
        lots = self.filtered('ug_current_assay_id')
        if not lots:
            raise UserError(_("No approved assay on the selected lot(s)."))
        return self.env.ref('ug_lot_assay.action_report_ug_coa').report_action(lots)
