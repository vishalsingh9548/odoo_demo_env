from odoo import api, fields, models, _


class StockPicking(models.Model):
    """Transfers into a Rejection location create scrap records automatically; outgoing transfers leave from MO Stock."""
    _inherit = 'stock.picking'

    scrap_count = fields.Integer(compute='_compute_scrap_count', string='Scrap Count')

    @api.model_create_multi
    def create(self, vals_list):
        """Deliveries leave from the MO Stock location (where packed units wait), when one is set up."""
        switch = self.env['advmfg.switch']
        for vals in vals_list:
            picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id'))
            company = self.env['res.company'].browse(vals.get('company_id') or picking_type.company_id.id or self.env.company.id)
            if picking_type.code == 'outgoing' and switch.is_active(company):
                mo_location = self.env['stock.location'].search([
                    ('is_mo_stock', '=', True), ('company_id', 'in', [company.id, False])], limit=1)
                if mo_location:
                    vals['location_id'] = mo_location.id
        return super().create(vals_list)

    def _compute_scrap_count(self):
        """Number of scrap records made from this transfer."""
        for pick in self:
            pick.scrap_count = self.env['stock.scrap'].search_count([('picking_id', '=', pick.id)])

    def action_view_scraps(self):
        """Scraps button: one scrap opens its form, several open a list."""
        self.ensure_one()
        scraps = self.env['stock.scrap'].search([('picking_id', '=', self.id)])
        action = self.env['ir.actions.act_window']._for_xml_id('stock.action_stock_scrap')
        if len(scraps) == 1:
            action['views'] = [(self.env.ref('stock.stock_scrap_form_view').id, 'form')]
            action['res_id'] = scraps.id
        else:
            action['domain'] = [('id', 'in', scraps.ids)]
        return action

    def button_validate(self):
        """After an internal transfer into a Rejection location is done, create a scrap record for each moved line."""
        res = super().button_validate()
        if isinstance(res, dict) and res.get('res_model'):
            return res
        for pick in self:
            if pick.state != 'done' or pick.picking_type_code != 'internal':
                continue
            if not self.env['advmfg.switch'].is_active(pick.company_id):
                continue
            for move in pick.move_ids.filtered(lambda m: m.location_dest_id.for_scrap_order):
                for line in move.move_line_ids.filtered('quantity'):
                    self.env['stock.scrap'].create({
                        'product_id': line.product_id.id, 'product_uom_id': line.product_uom_id.id,
                        'scrap_qty': line.quantity, 'location_id': line.location_dest_id.id,
                        'origin': pick.name, 'company_id': pick.company_id.id, 'picking_id': pick.id})
        return res


class StockScrap(models.Model):
    """A scrap record remembers the transfer that produced it."""
    _inherit = 'stock.scrap'

    picking_id = fields.Many2one('stock.picking', string='Transfer', readonly=True)


class ScrapSerialReportWizard(models.TransientModel):
    """Excel report: every cancelled unit with the components scrapped for it."""
    _name = 'scrap.serial.report.wizard'
    _description = 'Scrap Serial Excel Report'

    file_data = fields.Binary('File')
    file_name = fields.Char('Filename')

    def action_download_report(self):
        """Build the workbook (title, header with Component/Qty pairs, banded rows, total row) and download it."""
        import base64
        import io
        import xlsxwriter
        units = self.env['advmfg.unit'].search([('state', '=', 'cancel')])
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        ws = wb.add_worksheet('Scrap Serial Report')
        red, mid, light, grey = '#C0392B', '#E74C3C', '#FADBD8', '#F2F3F4'
        base = {'border': 1, 'border_color': '#D5D8DC', 'font_name': 'Arial', 'font_size': 10}
        f_title = wb.add_format({'bold': True, 'font_size': 16, 'font_color': red, 'bottom': 2, 'bottom_color': red})
        f_sub = wb.add_format({'italic': True, 'font_color': '#7F8C8D'})
        f_h = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=red, align='center'))
        f_hc = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=mid, align='center'))
        f_odd = wb.add_format(dict(base, bg_color='#FFFFFF'))
        f_even = wb.add_format(dict(base, bg_color=grey))
        f_c_odd = wb.add_format(dict(base, font_color='#922B21', bg_color='#FFFFFF'))
        f_c_even = wb.add_format(dict(base, font_color='#922B21', bg_color=light))
        f_tot = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=red, align='right'))
        f_totv = wb.add_format(dict(base, bold=True, font_color='#FFFFFF', bg_color=red, align='center'))
        most = max((len(u.scrap_ids) for u in units), default=0)
        heads = ['Serial Number', 'Manufacturing Order']
        for i in range(1, most + 1):
            heads += ['Component %s' % i, 'Qty %s' % i]
        cols = len(heads)
        ws.merge_range(0, 0, 0, cols - 1, 'Scrap Serial Report', f_title)
        ws.merge_range(1, 0, 1, cols - 1, 'Lines with status: Cancelled  |  Total records: %s' % len(units), f_sub)
        for i, h in enumerate(heads):
            ws.write(2, i, h, f_h if i < 2 else f_hc)
            ws.set_column(i, i, 24 if i < 2 or i % 2 == 0 else 10)
        ws.freeze_panes(3, 0)
        row = 3
        for n, unit in enumerate(units):
            odd = n % 2 == 0
            ws.write(row, 0, unit.name, f_odd if odd else f_even)
            ws.write(row, 1, unit.production_id.name or '', f_odd if odd else f_even)
            for j, scrap in enumerate(unit.scrap_ids):
                ws.write(row, 2 + j * 2, scrap.product_id.display_name, f_c_odd if odd else f_c_even)
                ws.write(row, 3 + j * 2, scrap.scrap_qty, f_c_odd if odd else f_c_even)
            row += 1
        if cols > 2:
            ws.merge_range(row, 0, row, cols - 2, 'Total Scrapped Lines', f_tot)
        else:
            ws.write(row, 0, 'Total Scrapped Lines', f_tot)
        ws.write(row, cols - 1, len(units), f_totv)
        ws.autofilter(2, 0, max(row - 1, 2), cols - 1)
        ws.set_landscape(); ws.set_paper(9)
        wb.close()
        self.write({'file_data': base64.b64encode(out.getvalue()), 'file_name': 'Scrap_Serial_Report.xlsx'})
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/?model=%s&id=%s&field=file_data&filename_field=file_name&download=true' % (self._name, self.id)}
