# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EpcQualityCheck(models.Model):
    """Stage 12 of the EPC pipeline: Quality Checks. Standard Odoo Quality app
    assumes every check is tied to a warehouse stock picking, which doesn't fit
    on-site installation/electrical/final checks — so this is a small, purpose-
    built checklist model covering all four QC categories from the process flow.
    """
    _name = 'epc.quality.check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Solar Quality Check'
    _order = 'check_date desc, id desc'

    name = fields.Char(
        string='QC Reference', default='New', copy=False, readonly=True,
        help="Auto-generated reference number for this quality check, e.g. QC/2026/00001.",
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True,
        help="The solar project this quality check was carried out on.",
    )
    category = fields.Selection(
        [
            ('incoming_material', 'Incoming Material QC'),
            ('final', 'Final QC'),
        ],
        string='QC Category', required=True, tracking=True,
        help="Which stage of quality checking this is: material arriving on site, "
             "or the final sign-off before handover.",
    )
    picking_id = fields.Many2one(
        'stock.picking', string='Related Delivery/Receipt',
        help="For Incoming Material checks, the stock receipt this check was done "
             "against. Not applicable to on-site installation/electrical/final checks.",
    )
    inspector_id = fields.Many2one(
        'res.users', string='Inspector', default=lambda self: self.env.user,
        help="The person who carried out this quality check.",
    )
    check_date = fields.Date(
        string='Check Date', default=fields.Date.context_today,
        help="The date this quality check was performed.",
    )
    line_ids = fields.One2many(
        'epc.quality.check.line', 'check_id', string='Checklist Items',
        help="Each individual item inspected and whether it passed.",
    )
    overall_result = fields.Selection(
        [('pending', 'Pending'), ('pass', 'Pass'), ('fail', 'Fail')],
        string='Overall Result', compute='_compute_overall_result', store=True,
        help="Automatically worked out from the checklist items: Fail if any item "
             "failed, Pass if every item passed, otherwise Pending.",
    )
    remarks = fields.Text(
        string='Remarks',
        help="Any additional notes about this quality check.",
    )
    fail_reason = fields.Text(
        string='Reason for Failure', tracking=True,
        help="Why this check failed. It has to be filled in whenever the check fails, "
             "and it is written in the chatter so there is a record of it.",
    )
    previous_check_id = fields.Many2one(
        'epc.quality.check', string='Re-inspection Of', copy=False, readonly=True,
        help="The failed check this one was created from when it was re-inspected.",
    )
    fail_notified = fields.Boolean(
        copy=False,
        help="Technical flag: a 'quality check failed' to-do has already been sent for this check.",
    )

    # Fills in the sequence-based reference number the first time a check is saved.
    # The "failed" notification is sent only after the check itself is fully
    # created (sending it while its lines are still being created made Odoo try
    # to add the same follower twice).
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('epc.quality.check') or 'New'
        checks = super(EpcQualityCheck, self.with_context(epc_creating_check=True)).create(vals_list)
        checks = checks.with_env(self.env)      # drop the "creating" flag from the returned records
        checks._epc_after_result_change()
        return checks

    # Suggests checklist items for whichever QC category is picked, pulled from
    # the configurable list at Solar EPC > Configuration > QC Checkpoints (not
    # hardcoded in Python) so a Project Manager can tailor what gets checked
    # without needing a code change. Re-runs every time the category changes
    # (not just the first time) and replaces whatever checklist was showing
    # before, since the checklist is meant to always match the category
    # currently selected — leaving the old category's items behind after
    # switching would silently check the wrong things (e.g. still showing
    # Incoming Material's items after switching to Installation QC).
    @api.onchange('category')
    def _onchange_category(self):
        if not self.category:
            return
        if self.category == 'incoming_material':
            # Per-product lines depend on which receipt is picked too, so
            # both onchanges share one method that rebuilds the whole list
            self._epc_rebuild_incoming_checklist()
            return
        checkpoints = self.env['epc.quality.checkpoint'].search([('category', '=', self.category)])
        self.line_ids = [(5, 0, 0)] + [
            (0, 0, {'name': checkpoint.name}) for checkpoint in checkpoints
        ]

    # Rebuilds Incoming Material QC's checklist from scratch: the generic
    # checkpoints configured for Incoming Material (things that apply to every
    # delivery, e.g. "Packaging Condition"), plus one line per actual product
    # on whichever receipt is currently picked — so the checklist always
    # matches what was really ordered and delivered, never a generic guess
    @api.onchange('picking_id')
    def _onchange_picking_id(self):
        if self.category == 'incoming_material':
            self._epc_rebuild_incoming_checklist()

    def _epc_rebuild_incoming_checklist(self):
        checkpoints = self.env['epc.quality.checkpoint'].search([('category', '=', 'incoming_material')])
        generic_lines = [(0, 0, {'name': checkpoint.name}) for checkpoint in checkpoints]
        product_lines = [
            (0, 0, {'name': move.product_id.display_name})
            for move in self.picking_id.move_ids
        ] if self.picking_id else []
        self.line_ids = [(5, 0, 0)] + generic_lines + product_lines

    # Works out the overall pass/fail result from the individual checklist items:
    # any failure fails the whole check; "Not Applicable" lines are ignored; it
    # passes only when at least one real item exists and every one of them passed
    @api.depends('line_ids.result')
    def _compute_overall_result(self):
        for check in self:
            results = [result for result in check.line_ids.mapped('result') if result != 'na']
            if 'fail' in results:
                check.overall_result = 'fail'
            elif results and all(result == 'pass' for result in results):
                check.overall_result = 'pass'
            else:
                check.overall_result = 'pending'

    # A failed line must say why, when the "Failed Items Need a Remark" switch is on
    @api.constrains('line_ids')
    def _check_failed_lines_have_remarks(self):
        if not self.env['epc.config'].flag('qc_require_fail_remark'):
            return
        for check in self:
            missing = check.line_ids.filtered(lambda line: line.result == 'fail' and not line.remarks)
            if missing:
                raise ValidationError(
                    "Write a remark for every failed item (%s) so the reason is on record." %
                    ", ".join(missing.mapped('name')))

    # Every time a check turns out to be Failed, writes it in the chatter (which
    # items failed and why), asks for the reason if it has not been given, and
    # sends a to-do to the project's manager (or the approvers). A check that
    # is fixed and then fails again is logged again.
    def _epc_after_result_change(self):
        for check in self.exists():
            failed = check.overall_result == 'fail'
            if failed and not check.fail_notified:
                check.sudo().fail_notified = True
                failed_lines = check.line_ids.filtered(lambda line: line.result == 'fail')
                items = Markup("").join(
                    Markup("<li>%s%s</li>") % (line.name, " - %s" % line.remarks if line.remarks else "")
                    for line in failed_lines)
                body = Markup("<b>Quality check failed.</b><ul>%s</ul>") % items
                if check.fail_reason:
                    body += Markup("<b>Reason:</b> %s") % check.fail_reason
                else:
                    body += Markup("<b>Reason:</b> not given yet - please write why it failed.")
                check.message_post(body=body)
                check._epc_log_failure_elsewhere(failed_lines)
                if not self.env['epc.config'].flag('disable_notifications'):
                    users = check.project_id.user_id or self.env['epc.approval.mixin']._epc_approvers()
                    for user in users:
                        check.sudo().activity_schedule(
                            'mail.mail_activity_data_todo',
                            summary="Quality check failed: %s" % check.name, user_id=user.id)
                    if not check.fail_reason and check.inspector_id:
                        check.sudo().activity_schedule(
                            'mail.mail_activity_data_todo', user_id=check.inspector_id.id,
                            summary="Write why quality check %s failed" % check.name)
            elif not failed and check.fail_notified:
                check.sudo().fail_notified = False

    # One save changes the check and its items together: look at the result once,
    # after everything (items and reason) has been written
    def write(self, vals):
        result = super(EpcQualityCheck, self.with_context(epc_creating_check=True)).write(vals)
        self._epc_after_result_change()
        return result

    # The other records a failed check should also be written on (a list of
    # records; other modules add to it). Incoming Material checks go to the
    # receipt they were done against and to its purchase order.
    def _epc_failure_documents(self):
        self.ensure_one()
        documents = []
        if self.picking_id:
            documents.append(self.picking_id)
            documents.extend(self.picking_id.move_ids.mapped('purchase_line_id.order_id'))
        return documents

    # Writes the failure (check link, failed items, reason) in the chatter of
    # those other records, as an internal note, so the people working there see it
    def _epc_log_failure_elsewhere(self, failed_lines):
        self.ensure_one()
        documents = self._epc_failure_documents()
        if not documents:
            return
        items = Markup("").join(
            Markup("<li>%s%s</li>") % (line.name, " - %s" % line.remarks if line.remarks else "")
            for line in failed_lines)
        label = dict(self._fields['category'].selection).get(self.category, 'Quality check')
        body = Markup("<b>%s failed</b> (%s).<ul>%s</ul>") % (label, self._get_html_link(), items)
        if self.fail_reason:
            body += Markup("<b>Reason:</b> %s") % self.fail_reason
        for document in documents:
            document.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')

    # Creates a new check of the same kind for the same project / receipt,
    # carrying over only the items that failed, so they can be inspected again.
    # The newest check is the one that counts; the failed one stays as history.
    def action_reinspect(self):
        self.ensure_one()
        if self.overall_result != 'fail':
            raise UserError("Only a failed check can be re-inspected.")
        failed = self.line_ids.filtered(lambda line: line.result == 'fail')
        new = self.create({
            'project_id': self.project_id.id,
            'category': self.category,
            'picking_id': self.picking_id.id,
            'previous_check_id': self.id,
            'line_ids': [(0, 0, {'name': line.name}) for line in failed],
        })
        self.message_post(body="Re-inspection %s created." % new.name)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'epc.quality.check',
            'view_mode': 'form',
            'res_id': new.id,
            'target': 'current',
        }

    # Once Final QC has passed, moves the material still sitting at this
    # project's site location into "Installed / Consumed" - it has now
    # physically gone into the system being built, so it should stop counting
    # as warehouse stock on hand. Only free stock that can be consumed cleanly
    # is moved; anything that cannot (reserved elsewhere, lot/serial number not
    # recorded) is left alone and listed, instead of failing the whole step.
    def action_consume_site_stock(self):
        self.ensure_one()
        if self.category != 'final' or self.overall_result != 'pass':
            raise UserError("Only a Final QC that has Passed can consume the material at site.")
        latest = self.sudo().search([('project_id', '=', self.project_id.id), ('category', '=', 'final')], limit=1)
        if latest and latest != self and latest.overall_result != 'pass':
            raise UserError("A newer Final QC (%s) exists and has not passed. Pass it first." % latest.name)
        site_location = self.project_id.site_location_id
        if not site_location:
            raise UserError("This project has no material issued to its site yet — nothing to consume.")
        quants = self.env['stock.quant'].search([
            ('location_id', '=', site_location.id),
            ('quantity', '>', 0),
        ])
        if not quants:
            raise UserError("There is no stock left at this project's site to consume.")

        consumed_location = self.env.ref('csl_epc_quality.epc_location_consumed')
        move_vals = []
        skipped = []
        for product in quants.mapped('product_id'):
            move_lines = []
            quantity = 0.0
            for quant in quants.filtered(lambda q: q.product_id == product):
                free = quant.quantity - quant.reserved_quantity
                if quant.reserved_quantity > 0:
                    skipped.append("%s%s: %s reserved for another transfer" % (
                        product.display_name, " (lot %s)" % quant.lot_id.name if quant.lot_id else "",
                        quant.reserved_quantity))
                if free <= 0:
                    continue
                if product.tracking != 'none' and not quant.lot_id:
                    skipped.append("%s: %s at site has no lot/serial number recorded - add it with an "
                                   "inventory adjustment on %s, then try again" % (
                                       product.display_name, free, site_location.display_name))
                    continue
                if product.tracking == 'serial' and abs(free - round(free)) > 1e-6:
                    skipped.append("%s: serial-tracked stock must be whole units (%s)" % (product.display_name, free))
                    continue
                quantity += free
                move_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'lot_id': quant.lot_id.id,
                    'package_id': quant.package_id.id,
                    'owner_id': quant.owner_id.id,
                    'quantity': free,
                    'picked': True,
                    'location_id': site_location.id,
                    'location_dest_id': consumed_location.id,
                }))
            if move_lines:
                move_vals.append((0, 0, {
                    'name': product.display_name,
                    'product_id': product.id,
                    'product_uom_qty': quantity,
                    'product_uom': product.uom_id.id,
                    'location_id': site_location.id,
                    'location_dest_id': consumed_location.id,
                    'move_line_ids': move_lines,
                }))
        if not move_vals:
            raise UserError(
                "Nothing at this project's site can be consumed right now:\n- " + "\n- ".join(skipped))

        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': site_location.id,
            'location_dest_id': consumed_location.id,
            'origin': self.name,
            'project_id': self.project_id.id,
            'move_ids': move_vals,
        })
        picking.action_confirm()
        picking.move_ids.picked = True
        picking.with_context(skip_backorder=True, skip_immediate=True, skip_sms=True).button_validate()
        if skipped:
            self.message_post(body=Markup("Consumed everything that could be consumed. Left at site:<br/>") +
                              Markup("<br/>").join(escape(line) for line in skipped))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }


class EpcQualityCheckLine(models.Model):
    """One individual item on a Quality Check's checklist, for example
    'Insulation Test' or 'Module QC', with a pass/fail/not-applicable result.
    """
    _name = 'epc.quality.check.line'
    _description = 'Solar Quality Check Line'
    _order = 'id'

    check_id = fields.Many2one(
        'epc.quality.check', string='Quality Check', required=True, ondelete='cascade',
        help="The quality check this checklist item belongs to.",
    )
    name = fields.Char(
        string='Checklist Item', required=True,
        help="What is being checked, e.g. 'Insulation Test' or 'Module QC'.",
    )
    result = fields.Selection(
        [('pending', 'Pending'), ('pass', 'Pass'), ('fail', 'Fail'), ('na', 'Not Applicable')],
        string='Result', default='pending',
        help="Whether this specific item passed inspection.",
    )
    remarks = fields.Char(
        string='Remarks',
        help="Any note about this specific checklist item, especially useful if it failed.",
    )

    # Stops changes to the results of a finished check when the "Lock Finished
    # Quality Checks" switch is on (a Project Manager can still change them)
    def _epc_check_unlocked(self):
        if self.env.su or not self.env['epc.config'].flag('qc_lock_results'):
            return
        if self.env.user.has_group('csl_epc_core.group_epc_manager'):
            return
        if any(line.check_id.overall_result in ('pass', 'fail') for line in self):
            raise UserError("This quality check is finished and locked. Ask a Project Manager to change it.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env.context.get('epc_creating_check'):
            lines.mapped('check_id')._epc_after_result_change()
        return lines

    def write(self, vals):
        self._epc_check_unlocked()
        result = super().write(vals)
        if 'result' in vals and not self.env.context.get('epc_creating_check'):
            self.mapped('check_id')._epc_after_result_change()
        return result

    def unlink(self):
        self._epc_check_unlocked()
        return super().unlink()
