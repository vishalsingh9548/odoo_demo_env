import base64
import io
from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError


class MaterialRequisitionExcelWizard(models.TransientModel):
    """Purchase Requisition Excel Report: requisitions raised between two dates, as a spreadsheet."""
    _name = 'material.requisition.excel.wizard'
    _description = 'Purchase Requisition Excel Report'

    start_date = fields.Date(required=True, default=lambda self: fields.Date.today() - timedelta(days=30))
    end_date = fields.Date(required=True, default=fields.Date.today)
    request_raised_by = fields.Many2many('hr.employee', 'mr_excel_by_rel', 'wiz_id', 'emp_id', string='Request Raised By')
    request_raised_for = fields.Many2many('hr.employee', 'mr_excel_for_rel', 'wiz_id', 'emp_id', string='Request Raised For')
    report_file = fields.Binary(readonly=True)
    report_file_name = fields.Char()

    def action_download(self):
        """Build the Excel file and return a download link."""
        import xlsxwriter
        self.ensure_one()
        domain = [('indented_date', '>=', '%s 00:00:00' % self.start_date), ('indented_date', '<=', '%s 23:59:59' % self.end_date)]
        if self.request_raised_by:
            domain.append(('request_raised_by', 'in', self.request_raised_by.ids))
        if self.request_raised_for:
            domain.append(('request_raised_for', 'in', self.request_raised_for.ids))
        reqs = self.env['material.requisition'].search(domain, order='indented_date')
        if not reqs:
            raise UserError(_('No Material Requisitions found for the selected criteria.'))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        ws = wb.add_worksheet('Material Requisition Report')
        bold = wb.add_format({'bold': True, 'border': 1, 'bg_color': '#D9E1F2'})
        cell = wb.add_format({'border': 1})
        title = wb.add_format({'bold': True, 'font_size': 14})
        ws.write(0, 0, self.env.company.name, title)
        ws.write(1, 0, 'Material Requisition Report', title)
        ws.write(3, 0, 'Start Date'); ws.write(3, 1, str(self.start_date))
        ws.write(4, 0, 'End Date'); ws.write(4, 1, str(self.end_date))
        ws.write(5, 0, 'Request Raised By'); ws.write(5, 1, ', '.join(self.request_raised_by.mapped('name')) or 'All')
        ws.write(6, 0, 'Request Raised For'); ws.write(6, 1, ', '.join(self.request_raised_for.mapped('name')) or 'All')
        heads = ['S.No.', 'Requisition Reference', 'Date', 'Raised By', 'Raised For', 'Department', 'Status',
                 'Product', 'Requested Qty', 'Unit']
        for i, h in enumerate(heads):
            ws.write(8, i, h, bold)
            ws.set_column(i, i, 22)
        row, n = 9, 0
        for r in reqs:
            for line in r.material_requisition_line_ids:
                n += 1
                vals = [n, r.name, str(r.indented_date), r.request_raised_by.name, r.request_raised_for.name or '',
                        r.department_id.name or '', r.state_label, line.product_id.display_name, line.product_uom_qty,
                        line.product_uom.name]
                for i, v in enumerate(vals):
                    ws.write(row, i, v, cell)
                row += 1
        wb.close()
        self.write({'report_file': base64.b64encode(out.getvalue()), 'report_file_name': 'Material_Requisition_Report.xlsx'})
        return {'type': 'ir.actions.act_url', 'target': 'self',
                'url': '/web/content/?model=%s&id=%s&field=report_file&filename_field=report_file_name&download=true' % (self._name, self.id)}
