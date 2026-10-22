from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgQc(models.Model):
    """A quality check for ONE unit at ONE stage. Result is Pass or Fail."""
    _name = 'advmfg.qc'
    _description = 'Unit Quality Check'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    unit_id = fields.Many2one('advmfg.unit', required=True, ondelete='cascade')
    stage_id = fields.Many2one('advmfg.stage', required=True)
    production_id = fields.Many2one(related='unit_id.production_id', store=True)
    company_id = fields.Many2one(related='unit_id.company_id', store=True)
    state = fields.Selection(
        [('todo', 'To Do'), ('pass', 'Pass'), ('fail', 'Fail')], default='todo', required=True)
    # Why it failed - mandatory when failing.
    fail_reason = fields.Text(readonly=True)
    serial_number = fields.Char(related='unit_id.name', store=True)
    sale_order_id = fields.Many2one('sale.order', related='unit_id.sale_order_id', string='SO #')
    # Documents (photos, reports) attached to this check.
    attachment_ids = fields.Many2many('ir.attachment', 'advmfg_qc_attachment_rel', 'qc_id', 'attachment_id',
                                      string='Attachments')
    attachment_count = fields.Integer(compute='_compute_attachment_count')

    def _compute_attachment_count(self):
        """How many documents are attached (shown on the Attachments button)."""
        for qc in self:
            qc.attachment_count = len(qc.attachment_ids)

    def action_view_attachments(self):
        """Attachments button: opens the window to upload documents for this check."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Upload Attachments'),
            'res_model': 'advmfg.qc.attachment.wizard', 'view_mode': 'form', 'target': 'new',
            'context': {'default_qc_id': self.id, 'default_attachment_ids': [(6, 0, self.attachment_ids.ids)]},
        }

    def _compute_name(self):
        """Display name like 'SERIAL - Stage name'."""
        for qc in self:
            qc.name = '%s - %s' % (qc.unit_id.name or '', qc.stage_id.name or '')

    def action_pass(self):
        """Mark the check as passed. A passed unit is also auto-started if it hadn't started yet."""
        for qc in self:
            if qc.state != 'todo':
                raise UserError(_('This quality check is already %s.', qc.state))
            qc.state = 'pass'
            if qc.unit_id.state == 'yet_to_start':
                qc.unit_id.state = 'in_progress'
        return True

    def action_fail(self):
        """Open the small window that asks for the failure reason."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Failure Reason'),
            'res_model': 'advmfg.qc.fail.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_qc_id': self.id},
        }
