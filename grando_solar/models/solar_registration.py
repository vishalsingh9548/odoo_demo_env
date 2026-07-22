from odoo import models, fields, api
from odoo.exceptions import UserError


class SolarRegistration(models.Model):
    _name = 'solar.registration'
    _description = 'Solar Registration Department Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Registration Reference",
        required=True,
        copy=False,
        default="New",
    )

    design_id = fields.Many2one('solar.design', string='Design')
    sale_order_id = fields.Many2one('sale.order', string='Quotation', required=True)
    lead_id = fields.Many2one(
        related='design_id.lead_id',
        store=True,
        string='Lead',
    )

    # Stage 7: Registration Department Workflow
    sales_rep_id = fields.Many2one(
        'res.users',
        string='Sales Rep (Deal Shared By)',
        help="e.g. Satish Shekh",
        tracking=True,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('file_checked', 'File Checked / Process Started'),
        ('cash_feasibility_check', 'Cash Feasibility Check'),
        ('loan_process', 'Loan Process'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True, string='Registration Stage')

    payment_mode = fields.Selection([
        ('cash', 'Full Cash'),
        ('loan', 'Loan'),
        ('partial_loan', 'Partial Loan'),
    ], string='Payment Mode')

    # A. Cash Payment Flow
    cash_feasibility_result = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', string='Cash Feasibility Result')

    # B. Loan / Partial Loan Flow
    loan_dept_user_id = fields.Many2one(
        'res.users',
        string='Loan Dept Executive',
        help="e.g. Dipak Shekh",
    )
    loan_approval_result = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', string='Loan Approval Result')

    # Stage 9: Completed Installation Files Returned to Registration Dept.
    installation_ids = fields.One2many(
        'solar.installation', 'registration_id', string='Installations',
    )
    installation_count = fields.Integer(compute='_compute_installation_count')
    installation_files_received = fields.Boolean(string='Installation Files Received')
    installation_files_received_date = fields.Datetime(string='Files Received On')

    # Stage 10: Payment Clearance Verification Before DISCOM
    payment_clearance_state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ], default='pending', string='Payment Clearance', tracking=True)
    payment_clearance_checked_by_id = fields.Many2one(
        'res.users',
        string='Payment Confirmed By (Accounts)',
        help="e.g. Mitul Patel",
    )
    payment_clearance_date = fields.Datetime(string='Payment Clearance Date')

    discom_id = fields.Many2one('solar.discom.activation', string='DISCOM Activation', copy=False)
    discom_count = fields.Integer(compute='_compute_discom_count')

    def _compute_discom_count(self):
        for rec in self:
            rec.discom_count = 1 if rec.discom_id else 0

    def _compute_installation_count(self):
        for rec in self:
            rec.installation_count = len(rec.installation_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('solar.registration')
        return super().create(vals)

    # --- Stage 7 actions ---
    def action_start_process(self):
        self.write({'state': 'file_checked'})

    def action_select_cash_payment(self):
        self.write({'payment_mode': 'cash', 'state': 'cash_feasibility_check'})

    def action_select_loan_payment(self):
        self.write({'payment_mode': 'loan', 'state': 'loan_process'})

    def action_select_partial_loan_payment(self):
        self.write({'payment_mode': 'partial_loan', 'state': 'loan_process'})

    def action_feasibility_approve(self):
        self.write({'cash_feasibility_result': 'approved', 'state': 'approved'})

    def action_feasibility_reject(self):
        self.write({'cash_feasibility_result': 'rejected', 'state': 'rejected'})

    def action_loan_approve(self):
        self.write({'loan_approval_result': 'approved', 'state': 'approved'})

    def action_loan_reject(self):
        self.write({'loan_approval_result': 'rejected', 'state': 'rejected'})

    # --- Bridge to Stage 8 (Installation Dept) ---
    def action_create_installation(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError("Registration must be Approved before creating an Installation record.")
        installation = self.env['solar.installation'].create({
            'registration_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.installation',
            'res_id': installation.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_installations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Installations',
            'res_model': 'solar.installation',
            'view_mode': 'list,form',
            'domain': [('registration_id', '=', self.id)],
            'context': {'default_registration_id': self.id},
        }

    # --- Called from solar.installation once installation is completed (Stage 9) ---
    def action_receive_installation_files(self):
        self.write({
            'installation_files_received': True,
            'installation_files_received_date': fields.Datetime.now(),
        })

    # --- Stage 10 actions ---
    def action_approve_payment_clearance(self):
        self.ensure_one()
        if not self.installation_files_received:
            raise UserError("Installation files have not been returned by the Installation Dept yet.")
        self.write({
            'payment_clearance_state': 'approved',
            'payment_clearance_date': fields.Datetime.now(),
        })

    # --- Bridge to Stage 11 (DISCOM & Final Activation) ---
    def action_create_discom_activation(self):
        self.ensure_one()
        if self.payment_clearance_state != 'approved':
            raise UserError("Payment Clearance must be Approved before submitting to DISCOM.")
        if self.discom_id:
            return self.action_view_discom()
        discom = self.env['solar.discom.activation'].create({
            'registration_id': self.id,
        })
        self.discom_id = discom.id
        return self.action_view_discom()

    def action_view_discom(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'solar.discom.activation',
            'res_id': self.discom_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
