from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

MAX_TOTAL_PCT = 100.5  # small tolerance for lab rounding


class UgLotAssay(models.Model):
    _name = 'ug.lot.assay'
    _description = 'Lot Assay'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sample_date desc, id desc'

    name = fields.Char('Reference', required=True, readonly=True, copy=False, default=lambda self: _('New'))
    lot_id = fields.Many2one('stock.lot', string='Lot', required=True, index=True, tracking=True,
        check_company=True, readonly=False)
    product_id = fields.Many2one(related='lot_id.product_id', store=True, index=True)
    battery_chemistry_id = fields.Many2one(related='lot_id.battery_chemistry_id', store=True, index=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
        default=lambda self: self.env.company)

    sample_date = fields.Date(default=fields.Date.context_today, tracking=True)
    sample_ref = fields.Char('Sample Reference')
    lab_type = fields.Selection([('in_house', 'In-house'), ('external', 'External')],
        string='Laboratory', required=True, default='in_house', tracking=True)
    lab_partner_id = fields.Many2one('res.partner', string='External Lab', tracking=True)
    certificate_attachment_ids = fields.Many2many('ir.attachment', string='Lab Certificates')
    basis_weight_kg = fields.Float('Basis Weight (kg)', digits='Product Unit of Measure',
        help="Lot quantity in kg when the assay was taken; contained kg on the lines are computed from it.")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, index=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    is_current = fields.Boolean('Current', readonly=True, copy=False, index=True,
        help="Approved assay currently used for this lot (only one per lot).")

    production_id = fields.Many2one('mrp.production', string='Source MO', compute='_compute_production_id',
        store=True, index=True, readonly=True, help="Manufacturing order that produced the assayed lot.")
    production_ids = fields.Many2many('mrp.production', compute='_compute_production_ids',
        string='Manufacturing Orders', help="Orders that produced or consume the assayed lot.")
    production_count = fields.Integer(compute='_compute_production_ids', string='MO Count')

    line_ids = fields.One2many('ug.lot.assay.line', 'assay_id', string='Results', copy=True)
    total_pct = fields.Float('Total (%)', compute='_compute_totals', digits=(6, 4))
    others_pct = fields.Float('Others (%)', compute='_compute_totals', digits=(6, 4),
        help="100 - sum of measured elements.")
    note = fields.Html()

    @api.depends('lot_id')
    def _compute_production_id(self):
        Production = self.env['mrp.production']
        for assay in self:
            producers = Production._ug_producers_of(assay.lot_id._origin) if assay.lot_id._origin else Production
            assay.production_id = producers.sorted('id')[:1]

    @api.depends('lot_id')
    def _compute_production_ids(self):
        Production = self.env['mrp.production']
        for assay in self:
            lot = assay.lot_id._origin
            productions = (Production._ug_producers_of(lot) | Production._ug_consumers_of(lot)) if lot else Production
            assay.production_ids = productions.sorted('id')
            assay.production_count = len(productions)

    def action_view_productions(self):
        self.ensure_one()
        if len(self.production_ids) == 1:
            return {'type': 'ir.actions.act_window', 'res_model': 'mrp.production',
                    'res_id': self.production_ids.id, 'views': [(False, 'form')]}
        return {
            'type': 'ir.actions.act_window',
            'name': _("Manufacturing Orders – %s", self.lot_id.name),
            'res_model': 'mrp.production',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', self.production_ids.ids)],
            'context': {'create': False},
        }

    @api.depends('line_ids.percentage')
    def _compute_totals(self):
        for assay in self:
            total = sum(assay.line_ids.mapped('percentage'))
            assay.total_pct = total
            assay.others_pct = 100.0 - total

    @api.constrains('line_ids')
    def _check_total_percentage(self):
        for assay in self:
            if sum(assay.line_ids.mapped('percentage')) > MAX_TOTAL_PCT:
                raise ValidationError(_(
                    "The element percentages of assay %(assay)s add up to %(total).4f%%, more than %(max)s%%.",
                    assay=assay.name, total=sum(assay.line_ids.mapped('percentage')), max=MAX_TOTAL_PCT))
            elements = assay.line_ids.element_id
            if len(elements) != len(assay.line_ids):
                raise ValidationError(_("An element can only appear once on assay %s.", assay.name))

    @api.constrains('lab_type', 'lab_partner_id')
    def _check_lab_partner(self):
        for assay in self:
            if assay.lab_type == 'external' and not assay.lab_partner_id:
                raise ValidationError(_("Select the external laboratory for assay %s.", assay.name))

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id and not self.basis_weight_kg:
            self.basis_weight_kg = self.lot_id._ug_qty_kg()
        if self.lot_id and not self.line_ids:
            self.line_ids = self._ug_template_line_commands(self.lot_id.product_id)

    @api.model
    def _ug_template_line_commands(self, product):
        template = product.ug_assay_template_id
        return [Command.create({'element_id': element.id, 'percentage': 0.0})
                for element in template.element_ids.sorted(lambda e: (e.sequence, e.id))]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('ug.lot.assay') or _('New')
            lot = vals.get('lot_id') and self.env['stock.lot'].browse(vals['lot_id'])
            if lot:
                if 'basis_weight_kg' not in vals:
                    vals['basis_weight_kg'] = lot._ug_qty_kg()
                if 'line_ids' not in vals:
                    vals['line_ids'] = self._ug_template_line_commands(lot.product_id)
                if 'company_id' not in vals and lot.company_id:
                    vals['company_id'] = lot.company_id.id
        return super().create(vals_list)

    def write(self, vals):
        locked = {'lot_id', 'line_ids', 'basis_weight_kg', 'lab_type', 'lab_partner_id', 'sample_date'}
        if locked & set(vals) and any(a.state == 'approved' for a in self):
            raise UserError(_("Approved assays cannot be modified. Create a new assay instead."))
        return super().write(vals)

    def unlink(self):
        if any(a.state == 'approved' for a in self):
            raise UserError(_("Approved assays cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _ug_check_group(self, xmlid, action):
        if not self.env.su and not self.env.user.has_group(xmlid):
            group = self.env.ref(xmlid)
            raise UserError(_("Only members of '%(group)s' can %(action)s an assay.", group=group.name, action=action))

    def action_submit(self):
        self._ug_check_group('ug_recycling_base.group_ug_lab', _('submit'))
        for assay in self:
            if assay.state != 'draft':
                raise UserError(_("Only draft assays can be submitted."))
            if not assay.line_ids:
                raise UserError(_("Add at least one element result to assay %s.", assay.name))
            assay._ug_check_has_results()
        self.write({'state': 'submitted'})

    def _ug_check_has_results(self):
        for assay in self:
            if not any(assay.line_ids.mapped('percentage')):
                raise UserError(_(
                    "All results of assay %s are 0 %%. Enter the element percentages from the lab report first.",
                    assay.name))

    def action_approve(self):
        self._ug_check_group('ug_recycling_base.group_ug_manager', _('approve'))
        for assay in self:
            if assay.state != 'submitted':
                raise UserError(_("Only submitted assays can be approved."))
            assay._ug_check_has_results()
            if assay.lab_type == 'external' and not assay.certificate_attachment_ids:
                raise UserError(_("Attach the external lab certificate before approving %s.", assay.name))
            previous = self.search([('lot_id', '=', assay.lot_id.id), ('is_current', '=', True), ('id', '!=', assay.id)])
            previous.is_current = False
            assay.write({
                'state': 'approved',
                'is_current': True,
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            body = _("Assay %(new)s approved and set as current composition.", new=assay._get_html_link())
            if previous:
                body = Markup("%s<br/>%s") % (body, _("Replaces assay %s.", ", ".join(previous.mapped('name'))))
            assay.lot_id.message_post(body=body)
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_reject(self):
        self._ug_check_group('ug_recycling_base.group_ug_manager', _('reject'))
        if any(assay.state != 'submitted' for assay in self):
            raise UserError(_("Only submitted assays can be rejected."))
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self._ug_check_group('ug_recycling_base.group_ug_lab', _('reset'))
        if any(assay.state not in ('submitted', 'rejected') for assay in self):
            raise UserError(_("Only submitted or rejected assays can be reset to draft."))
        self.write({'state': 'draft'})

    @api.model
    def _ug_create_from_production(self, lots):
        """ Draft assays for freshly produced lots + activity for the lab. """
        lab_users = self.env['res.users'].search([('groups_id', 'in', self.env.ref('ug_recycling_base.group_ug_lab').ids)]).filtered(
            lambda u: not u.share and u.active)
        assays = self.browse()
        for lot in lots:
            if not lot.product_id.ug_requires_assay:
                continue
            if self.search_count([('lot_id', '=', lot.id), ('state', 'in', ('draft', 'submitted'))]):
                continue
            assay = self.create({'lot_id': lot.id, 'company_id': (lot.company_id or self.env.company).id})
            for user in lab_users.filtered(lambda u: assay.company_id in u.company_ids):
                assay.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_("Assay lot %s", lot.name),
                    user_id=user.id,
                )
            assays |= assay
        return assays


class UgLotAssayLine(models.Model):
    _name = 'ug.lot.assay.line'
    _description = 'Lot Assay Result'
    _order = 'sequence, id'

    assay_id = fields.Many2one('ug.lot.assay', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='assay_id.company_id', store=True, index=True)
    lot_id = fields.Many2one(related='assay_id.lot_id', store=True, index=True)
    element_id = fields.Many2one('ug.assay.element', required=True, index=True)
    sequence = fields.Integer(related='element_id.sequence', store=True)
    percentage = fields.Float('Result (%)', digits=(6, 4),
        help="Mass percentage of the element in the sample, as reported by the lab.")
    contained_kg_basis = fields.Float('kg in Lot (at Sampling)', compute='_compute_contained_kg_basis',
        store=True, digits='Product Unit of Measure')
    contained_kg_current = fields.Float('kg in Lot (Now)', compute='_compute_contained_kg_current',
        digits='Product Unit of Measure')

    @api.depends('percentage', 'assay_id.basis_weight_kg')
    def _compute_contained_kg_basis(self):
        for line in self:
            line.contained_kg_basis = line.assay_id.basis_weight_kg * line.percentage / 100.0

    @api.depends('percentage', 'assay_id.lot_id')
    def _compute_contained_kg_current(self):
        for line in self:
            line.contained_kg_current = line.assay_id.lot_id._ug_qty_kg() * line.percentage / 100.0

    @api.constrains('percentage')
    def _check_percentage(self):
        for line in self:
            if not 0.0 <= line.percentage <= 100.0:
                raise ValidationError(_("Element percentages must be between 0 and 100 (%s).",
                                        line.element_id.display_name))

    @api.constrains('element_id', 'percentage')
    def _check_assay_totals(self):
        self.assay_id._check_total_percentage()
