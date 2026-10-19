# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


TODO_SUMMARIES = ('Approval requested', 'Rejected - please fix and resubmit')

APPROVAL_FIELDS = (
    'approval_state', 'submitted_by', 'submitted_date', 'approved_by', 'approved_date', 'rejection_reason',
)


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

    # Stored fields that may still be edited on an approved document when the
    # "Lock Approved Documents" switch is on (models can add to this)
    _epc_lock_whitelist = ()

    # Only Project Managers / Administrators may approve or reject, enforced
    # here (not just by hiding the buttons on the form)
    def _epc_check_manager(self):
        if not (self.env.su or self.env.user.has_group('csl_epc_core.group_epc_manager')):
            raise AccessError("Only a Project Manager or Administrator can approve or reject this document.")

    # Raises if the "Block Self-Approval" switch is on and the approver is the submitter
    def _epc_check_not_self(self):
        if self.env['epc.config'].flag('block_self_approval') and not self.env.su:
            for record in self:
                if record.submitted_by and record.submitted_by == self.env.user:
                    raise UserError("You submitted this document, so someone else has to approve or reject it.")

    # Raises unless every record is in one of the given approval states
    def _epc_require_state(self, states, action):
        for record in self:
            if record.approval_state not in states:
                raise UserError(
                    "%s cannot be %s while its status is '%s'." % (
                        record.display_name, action,
                        dict(self._fields['approval_state'].selection).get(record.approval_state)))

    # Users who can approve (Project Managers and above), used for notifications
    def _epc_approvers(self):
        manager_group = self.env.ref('csl_epc_core.group_epc_manager')
        users = self.env['res.users'].sudo().search([('share', '=', False), ('active', '=', True)])
        return users.filtered(lambda user: manager_group in user.groups_id)

    # Removes the approval to-dos that are no longer relevant (the request was
    # answered, or the document was reset/resubmitted), so they never pile up
    def _epc_clear_todos(self, summaries):
        for record in self:
            if hasattr(record, 'activity_ids'):
                record.activity_ids.filtered(lambda act: act.summary in summaries).sudo().unlink()

    # Schedules a to-do for the given users unless notifications are switched off
    def _epc_schedule_todo(self, users, summary):
        if self.env['epc.config'].flag('disable_notifications') or not hasattr(self, 'activity_schedule'):
            return
        for record in self:
            for user in users:
                record.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', summary=summary, user_id=user.id)

    # Blocks edits on an approved document when "Lock Approved Documents" is on
    def write(self, vals):
        if vals and not self.env.su and self.env['epc.config'].flag('lock_approved'):
            allowed = set(self._epc_lock_whitelist) | set(APPROVAL_FIELDS) | set(
                name for name, field in self._fields.items()
                if name.startswith('message_') or name.startswith('activity_') or not field.store)
            blocked = set(vals) - allowed
            if blocked and any(record.approval_state == 'approved' for record in self):
                raise UserError(
                    "This document is approved and locked. Use Reset to Draft first if it "
                    "really has to change.")
        return super().write(vals)

    # Moves the document from "being prepared" to "waiting for manager approval"
    def action_submit(self):
        self._epc_require_state(('to_submit', 'rejected'), 'submitted')
        self._epc_clear_todos(TODO_SUMMARIES)
        for record in self:
            record.write({
                'approval_state': 'submitted',
                'submitted_by': self.env.user.id,
                'submitted_date': fields.Datetime.now(),
            })
        self._epc_schedule_todo(
            self._epc_approvers() - self.env.user, "Approval requested")

    # Manager clicks this to clear the document to move forward in the pipeline
    def action_approve(self):
        self._epc_check_manager()
        self._epc_require_state(('submitted',), 'approved')
        self._epc_check_not_self()
        self._epc_clear_todos(TODO_SUMMARIES)
        for record in self:
            record.write({
                'approval_state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            record._epc_notify_submitter("approved")

    # Opens the small pop-up that asks for the rejection reason (the Reject
    # button on the forms calls this; the pop-up then calls action_reject)
    def action_open_reject_wizard(self):
        self.ensure_one()
        self._epc_check_manager()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject',
            'res_model': 'epc.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }

    # Manager clicks this to send the document back for rework; a reason is required
    # so the person who submitted it knows exactly what needs fixing
    def action_reject(self):
        self._epc_check_manager()
        self._epc_require_state(('submitted',), 'rejected')
        self._epc_check_not_self()
        for record in self:
            if not record.rejection_reason:
                raise UserError(
                    "Please write a rejection reason before rejecting this "
                    "document, so the submitter knows what to correct."
                )
            record._epc_clear_todos(TODO_SUMMARIES)
            record.write({
                'approval_state': 'rejected',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            record._epc_notify_submitter("rejected")
            if record.submitted_by:
                record._epc_schedule_todo(record.submitted_by, "Rejected - please fix and resubmit")

    # Tells the person who submitted the document what happened to it
    def _epc_notify_submitter(self, outcome):
        self.ensure_one()
        if self.env['epc.config'].flag('disable_notifications') or not self.submitted_by \
                or not hasattr(self, 'message_post'):
            return
        body = "%s was %s by %s." % (self.display_name, outcome, self.env.user.name)
        if outcome == 'rejected' and self.rejection_reason:
            body += " Reason: %s" % self.rejection_reason
        self.sudo().message_post(body=body, partner_ids=[self.submitted_by.partner_id.id])

    # Lets the submitter pull a rejected (or submitted) document back to
    # "being prepared" so they can edit and resubmit it
    def action_reset_to_submit(self):
        # Re-opening an approved document is a manager decision
        if any(record.approval_state == 'approved' for record in self):
            self._epc_check_manager()
        self._epc_clear_todos(TODO_SUMMARIES)
        for record in self:
            record.write({
                'approval_state': 'to_submit',
                'submitted_by': False,
                'submitted_date': False,
                'approved_by': False,
                'approved_date': False,
                'rejection_reason': False,
            })
