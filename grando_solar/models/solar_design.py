from odoo import models, fields, api

class SolarDesign(models.Model):
    _name = 'solar.design'
    _description = 'Solar Design'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        default='New',
        copy=False
    )

    survey_id = fields.Many2one(
        'solar.site.survey',
        required=True
    )

    lead_id = fields.Many2one(
        related='survey_id.lead_id',
        store=True
    )

    designer_id = fields.Many2one(
        'res.users'
    )

    layout_plan = fields.Binary()

    layout_filename = fields.Char()

    bom_file = fields.Binary()

    bom_filename = fields.Char()

    state = fields.Selection([
        ('draft','Draft'),
        ('review','Review'),
        ('approved','Approved'),
        ('rejected','Rejected')
    ], default='draft')

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Quotation'
    )

    quotation_count = fields.Integer(
        compute='_compute_quotation_count'
    )


    @api.model
    def create(self, vals):

        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env[
                'ir.sequence'
            ].next_by_code(
                'solar.design'
            )

        return super().create(vals)

    def action_submit(self):
        self.write({'state': 'review'})


    def action_approve(self):
        self.write({'state': 'approved'})


    def action_reject(self):
        self.write({'state': 'rejected'})

    def _compute_quotation_count(self):
        for rec in self:
            rec.quotation_count = 1 if rec.sale_order_id else 0
    def action_create_quotation(self):
        """
        Create quotation from approved design
        """

        self.ensure_one()

        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        partner = self.lead_id.partner_id

        if not partner:
            partner = self.env['res.partner'].create({
                'name': self.lead_id.partner_name or self.lead_id.name,
                'email': self.lead_id.email_from,
                'phone': self.lead_id.phone,
            })

            self.lead_id.partner_id = partner.id

        quotation = self.env['sale.order'].create({
            'partner_id': partner.id,
            'origin': self.name,
            'warranty_type': 'performance_warranty',
            'delivery_type': 'as_per_discussion',
            'freight_type': 'included',
            'payment_type': 'advance_100',
            'cancellation_policy': 'custom',
            'certifications_type': 'iec_almm_bis',
            'tolerance_type': 'positive',
        })

        self.sale_order_id = quotation.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': quotation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_quotation(self):

        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }



    
