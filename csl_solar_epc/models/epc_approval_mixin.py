# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class EpcApprovalMixin(models.AbstractModel):
    """Reusable 'needs sign-off' behaviour shared by Site Survey, Feasibility,
    BOQ, Commissioning and Handover records.

    In plain words: instead of writing the same Submit/Approve/Reject buttons
    and status field five separate times, every document that needs a manager
    sign-off before it can move forward just adds this mixin and gets the
    same behaviour for free.
    """
    _name = 'epc.approval.mixin'
    _description = 'EPC Approval Workflow (shared Submit/Approve/Reject logic)'

    approval_state = fields.Selection(
        [
            ('to_submit', 'To Submit'),
            ('submitted', 'Submitted for Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Approval Status',
        default='to_submit',
        tracking=True,
        copy=False,
        help="Where this document stands in its sign-off process: still being "
             "prepared (To Submit), waiting on a manager (Submitted), cleared "
             "to move forward (Approved), or sent back for rework (Rejected).",
    )
    submitted_by = fields.Many2one(
        'res.users', string='Submitted By', copy=False, readonly=True,
        help="The person who marked this document ready and sent it for approval.",
    )
    submitted_date = fields.Datetime(
        string='Submitted On', copy=False, readonly=True,
        help="Date and time this document was sent for approval.",
    )
    approved_by = fields.Many2one(
        'res.users', string='Approved By', copy=False, readonly=True,
        help="The manager who approved (or rejected) this document.",
    )
    approved_date = fields.Datetime(
        string='Approved On', copy=False, readonly=True,
        help="Date and time this document was approved or rejected.",
    )
    rejection_reason = fields.Text(
        string='Rejection Reason', copy=False,
        help="Why this document was sent back. Fill this in before rejecting "
             "so the person who submitted it knows what to fix.",
    )

    # Moves the document from "being prepared" to "waiting for manager approval"
    def action_submit(self):
        for record in self:
            record.write({
                'approval_state': 'submitted',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })

    # Manager clicks this to clear the document to move forward in the pipeline
    def action_approve(self):
        for record in self:
            record.write({
                'approval_state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })

    # Manager clicks this to send the document back for rework; a reason is required
    # so the person who submitted it knows exactly what needs fixing
    def action_reject(self):
        for record in self:
            if not record.rejection_reason:
                raise UserError(
                    "Please write a rejection reason before rejecting this "
                    "document, so the submitter knows what to correct."
                )
            record.write({
                'approval_state': 'rejected',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })

    # Lets the submitter pull a rejected (or submitted) document back to
    # "being prepared" so they can edit and resubmit it
    def action_reset_to_submit(self):
        for record in self:
            record.write({
                'approval_state': 'to_submit',
                'submitted_by': False,
                'submitted_date': False,
                'approved_by': False,
                'approved_date': False,
                'rejection_reason': False,
            })
