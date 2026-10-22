from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgQcFailWizard(models.TransientModel):
    """Small pop-up that forces the person to write WHY a quality check failed."""
    _name = 'advmfg.qc.fail.wizard'
    _description = 'Quality Check Failure Reason'

    qc_id = fields.Many2one('advmfg.qc', required=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        """Save the reason and mark the check as failed."""
        self.ensure_one()
        if self.qc_id.state != 'todo':
            raise UserError(_('This quality check is already %s.', self.qc_id.state))
        self.qc_id.write({'state': 'fail', 'fail_reason': self.reason})
        if self.qc_id.unit_id.state == 'yet_to_start':
            self.qc_id.unit_id.state = 'in_progress'
        return {'type': 'ir.actions.act_window_close'}
