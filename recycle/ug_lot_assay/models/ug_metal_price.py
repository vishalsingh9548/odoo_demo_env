from odoo import api, fields, models


class UgMetalPrice(models.Model):
    _name = 'ug.metal.price'
    _description = 'Metal Price'
    _order = 'date desc, id desc'

    element_id = fields.Many2one('ug.assay.element', string='Element', required=True, index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    price_per_kg = fields.Monetary('Price per kg of metal', required=True)
    currency_id = fields.Many2one('res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', required=True, index=True,
        default=lambda self: self.env.company)

    @api.model
    def _ug_latest_prices(self, company, date=None):
        """ {element: price per kg in company currency}, latest price by date wins. """
        date = date or fields.Date.context_today(self)
        prices = {}
        for price in self.search([('company_id', '=', company.id), ('date', '<=', date)], order='date desc, id desc'):
            if price.element_id in prices:
                continue
            prices[price.element_id] = price.currency_id._convert(
                price.price_per_kg, company.currency_id, company, date)
        return prices
