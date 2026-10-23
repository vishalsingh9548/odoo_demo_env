from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AdvmfgQcAttachmentWizard(models.TransientModel):
    """Small window to upload documents onto a quality check."""
    _name = 'advmfg.qc.attachment.wizard'
    _description = 'Upload Quality Check Attachments'

    qc_id = fields.Many2one('advmfg.qc', required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    def action_save(self):
        """Attach the uploaded files to the check and re-tag them so other users can open them."""
        self.ensure_one()
        self.attachment_ids.sudo().write({'res_model': 'advmfg.qc', 'res_id': self.qc_id.id})
        self.qc_id.attachment_ids = [(6, 0, self.attachment_ids.ids)]
        return {'type': 'ir.actions.act_window_close'}


class AdvmfgAttachmentBulkWizard(models.TransientModel):
    """Upload one document per unit per stage, for a whole order in one go."""
    _name = 'advmfg.attachment.bulk.wizard'
    _description = 'Update Bulk Attachments'

    line_ids = fields.One2many('advmfg.attachment.bulk.line', 'wizard_id', string='Attachments')

    @api.model
    def default_get(self, fields_list):
        """Pre-fill one row for each unit at (or before) a stage that needs a document."""
        res = super().default_get(fields_list)
        mo = self.env['mrp.production'].browse(self.env.context.get('active_id'))
        lines = []
        for unit in mo.advmfg_unit_ids.filtered(lambda u: u.state not in ('cancel',)):
            stages = self.env['advmfg.stage'].search([
                ('company_id', '=', unit.company_id.id), ('attachment_required', '=', True),
                ('sequence', '<=', unit.stage_id.sequence or 0)])
            for stage in stages:
                lines.append((0, 0, {'serial_number': unit.name, 'stage_id': stage.id, 'unit_id': unit.id}))
        res['line_ids'] = lines
        return res

    def action_update(self):
        """Attach every uploaded file to its unit (re-tagged so nobody gets an access error)."""
        self.ensure_one()
        for line in self.line_ids.filtered('attachment_ids'):
            line.attachment_ids.sudo().write({'res_model': 'advmfg.unit', 'res_id': line.unit_id.id})
            line.unit_id.attachment_ids = [(4, a.id) for a in line.attachment_ids]
        return {'type': 'ir.actions.act_window_close'}


class AdvmfgAttachmentBulkLine(models.TransientModel):
    """One row of the bulk upload: a unit, a stage, and its document."""
    _name = 'advmfg.attachment.bulk.line'
    _description = 'Bulk Attachment Row'

    wizard_id = fields.Many2one('advmfg.attachment.bulk.wizard', ondelete='cascade')
    unit_id = fields.Many2one('advmfg.unit')
    serial_number = fields.Char(readonly=True)
    stage_id = fields.Many2one('advmfg.stage', string='Process', readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachment')

    @api.constrains('attachment_ids')
    def _check_one_attachment(self):
        """Only one document per row."""
        for line in self:
            if len(line.attachment_ids) > 1:
                raise ValidationError(_('Only one attachment is allowed.'))
