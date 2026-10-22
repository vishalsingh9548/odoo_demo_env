import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class MaterialRequestApproverMaster(models.Model):
    """Who must approve a requisition: one master per type and company, with up to five approval levels."""
    _name = 'material.request.approver.master'
    _description = 'Material Request Approver Master'
    _rec_name = 'material_type'

    material_type = fields.Selection([('admin_manager', 'Admin Manager Approval'),
                                      ('standard_multi_level', 'Standard Multi-Level Approval')],
                                     required=True, string='Material Type')
    approvals_type = fields.Selection([('single', 'Single')], default='single')
    no_of_approvals = fields.Integer(string='Number of Approvals', default=1)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    approver_line_ids = fields.One2many('material.request.approver.line', 'approver_master_id', string='Approver Levels')

    _sql_constraints = [
        ('type_company_uniq', 'unique(material_type, company_id)', 'The Material Type must be unique per company!'),
    ]

    @api.constrains('no_of_approvals')
    def _check_no_of_approvals(self):
        """Between 1 and 5 approval levels."""
        for rec in self:
            if rec.no_of_approvals <= 0:
                raise ValidationError(_('Number of Approvals must be greater than zero.'))
            if rec.no_of_approvals > 5:
                raise ValidationError(_('The system accommodates up to five levels of approvers.'))

    @api.depends('material_type')
    def _compute_display_name(self):
        """Show the type's label."""
        labels = dict(self._fields['material_type'].selection)
        for rec in self:
            rec.display_name = labels.get(rec.material_type, '')


class MaterialRequestApproverLine(models.Model):
    """One approval level: one or more users who can approve at that level."""
    _name = 'material.request.approver.line'
    _description = 'Material Request Approver Line'
    _order = 'sequence, id'

    approver_master_id = fields.Many2one('material.request.approver.master', ondelete='cascade')
    sequence = fields.Integer(default=1)
    approver_level = fields.Char(compute='_compute_level', store=True)
    approver_id = fields.Many2many('res.users', string='Approvers')

    @api.depends('sequence')
    def _compute_level(self):
        """Label like 'Approver 1'."""
        for rec in self:
            rec.approver_level = _('Approver %s', rec.sequence)

    @api.constrains('sequence')
    def _check_sequence(self):
        """Levels start at 1."""
        for rec in self:
            if rec.sequence <= 0:
                raise ValidationError(_('Approver sequence must be greater than zero.'))


class MaterialRequisition(models.Model):
    """A request to the store for materials, approved level by level, then turned into an internal transfer."""
    _name = 'material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Indent Reference', required=True, readonly=True, copy=False, default='New')
    state = fields.Selection([('draft', 'Draft'), ('waiting_for_approval', 'Waiting for Approval'),
                              ('second_approval', 'Second Approval'), ('approved', 'Approved'),
                              ('received', 'Received'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')],
                             default='draft', tracking=True)
    state_label = fields.Char(compute='_compute_state_label', store=True)
    request_raised_by = fields.Many2one('hr.employee', string='Request Raised By', required=True,
                                        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1))
    department_id = fields.Many2one('hr.department', related='request_raised_by.department_id', store=True)
    job_position_id = fields.Many2one('hr.job', related='request_raised_by.job_id', store=True)
    reporting_manager_id = fields.Many2one('hr.employee', related='request_raised_by.parent_id', store=True)
    request_raised_for = fields.Many2one('hr.employee', string='Request Raised For')
    raised_for_department_id = fields.Many2one('hr.department', related='request_raised_for.department_id', store=True, string='Department (For)')
    raised_for_job_id = fields.Many2one('hr.job', related='request_raised_for.job_id', store=True, string='Job Position (For)')
    raised_for_manager_id = fields.Many2one('hr.employee', related='request_raised_for.parent_id', store=True, string='Reporting Manager (For)')
    purpose = fields.Char(required=True)
    source_location_id = fields.Many2one('stock.location', string='Source Location')
    destination_location_id = fields.Many2one('stock.location', string='Destination Location', required=True,
                                              domain="[('usage', '=', 'internal')]",
                                              help='Internal location where the requested items should be delivered (e.g., Floor 1).')
    indented_date = fields.Datetime(string='Indent Date', readonly=True, default=fields.Datetime.now)
    required_date = fields.Datetime(required=True)
    verified_date = fields.Datetime(readonly=True, copy=False)
    requirement = fields.Selection([('urgent', 'Urgent'), ('normal', 'Normal')], default='normal', string='Requirement Type')
    material_requisition_line_ids = fields.One2many('material.requisition.line', 'requisition_id', copy=True)
    signature = fields.Binary(string='Signature of the requestor')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    approval_type_id = fields.Many2one('material.request.approver.master', string='Approval Type', ondelete='restrict', required=True)
    no_of_approvals = fields.Integer(related='approval_type_id.no_of_approvals', store=True)
    approver_ids = fields.Many2many('res.users', 'mr_approver_rel', 'mr_id', 'user_id', compute='_compute_approvers', store=True, string='All Approvers')
    approver_1_id = fields.Many2many('res.users', 'mr_approver1_rel', 'mr_id', 'user_id', compute='_compute_approvers',
                                     store=True, string='Approver')
    approver_2_id = fields.Many2many('res.users', 'mr_approver2_rel', 'mr_id', 'user_id', compute='_compute_approvers', store=True)
    current_approver_level = fields.Integer(default=0)
    current_approver_user_id = fields.Many2one('res.users', compute='_compute_current_approver', store=True)
    approved_by_ids = fields.Many2many('res.users', 'mr_approved_by_rel', 'mr_id', 'user_id', readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True, copy=False)
    picking_state = fields.Selection(related='picking_id.state', store=True)
    transfer_count = fields.Integer(compute='_compute_counts')
    purchase_order_count = fields.Integer(compute='_compute_counts')
    product_tmpl_id = fields.Many2one('product.template', string='Product', tracking=True, domain="[('is_finished_good', '=', True)]")
    ribbon_status = fields.Selection([('approved', 'Approved'), ('in_progress', 'In Progress'),
                                      ('transfer_done', 'Transfer Done'), ('to_verify', 'To Verify')],
                                     compute='_compute_ribbon', store=True)
    is_manager_admin = fields.Boolean(compute='_compute_is_manager_admin')
    is_current_user_authorized = fields.Boolean(compute='_compute_authorized')
    is_purchase_order_creation_blocked_for_user = fields.Boolean(compute='_compute_authorized')
    has_unavailable_products = fields.Boolean(compute='_compute_has_unavailable')
    rejected_by = fields.Many2one('hr.employee', compute='_compute_rejected_by')
    mrp_production_id = fields.Many2one('mrp.production', string='Manufacturing Order', readonly=True, copy=False)
    mrp_production_count = fields.Integer(compute='_compute_mrp_production_count')

    # ------------------------------------------------------------------ computes
    @api.depends('state')
    def _compute_state_label(self):
        """Readable label of the status."""
        labels = dict(self._fields['state'].selection)
        for rec in self:
            rec.state_label = labels.get(rec.state, '')

    @api.depends('approval_type_id.approver_line_ids.approver_id')
    def _compute_approvers(self):
        """Flatten the approvers of every level (and of level 1 and 2 on their own)."""
        for rec in self:
            lines = rec.approval_type_id.approver_line_ids.sorted('sequence')
            rec.approver_ids = lines.approver_id
            rec.approver_1_id = lines[:1].approver_id
            rec.approver_2_id = lines[1:2].approver_id

    @api.depends('approver_ids', 'current_approver_level')
    def _compute_current_approver(self):
        """The person whose turn it is."""
        for rec in self:
            ordered = rec.approver_ids
            rec.current_approver_user_id = ordered[rec.current_approver_level] if len(ordered) > rec.current_approver_level else False

    def _compute_counts(self):
        """Counts shown on the smart buttons."""
        for rec in self:
            rec.transfer_count = 1 if rec.picking_id else 0
            rec.purchase_order_count = self.env['purchase.order'].search_count(
                [('material_requisition_id', '=', rec.id)]) or self.env['purchase.order'].search_count(
                [('origin', 'like', rec.name)])

    @api.depends('state', 'picking_state')
    def _compute_ribbon(self):
        """Ribbon text from the status and the transfer status."""
        for rec in self:
            if rec.state == 'approved':
                rec.ribbon_status = 'transfer_done' if rec.picking_state == 'done' else 'in_progress' if rec.picking_id else 'approved'
            elif rec.state == 'received':
                rec.ribbon_status = 'to_verify'
            else:
                rec.ribbon_status = False

    def _manager_is_admin(self, employee):
        """True when the employee's manager chain reaches a system administrator."""
        manager = employee.parent_id
        if not manager:
            return False
        if manager.parent_id:
            return bool(manager.parent_id.user_id and manager.parent_id.user_id.has_group('base.group_system'))
        return bool(manager.user_id and manager.user_id.has_group('base.group_system'))

    @api.depends('request_raised_by')
    def _compute_is_manager_admin(self):
        """Is an administrator in the requester's manager chain?"""
        for rec in self:
            rec.is_manager_admin = self._manager_is_admin(rec.request_raised_by)

    @api.depends_context('uid')
    def _compute_authorized(self):
        """May the current user act as the requester's manager? Is PO creation blocked for them?"""
        user = self.env.user
        for rec in self:
            mgr = rec.reporting_manager_id.user_id
            rec.is_current_user_authorized = user.has_group('base.group_system') or (bool(mgr) and mgr == user)
            rec.is_purchase_order_creation_blocked_for_user = user.block_create_purchase_order

    @api.depends('material_requisition_line_ids.is_stock_available')
    def _compute_has_unavailable(self):
        """True when any line cannot be fully covered from the source location."""
        for rec in self:
            rec.has_unavailable_products = any(not l.is_stock_available for l in rec.material_requisition_line_ids)

    @api.depends_context('uid')
    def _compute_rejected_by(self):
        """Who rejected it: the current user's employee when the state is Rejected."""
        emp = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        for rec in self:
            rec.rejected_by = emp if rec.state == 'rejected' else False

    def _compute_mrp_production_count(self):
        """1 when linked to a manufacturing order."""
        for rec in self:
            rec.mrp_production_count = 1 if rec.mrp_production_id else 0

    @api.constrains('required_date', 'indented_date')
    def _check_dates(self):
        """The required date cannot be before the indent date."""
        for rec in self:
            if rec.required_date and rec.indented_date and rec.required_date < rec.indented_date:
                raise ValidationError(_('Required Date cannot be earlier than Indent Date.'))

    # ------------------------------------------------------------------ create / copy rules
    @api.model_create_multi
    def create(self, vals_list):
        """Number each requisition (MR/year/00001); only Manufacturing Users may create them."""
        self._check_creator_role()
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('material.requisition.sequence') or 'New'
        return super().create(vals_list)

    def copy(self, default=None):
        """Duplicating follows the same role rule."""
        self._check_creator_role()
        return super().copy(default)

    def _check_creator_role(self):
        """Only Manufacturing Users and Administrators may create requisitions."""
        user = self.env.user
        if self.env.su:
            return
        if not (user.has_group('mrp.group_mrp_user') or user.has_group('base.group_system')):
            raise AccessError(_('Only Manufacturing Users and Administrators can create Material Requisitions.'))

    # ------------------------------------------------------------------ approval type
    def _role_master(self, employee):
        """The approver master that fits the requester: admin-manager chain or standard multi-level."""
        kind = 'admin_manager' if self._manager_is_admin(employee) else 'standard_multi_level'
        return self.env['material.request.approver.master'].search([
            ('material_type', '=', kind), ('company_id', '=', self.company_id.id or self.env.company.id)], limit=1)

    def _get_notification_approval_master(self):
        """Approval master by the requester's own role (MRP manager -> admin type, MRP user -> multi-level)."""
        self.ensure_one()
        user = self.request_raised_by.user_id or self.create_uid or self.env.user
        user_type = user.mr_approval_type_id
        if user_type and user_type.company_id == self.company_id:
            return user_type
        kind = False
        if user.has_group('mrp.group_mrp_manager'):
            kind = 'admin_manager'
        elif user.has_group('mrp.group_mrp_user'):
            kind = 'standard_multi_level'
        master = kind and self.env['material.request.approver.master'].search(
            [('material_type', '=', kind), ('company_id', '=', self.company_id.id)], limit=1)
        return master or self.approval_type_id

    def _sync_approval_type_with_requester_role(self):
        """Request Approval first aligns the approval type with the requester's role."""
        for rec in self:
            master = rec._get_notification_approval_master()
            if master and master != rec.approval_type_id:
                rec.approval_type_id = master

    @api.onchange('request_raised_by')
    def _onchange_request_raised_by(self):
        """Pick the approval type for the chosen requester (user's own type first, else by manager chain)."""
        if self.state != 'draft':
            return
        self.approval_type_id = False
        user = self.request_raised_by.user_id
        if user and user.mr_approval_type_id:
            if user.mr_approval_type_id.company_id != self.company_id:
                raise UserError(_('Selected user approval type belongs to another company. '
                                  'Please choose an approval type for this company.'))
            self.approval_type_id = user.mr_approval_type_id
            return
        master = self._role_master(self.request_raised_by) if self.request_raised_by else False
        if self.request_raised_by and not master:
            raise UserError(_("Configuration Error: No 'Material Request Approver Master' found for this setup. "
                              "Please configure one."))
        self.approval_type_id = master

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        """Picking a finished product fills the lines with the components of its first BOM."""
        if not self.product_tmpl_id:
            return
        bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_tmpl_id.id)], limit=1)
        lines = [(5, 0, 0)]
        if bom:
            lines += [(0, 0, {'product_id': l.product_id.id, 'product_uom_qty': 1}) for l in bom.bom_line_ids]
        self.material_requisition_line_ids = lines

    # ------------------------------------------------------------------ buttons
    def _approval_link(self):
        """Link to this requisition inside the app."""
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return '%s/web#id=%s&model=material.requisition&view_type=form' % (base, self.id)

    def _stage_name(self):
        """Name of the approval stage now in force."""
        return {1: _('Waiting for Approval'), 2: _('Second Approval')}.get(self.current_approver_level + 1 if self.state != 'waiting_for_approval' else 1, _('Approval'))

    def _notify_current_approver(self):
        """Tell the person whose turn it is: a note on the requisition plus a To-Do for them."""
        self.ensure_one()
        approver = self.current_approver_user_id
        if not approver:
            return
        self.message_post(
            body=_("Approval moved to %(approver)s at stage '%(stage)s'.", approver=approver.name, stage=self._stage_name()),
            partner_ids=approver.partner_id.ids, message_type='comment', subtype_xmlid='mail.mt_note')
        title = _('Approve Material Requisition %s', self.name)
        if not self.activity_ids.filtered(lambda a: a.user_id == approver and a.summary == title):
            self.activity_schedule('mail.mail_activity_data_todo', user_id=approver.id, summary=title,
                                   date_deadline=fields.Date.context_today(self))

    def _complete_my_todos(self):
        """The current user's open approval To-Dos on this requisition are marked done."""
        for act in self.activity_ids.filtered(lambda a: a.user_id == self.env.user):
            act.action_feedback(feedback=_('Approval action completed.'))

    def _refresh_stock_figures(self):
        """Recalculate the stock numbers on open requisitions (they are saved figures, so they go stale otherwise)."""
        lines = self.filtered(lambda r: r.state in ('draft', 'waiting_for_approval', 'second_approval')).material_requisition_line_ids
        if lines:
            lines.invalidate_recordset(['onhand_quantity', 'is_stock_available', 'qty_to_purchase', 'qty_to_transfer'])
            for name in ('onhand_quantity', 'is_stock_available', 'qty_to_purchase', 'qty_to_transfer'):
                self.env.add_to_compute(lines._fields[name], lines)
            lines.mapped('onhand_quantity')  # touching one field runs the recalculation of all four

    def web_read(self, specification):
        """Opening a requisition shows up-to-date stock figures."""
        self._refresh_stock_figures()
        return super().web_read(specification)

    def action_request_approval(self):
        """Request Approval: validate, align the approval type with the requester's role, start the chain."""
        for rec in self:
            if not rec.material_requisition_line_ids:
                raise UserError(_('Please add at least one product to the requisition before requesting approval.'))
            if any(l.product_uom_qty <= 0 for l in rec.material_requisition_line_ids):
                raise UserError(_('Requested quantity for any product cannot be zero or negative.'))
            rec._sync_approval_type_with_requester_role()
            if not rec.approval_type_id:
                raise UserError(_('Please select an Approval Type before requesting approval.'))
            if not rec.approver_ids:
                raise UserError(_('No approvers are configured for the selected Approval Type.'))
            rec.write({'state': 'waiting_for_approval', 'current_approver_level': 0, 'approved_by_ids': [(5, 0, 0)]})
            rec._notify_current_approver()
        return True

    def action_create_purchase_order(self):
        """Create Purchase Order: buy the short lines from the first vendor of the first product."""
        self.ensure_one()
        if self.env.user.block_create_purchase_order:
            raise UserError(_('You do not have permission to create purchase orders from material requisitions.'))
        lines = self.material_requisition_line_ids.filtered(lambda l: l.qty_to_purchase > 0 and l.product_id.purchase_ok)
        if not lines:
            raise UserError(_('No products with insufficient stock were found or the products are not set up for purchase.'))
        seller = lines[0].product_id.seller_ids[:1]
        if not seller:
            raise UserError(_('No vendor found for product %s.', lines[0].product_id.display_name))
        po = self.env['purchase.order'].create({
            'partner_id': seller.partner_id.id, 'origin': self.name, 'company_id': self.company_id.id,
            'material_requisition_id': self.id,
            'order_line': [(0, 0, {'product_id': l.product_id.id, 'product_qty': l.qty_to_purchase,
                                   'product_uom': l.product_id.uom_po_id.id, 'name': l.product_id.display_name,
                                   'date_planned': self.required_date or fields.Datetime.now()}) for l in lines]})
        return {'type': 'ir.actions.act_window', 'res_model': 'purchase.order', 'res_id': po.id, 'view_mode': 'form'}

    def action_recommend_and_forward(self):
        """Recommend & Forward: needs stock or a purchase order first; moves to Second Approval (or opens the lot picker)."""
        self.ensure_one()
        self._refresh_stock_figures()
        if self.has_unavailable_products and not self.env['purchase.order'].search_count([('origin', 'like', self.name)]):
            raise UserError(_('You have products with insufficient stock. Please create a purchase order first '
                              'or adjust the quantities.'))
        if self.mrp_production_id and not self.env.context.get('skip_lot_selection_wizard'):
            tracked = self.material_requisition_line_ids.filtered(lambda l: l.qty_to_transfer > 0 and l.product_id.tracking != 'none')
            if tracked:
                wiz = self.env['material.requisition.lot.wizard'].create({
                    'requisition_id': self.id,
                    'line_ids': [(0, 0, {'requisition_line_id': l.id}) for l in tracked]})
                return {'type': 'ir.actions.act_window', 'name': _('Select Lots to Use'),
                        'res_model': 'material.requisition.lot.wizard', 'res_id': wiz.id, 'view_mode': 'form', 'target': 'new'}
        self._complete_my_todos()
        self.write({'state': 'second_approval', 'current_approver_level': 1})
        self._notify_current_approver()
        return True

    def action_approve_level(self):
        """Approve: next level, or (last level) approved with an internal transfer."""
        self.ensure_one()
        self._complete_my_todos()
        self.approved_by_ids = [(4, self.env.user.id)]
        if self.current_approver_level + 1 < self.no_of_approvals:
            self.current_approver_level += 1
            self._notify_current_approver()
        else:
            self.write({'state': 'approved', 'current_approver_level': self.no_of_approvals,
                        'verified_date': fields.Datetime.now()})
            self._create_internal_transfer()
        return True

    def action_received(self):
        """Received: validate the transfer; fully done means the requisition is received."""
        self.ensure_one()
        if self.state not in ('approved',):
            raise UserError(_("Material Requisition must be in 'Approved' or 'In Progress' state to be received."))
        if not self.picking_id:
            raise UserError(_('No internal transfer has been generated for this material requisition.'))
        picking = self.picking_id
        if picking.state not in ('done', 'cancel'):
            try:
                res = picking.button_validate()
                if isinstance(res, dict) and res.get('res_model') == 'stock.immediate.transfer':
                    self.env['stock.immediate.transfer'].with_context(**res.get('context', {})).browse(res['res_id']).process()
            except ValidationError as err:  # the transfer stays open; the user can finish it by hand
                _logger.warning('Requisition %s: transfer not validated: %s', self.name, err)
        if picking.state == 'done':
            self.state = 'received'
            self.message_post(body=_('Material received. Internal transfer %s is done.', picking.name))
            if self.mrp_production_id:
                self._refresh_mo_after_receipt()
        return True

    def _cancel_open_picking(self):
        """Cancel the linked transfer if it is still open."""
        for rec in self:
            if rec.picking_id and rec.picking_id.state not in ('done', 'cancel'):
                rec.picking_id.action_cancel()

    def action_reject(self):
        """Reject: the requisition is closed and its open transfer cancelled."""
        self._cancel_open_picking()
        self.write({'state': 'rejected'})
        return True

    def action_cancel(self):
        """Cancel: same as reject but labelled Cancelled."""
        self._cancel_open_picking()
        self.write({'state': 'cancelled'})
        return True

    def action_set_to_draft(self):
        """Set to Draft: start over."""
        self.write({'state': 'draft', 'current_approver_level': 0, 'approved_by_ids': [(5, 0, 0)],
                    'verified_date': False, 'picking_id': False})
        return True

    # ------------------------------------------------------------------ transfer
    def _source_location(self):
        """Where the stock comes from: the chosen source, else the company's main stock location."""
        self.ensure_one()
        if self.source_location_id:
            return self.source_location_id
        wh = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        if not wh:
            raise UserError(_("Main Stock location 'WH/Stock' not found. Please configure a warehouse."))
        return wh.lot_stock_id

    def _create_internal_transfer(self):
        """On final approval: create and confirm the internal transfer (MO-linked requisitions only move what the store has)."""
        self.ensure_one()
        lines = self.material_requisition_line_ids
        if not lines:
            raise UserError(_('Cannot create transfer for a requisition with no products.'))
        if self.mrp_production_id:
            lines = lines.filtered(lambda l: l.qty_to_transfer > 0)
            if not lines:
                self.message_post(body=_('No internal transfer was created because the requested quantities are '
                                         'already available at the destination.'))
                self.state = 'received'
                self._refresh_mo_after_receipt()
                return False
        src = self._source_location()
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company_id.id)], limit=1)
        picking_type = warehouse.int_type_id
        if not picking_type:
            raise UserError(_('No internal transfer type found for this company.'))
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id, 'location_id': src.id, 'location_dest_id': self.destination_location_id.id,
            'origin': self.name, 'company_id': self.company_id.id,
            'move_ids': [(0, 0, {
                'name': l.product_id.display_name, 'product_id': l.product_id.id,
                'product_uom_qty': l.qty_to_transfer if self.mrp_production_id else l.product_uom_qty,
                'product_uom': l.product_uom.id, 'location_id': src.id,
                'location_dest_id': self.destination_location_id.id, 'company_id': self.company_id.id,
            }) for l in lines]})
        picking.action_confirm()
        picking.action_assign()
        if self.mrp_production_id:
            self._reserve_selected_lots(picking)
        self.picking_id = picking
        return picking

    def _reserve_selected_lots(self, picking):
        """Replace the automatic reservation with the lots the user picked (strictly those lots)."""
        for move in picking.move_ids:
            line = self.material_requisition_line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]
            if not line.selected_lot_ids:
                continue
            move._do_unreserve()
            remaining = move.product_uom_qty
            for lot in line.selected_lot_ids:
                if float_compare(remaining, 0, precision_rounding=move.product_uom.rounding) <= 0:
                    break
                got = move._update_reserved_quantity(remaining, move.location_id, lot_id=lot, strict=True)
                remaining -= got
            if float_compare(remaining, 0, precision_rounding=move.product_uom.rounding) > 0:
                raise UserError(_(
                    "The lot(s) selected for '%(p)s' (%(l)s) no longer have enough free stock to cover the required "
                    "quantity (%(q)s %(u)s short). Please open the requisition again, forward it, and choose "
                    "additional or different lot(s).", p=move.product_id.display_name,
                    l=', '.join(line.selected_lot_ids.mapped('name')), q=remaining, u=move.product_uom.name))
            move.state = 'assigned' if move.move_line_ids else move.state

    # ------------------------------------------------------------------ after receipt: make the MO see the stock
    def _refresh_mo_after_receipt(self):
        """Re-reserve the order's components and give lot-less lines the delivered lots."""
        mo = self.mrp_production_id
        if mo.state not in ('confirmed', 'progress', 'to_close'):
            return
        raw = mo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
        if not raw:
            return
        raw._do_unreserve()
        mo.action_assign()
        self._bind_phantom_lots(raw)
        self.env.invalidate_all()

    def _bind_phantom_lots(self, moves):
        """Tracked components reserved without a lot get a lot: the requisition's lots first, then oldest stock."""
        for move in moves.filtered(lambda m: m.product_id.tracking != 'none'):
            line = self.material_requisition_line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]
            for ml in move.move_line_ids.filtered(lambda x: not x.lot_id and not x.lot_name):
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id), ('location_id', '=', ml.location_id.id),
                    ('lot_id', '!=', False), ('quantity', '>', 0)], order='in_date asc')
                quants = quants.sorted(key=lambda q: (q.lot_id not in line.selected_lot_ids, q.in_date))
                need = ml.quantity
                first = True
                for q in quants:
                    free = q.quantity - q.reserved_quantity
                    if free <= 0 or need <= 0:
                        continue
                    take = min(free, need)
                    if first:
                        if take >= ml.quantity:
                            ml.lot_id = q.lot_id
                        else:
                            leftover = ml.quantity - take
                            ml.quantity = take
                            ml.lot_id = q.lot_id
                            ml.copy({'quantity': leftover, 'lot_id': False})
                        first = False
                    else:
                        ml.copy({'quantity': take, 'lot_id': q.lot_id.id})
                    need -= take
                if need > 0:
                    _logger.warning('Requisition %s: could not bind lots for %s', self.name, move.product_id.display_name)

    # ------------------------------------------------------------------ smart buttons
    def action_view_purchase_orders(self):
        """Purchase Orders button."""
        self.ensure_one()
        pos = self.env['purchase.order'].search(['|', ('material_requisition_id', '=', self.id), ('origin', 'like', self.name)])
        action = {'type': 'ir.actions.act_window', 'res_model': 'purchase.order', 'name': _('Purchase Orders')}
        if len(pos) == 1:
            return dict(action, res_id=pos.id, view_mode='form')
        return dict(action, domain=[('id', 'in', pos.ids)], view_mode='list,form')

    def action_view_transfer(self):
        """Internal Transfer button."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': self.picking_id.id, 'view_mode': 'form'}

    def action_view_mrp_production(self):
        """Manufacturing Order button."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'mrp.production', 'res_id': self.mrp_production_id.id, 'view_mode': 'form'}

    def action_print_requisition_report(self):
        """Print the requisition PDF."""
        return self.env.ref('advance_manufacturing.action_report_material_requisition').report_action(self)


class MaterialRequisitionLine(models.Model):
    """One product on a requisition."""
    _name = 'material.requisition.line'
    _description = 'Material Requisition Line'

    requisition_id = fields.Many2one('material.requisition', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True, domain="[('product_tmpl_id.is_finished_good', '=', False)]")
    product_uom_qty = fields.Float(string='Requested Quantity', default=1.0)
    product_uom = fields.Many2one('uom.uom', related='product_id.uom_id', store=True)
    short_close = fields.Boolean(string='Short Close')
    onhand_quantity = fields.Float(string='Destination On Hand Qty', compute='_compute_onhand', store=True)
    is_stock_available = fields.Boolean(compute='_compute_stock', store=True)
    qty_to_purchase = fields.Float(compute='_compute_stock', store=True)
    qty_to_transfer = fields.Float(compute='_compute_stock', store=True)
    selected_lot_ids = fields.Many2many('stock.lot', 'mr_line_selected_lot_rel', 'line_id', 'lot_id', string='Lots to Use', copy=False)

    @api.constrains('product_uom_qty')
    def _check_qty(self):
        """Requested quantity must be positive."""
        for rec in self:
            if rec.product_uom_qty <= 0:
                raise ValidationError(_('Requested Quantity must be greater than zero.'))

    @api.depends('product_id', 'requisition_id.destination_location_id')
    def _compute_onhand(self):
        """Stock of this product at the destination location."""
        for line in self:
            loc = line.requisition_id.destination_location_id
            line.onhand_quantity = line.product_id.with_context(location=loc.id).qty_available if loc and line.product_id else 0.0

    @api.depends('product_id', 'product_uom_qty', 'requisition_id.source_location_id', 'requisition_id.mrp_production_id')
    def _compute_stock(self):
        """How much can come from the source location and how much must be bought (earlier lines use stock first)."""
        for line in self:
            req = line.requisition_id
            src = req.source_location_id
            if not src or not line.product_id:
                line.is_stock_available, line.qty_to_purchase, line.qty_to_transfer = False, line.product_uom_qty, 0.0
                continue
            quants = self.env['stock.quant'].search([('product_id', '=', line.product_id.id), ('location_id', '=', src.id)])
            if req.mrp_production_id:
                free = sum(q.quantity - q.reserved_quantity for q in quants)
            else:
                free = sum(quants.mapped('quantity'))
            earlier = sum(req.material_requisition_line_ids.filtered(
                lambda l: l.product_id == line.product_id and isinstance(l.id, int) and isinstance(line.id, int) and l.id < line.id
            ).mapped('product_uom_qty'))
            effective = max(free - earlier, 0.0)
            transfer = min(line.product_uom_qty, effective)
            shortage = line.product_uom_qty - transfer
            line.qty_to_transfer = transfer
            line.qty_to_purchase = shortage
            line.is_stock_available = shortage <= 0


class PurchaseOrder(models.Model):
    """Orders raised from a requisition deliver straight to the requisition's destination (e.g. the floor)."""
    _inherit = 'purchase.order'

    material_requisition_id = fields.Many2one('material.requisition', string='Material Requisition', readonly=True, copy=False)

    def _get_destination_location(self):
        """Receipt goes to the requisition's destination when there is one."""
        self.ensure_one()
        if self.material_requisition_id.destination_location_id:
            return self.material_requisition_id.destination_location_id.id
        return super()._get_destination_location()

    @api.model_create_multi
    def create(self, vals_list):
        """Users flagged 'Block Create Purchase Order' cannot create RFQs or orders."""
        if self.env.user.block_create_purchase_order and not self.env.su:
            raise UserError(_('You do not have permission to create RFQs or purchase orders.'))
        return super().create(vals_list)


class ResUsers(models.Model):
    """Requisition settings on the user."""
    _inherit = 'res.users'

    mr_approval_type_id = fields.Many2one('material.request.approver.master', string='MR Approval Type',
                                          help='Used for requisitions created from manufacturing orders by this user.')
    block_create_purchase_order = fields.Boolean(string='Block Create Purchase Order',
                                                 help='Hide the Purchase module for this user and block RFQ or purchase order creation.')

    def _sync_purchase_block(self):
        """Blocked users lose the Purchase User and Purchase Manager roles."""
        groups = self.env.ref('purchase.group_purchase_user') | self.env.ref('purchase.group_purchase_manager')
        for user in self.filtered('block_create_purchase_order'):
            user.with_context(skip_purchase_block_sync=True).sudo().write({'groups_id': [(3, g.id) for g in groups]})

    @api.model_create_multi
    def create(self, vals_list):
        """After creating users, apply the purchase block."""
        users = super().create(vals_list)
        users._sync_purchase_block()
        return users

    def write(self, vals):
        """When the block flag or the roles change, apply the purchase block."""
        res = super().write(vals)
        if not self.env.context.get('skip_purchase_block_sync') and ('block_create_purchase_order' in vals or 'groups_id' in vals):
            self._sync_purchase_block()
        return res


class StockLocation(models.Model):
    """Location flags used by manufacturing."""
    _inherit = 'stock.location'

    is_mr_source_location = fields.Boolean(string='Default MR Source Location',
                                           help='Requisitions created automatically from manufacturing orders take their material from here.')
    for_scrap_order = fields.Boolean(string='For Scrap Order', default=False,
                                     help='Automatically creates a Scrap Order when the destination of an Internal Transfer is this Rejection Location.')
    is_mo_stock = fields.Boolean(string='MO Stock', default=False,
                                 help='Check this box if this location is used for Manufacturing Order stock.')

    @api.constrains('is_mr_source_location')
    def _check_single_mr_source(self):
        """Only one default requisition source location."""
        for rec in self.filtered('is_mr_source_location'):
            other = self.search([('is_mr_source_location', '=', True), ('id', '!=', rec.id)], limit=1)
            if other:
                raise ValidationError(_("Only one location can be marked as the default Material Requisition source "
                                        "location. Location '%s' is already set.", other.display_name))

    @api.constrains('is_mo_stock')
    def _check_single_mo_stock(self):
        """Only one MO Stock location."""
        for rec in self.filtered('is_mo_stock'):
            other = self.search([('is_mo_stock', '=', True), ('id', '!=', rec.id)], limit=1)
            if other:
                raise ValidationError(_("Only one location can be marked as 'MO Stock'. Location '%s' is already set as MO Stock.",
                                        other.display_name))
