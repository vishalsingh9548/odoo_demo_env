from odoo import _, api, fields, models


class UgWasteManifest(models.Model):
    _name = 'ug.waste.manifest'
    _description = 'Hazardous Waste Manifest'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Reference', required=True, readonly=True, copy=False, default=lambda self: _('New'))
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    waste_description = fields.Char('Waste Description', required=True, tracking=True)
    quantity_kg = fields.Float('Quantity (kg)', digits='Product Unit of Measure', tracking=True)
    transporter_id = fields.Many2one('res.partner', string='Transporter', tracking=True)
    receiver_id = fields.Many2one('res.partner', string='Receiver (TSDF)', tracking=True)
    manifest_no = fields.Char('Manifest No.', tracking=True, help="Number on the statutory manifest form.")
    attachment_ids = fields.Many2many('ir.attachment', string='Documents')
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('dispatched', 'Dispatched'),
        ('acknowledged', 'Acknowledged'),
    ], default='draft', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ug.waste.manifest') or _('New')
        return super().create(vals_list)

    def action_dispatch(self):
        self.write({'state': 'dispatched'})

    def action_acknowledge(self):
        self.write({'state': 'acknowledged'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
