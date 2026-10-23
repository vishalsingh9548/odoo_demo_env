from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductTemplate(models.Model):
    """How many samples to inspect when this product is received."""
    _inherit = 'product.template'

    qc_sample_count = fields.Integer(string='QC Sample Count', default=1,
                                     help='Number of samples to inspect on each incoming receipt.')


class PurchaseOrderLine(models.Model):
    """Finished goods are made, not bought."""
    _inherit = 'purchase.order.line'

    @api.constrains('product_id')
    def _check_not_finished_good(self):
        """In Advance Manufacturing mode a finished good cannot be put on a purchase order."""
        for line in self:
            if line.product_id and self.env['advmfg.switch'].is_active(line.company_id) \
                    and line.product_id.product_tmpl_id.is_finished_good:
                raise ValidationError(_('Finished goods cannot be purchased: %s.', line.product_id.display_name))


class AdvmfgReceiptQc(models.Model):
    """Incoming quality check: one per product on a receipt, to be passed before the receipt is validated."""
    _name = 'advmfg.receipt.qc'
    _description = 'Incoming Quality Check'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    picking_id = fields.Many2one('stock.picking', string='Receipt', required=True, ondelete='cascade')
    purchase_id = fields.Many2one('purchase.order', related='picking_id.purchase_id', store=True)
    product_id = fields.Many2one('product.product', required=True)
    sample_count = fields.Integer(string='Samples to Inspect', default=1)
    state = fields.Selection([('todo', 'To Do'), ('pass', 'Pass'), ('fail', 'Fail')], default='todo', required=True)
    fail_reason = fields.Text()
    company_id = fields.Many2one(related='picking_id.company_id', store=True)
    note = fields.Text(string='Inspection Notes')

    @api.depends('picking_id', 'product_id')
    def _compute_name(self):
        """'Receipt - Product'."""
        for qc in self:
            qc.name = '%s - %s' % (qc.picking_id.name or '', qc.product_id.display_name or '')

    def action_pass(self):
        """Mark the inspection as passed."""
        self.write({'state': 'pass'})
        return True

    def action_fail(self):
        """Mark the inspection as failed (a reason is needed in the notes)."""
        for qc in self:
            if not qc.note:
                raise UserError(_('Please write the reason for the failure in the Inspection Notes first.'))
            qc.write({'state': 'fail', 'fail_reason': qc.note})
        return True


class StockPicking(models.Model):
    """Receipts create incoming quality checks, and cannot be validated until they are all done."""
    _inherit = 'stock.picking'

    receipt_qc_ids = fields.One2many('advmfg.receipt.qc', 'picking_id', string='Incoming Quality Checks')
    receipt_qc_count = fields.Integer(compute='_compute_receipt_qc_count')

    def _compute_receipt_qc_count(self):
        """Number of incoming checks on the receipt."""
        for pick in self:
            pick.receipt_qc_count = len(pick.receipt_qc_ids)

    def _advmfg_create_receipt_qcs(self):
        """One check per product of a receipt (skipped for products that already have one)."""
        for pick in self:
            if pick.picking_type_code != 'incoming' or not self.env['advmfg.switch'].is_active(pick.company_id):
                continue
            for move in pick.move_ids.filtered(lambda m: m.product_id.type == 'consu'):
                if not pick.receipt_qc_ids.filtered(lambda q: q.product_id == move.product_id):
                    self.env['advmfg.receipt.qc'].create({
                        'picking_id': pick.id, 'product_id': move.product_id.id,
                        'sample_count': move.product_id.product_tmpl_id.qc_sample_count or 1})

    def action_confirm(self):
        """After a receipt is confirmed, create its incoming quality checks."""
        res = super().action_confirm()
        self._advmfg_create_receipt_qcs()
        return res

    def button_validate(self):
        """A receipt cannot be validated while an incoming quality check is still open."""
        for pick in self:
            if pick.picking_type_code == 'incoming' and self.env['advmfg.switch'].is_active(pick.company_id):
                pick._advmfg_create_receipt_qcs()
                if pick.receipt_qc_ids.filtered(lambda q: q.state == 'todo'):
                    raise UserError(_('You cannot validate this transfer until all Purchase Quality Checks are done.'))
        return super().button_validate()

    def action_view_receipt_qcs(self):
        """Quality Checks button on the receipt."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Incoming Quality Checks'), 'res_model': 'advmfg.receipt.qc',
                'view_mode': 'list,form', 'domain': [('picking_id', '=', self.id)]}


class StockMove(models.Model):
    """Whenever receipt moves are confirmed, make sure the receipt has its incoming quality checks."""
    _inherit = 'stock.move'

    def _action_confirm(self, merge=True, merge_into=False):
        """After confirming, create incoming quality checks for the receipts these moves belong to."""
        moves = super()._action_confirm(merge=merge, merge_into=merge_into)
        moves.picking_id._advmfg_create_receipt_qcs()
        return moves
