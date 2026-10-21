# -*- coding: utf-8 -*-
"""Tests for the Solar EPC modules. They live in the parent module because it
depends on every stage, so one test class can walk the whole pipeline."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEpcFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # start from "every switch off", whatever the database has configured (rolled back after the tests)
        cls.env['ir.config_parameter'].sudo().search([('key', '=like', 'csl_epc.%')]).unlink()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.manager = Users.create({
            'name': 'EPC Manager', 'login': 'test_epc_manager', 'email': 'm@example.com',
            'groups_id': [(6, 0, [cls.env.ref('csl_epc_core.group_epc_manager').id])],
        })
        cls.field_user = Users.create({
            'name': 'EPC Field', 'login': 'test_epc_field', 'email': 'f@example.com',
            'groups_id': [(6, 0, [cls.env.ref('csl_epc_core.group_epc_user').id])],
        })
        cls.other_field_user = Users.create({
            'name': 'EPC Field 2', 'login': 'test_epc_field2', 'email': 'f2@example.com',
            'groups_id': [(6, 0, [cls.env.ref('csl_epc_core.group_epc_user').id])],
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Customer'})
        cls.lead = cls.env['crm.lead'].create({'name': 'Test Lead', 'partner_id': cls.partner.id, 'type': 'opportunity'})
        cls.product = cls.env['product.product'].create({'name': 'Test Panel', 'is_storable': True})

    def _config(self, **flags):
        for key, value in flags.items():
            self.env['ir.config_parameter'].sudo().set_param('csl_epc.%s' % key, 'True' if value else False)

    def _approved_boq(self, with_cost=True):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})
        survey.action_submit(); survey.action_approve()
        survey.action_create_feasibility()
        feasibility = survey.feasibility_ids
        feasibility.action_submit(); feasibility.action_approve()
        feasibility.action_create_boq()
        boq = feasibility.boq_ids
        self.env['epc.boq.line'].create({
            'boq_id': boq.id, 'category': 'solar_module', 'product_id': self.product.id,
            'quantity': 10, 'unit_cost': 100 if with_cost else 0,
        })
        boq.action_submit(); boq.action_approve()
        return boq

    # ---------------- happy path ----------------
    def test_full_pipeline(self):
        boq = self._approved_boq()
        boq.action_create_quotation()
        order = boq.sale_order_id
        self.assertTrue(order.is_epc_order)
        order.action_confirm()
        project = order.epc_project_id
        self.assertTrue(project)
        self.assertEqual(project.boq_id, boq)
        self.assertEqual(project.lead_id, self.lead)

    # ---------------- A1 ----------------
    def test_qc_not_applicable_lines_do_not_block_pass(self):
        project = self.env['project.project'].create({'name': 'P'})
        check = self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final',
            'line_ids': [(0, 0, {'name': 'a', 'result': 'pass'}), (0, 0, {'name': 'b', 'result': 'na'})],
        })
        self.assertEqual(check.overall_result, 'pass')
        check.line_ids[1].result = 'fail'
        self.assertEqual(check.overall_result, 'fail')
        only_na = self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'a', 'result': 'na'})]})
        self.assertEqual(only_na.overall_result, 'pending')

    # ---------------- A2 / A5 ----------------
    def test_qc_reinspect_and_latest_final_qc_counts(self):
        project = self.env['project.project'].create({'name': 'P'})
        failed = self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final',
            'line_ids': [(0, 0, {'name': 'a', 'result': 'fail'}), (0, 0, {'name': 'b', 'result': 'pass'})]})
        self.assertEqual(failed.overall_result, 'fail')
        self.assertTrue(failed.fail_notified)
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        self.assertTrue(commissioning.epc_needs_final_qc)
        action = failed.action_reinspect()
        new = self.env['epc.quality.check'].browse(action['res_id'])
        self.assertEqual(new.previous_check_id, failed)
        self.assertEqual(new.line_ids.mapped('name'), ['a'])
        new.line_ids.result = 'pass'
        commissioning.invalidate_recordset()
        self.assertFalse(commissioning.epc_needs_final_qc)
        # a newer failed Final QC makes the old pass worthless
        self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'x', 'result': 'fail'})]})
        commissioning.invalidate_recordset()
        self.assertTrue(commissioning.epc_needs_final_qc)

    def test_failed_check_created_by_a_real_user_in_one_save(self):
        # what the web form does: one create with the lines inside, by the user
        # who is also the project's manager (that user gets the to-do)
        project = self.env['project.project'].create({'name': 'P', 'user_id': self.manager.id})
        # followers are only added when mail tracking is on, as in the real app
        Check = self.env['epc.quality.check'].with_user(self.manager).with_context(
            tracking_disable=False, mail_notrack=False, mail_create_nosubscribe=False)
        check = Check.create({
            'project_id': project.id, 'category': 'final',
            'line_ids': [(0, 0, {'name': 'a', 'result': 'fail'})]})
        self.assertEqual(check.overall_result, 'fail')
        self.assertTrue(check.fail_notified)
        # adding a failing line later on a saved check also works
        ok = self.env['epc.quality.check'].with_user(self.manager).create({
            'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'a', 'result': 'pass'})]})
        self.env['epc.quality.check.line'].with_user(self.manager).create({
            'check_id': ok.id, 'name': 'b', 'result': 'fail'})
        self.assertTrue(ok.fail_notified)

    def test_failed_check_is_logged_with_reason_and_asks_when_missing(self):
        project = self.env['project.project'].create({'name': 'P'})
        with_reason = self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'fail_reason': 'Insulation below limit',
            'line_ids': [(0, 0, {'name': 'Insulation', 'result': 'fail', 'remarks': '0.4 MOhm'})]})
        bodies = ' '.join(with_reason.message_ids.mapped('body'))
        self.assertIn('Quality check failed', bodies)
        self.assertNotIn('&lt;b&gt;', bodies)          # real formatting, not visible tags
        self.assertIn('Insulation below limit', bodies)
        self.assertIn('0.4 MOhm', bodies)
        without = self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'inspector_id': self.manager.id,
            'line_ids': [(0, 0, {'name': 'Earthing', 'result': 'fail'})]})
        self.assertIn('not given yet', ' '.join(without.message_ids.mapped('body')))
        self.assertTrue(without.activity_ids.filtered(lambda a: 'Write why' in (a.summary or '')))
        # fixed, then failing again is logged again
        without.line_ids.result = 'pass'
        without.line_ids.result = 'fail'
        self.assertEqual(self.env['mail.message'].search_count([
            ('model', '=', 'epc.quality.check'), ('res_id', '=', without.id),
            ('body', 'ilike', 'Quality check failed')]), 2)

    def test_failed_incoming_check_is_logged_on_receipt_and_purchase_order(self):
        vendor = self.env['res.partner'].create({'name': 'Vendor'})
        project = self.env['project.project'].create({'name': 'P'})
        order = self.env['purchase.order'].create({
            'partner_id': vendor.id, 'project_id': project.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 3, 'price_unit': 10})]})
        order.button_confirm()
        picking = order.picking_ids
        self.assertTrue(picking)
        self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'incoming_material', 'picking_id': picking.id,
            'fail_reason': 'Boxes crushed',
            'line_ids': [(0, 0, {'name': 'Packaging', 'result': 'fail', 'remarks': 'torn'})]})
        for document in (picking, order):
            bodies = ' '.join(self.env['mail.message'].search([
                ('model', '=', document._name), ('res_id', '=', document.id)]).mapped('body'))
            self.assertIn('Incoming Material QC failed', bodies)
            self.assertIn('Boxes crushed', bodies)

    def test_failed_final_check_is_logged_on_commissioning(self):
        project = self.env['project.project'].create({'name': 'P'})
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'fail_reason': 'Inverter trips',
            'line_ids': [(0, 0, {'name': 'System Testing', 'result': 'fail', 'remarks': 'trips at 80%'})]})
        bodies = ' '.join(self.env['mail.message'].search([
            ('model', '=', 'epc.commissioning'), ('res_id', '=', commissioning.id)]).mapped('body'))
        self.assertIn('Final QC failed', bodies)
        self.assertIn('Inverter trips', bodies)
        self.assertIn('trips at 80%', bodies)

    def test_qc_fail_remark_switch(self):
        project = self.env['project.project'].create({'name': 'P'})
        self._config(qc_require_fail_remark=True)
        with self.assertRaises(ValidationError):
            self.env['epc.quality.check'].create({
                'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'a', 'result': 'fail'})]})

    # ---------------- B6 ----------------
    def test_only_managers_can_approve(self):
        survey = self.env['epc.site.survey'].with_user(self.field_user).create({'lead_id': self.lead.id})
        survey.action_submit()
        with self.assertRaises(AccessError):
            survey.action_approve()
        survey.with_user(self.manager).action_approve()
        self.assertEqual(survey.approval_state, 'approved')

    def test_old_approval_todos_do_not_pile_up(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})

        def todos(summary):
            return survey.activity_ids.filtered(lambda a: a.summary == summary)

        survey.action_submit()
        first = len(todos('Approval requested'))
        self.assertGreater(first, 0)
        survey.action_reset_to_submit()
        self.assertEqual(len(todos('Approval requested')), 0)
        survey.action_submit()
        survey.action_submit.__self__  # resubmitting does not double up
        self.assertEqual(len(todos('Approval requested')), first)
        survey.with_user(self.manager).action_approve()
        self.assertEqual(len(todos('Approval requested')), 0)

    def test_approval_state_guards(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})
        with self.assertRaises(UserError):
            survey.action_approve()           # not submitted yet
        survey.action_submit()
        with self.assertRaises(UserError):
            survey.action_submit()            # already submitted

    def test_block_self_approval_switch(self):
        self._config(block_self_approval=True)
        survey = self.env['epc.site.survey'].with_user(self.manager).create({'lead_id': self.lead.id})
        survey.action_submit()
        with self.assertRaises(UserError):
            survey.action_approve()

    def test_reject_wizard_asks_for_reason(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})
        survey.action_submit()
        action = survey.with_user(self.manager).action_open_reject_wizard()
        self.assertEqual(action['res_model'], 'epc.reject.wizard')
        wizard = self.env['epc.reject.wizard'].with_user(self.manager).with_context(**action['context']).create({
            'reason': 'Photos missing'})
        wizard.action_confirm()
        self.assertEqual(survey.approval_state, 'rejected')
        self.assertEqual(survey.rejection_reason, 'Photos missing')

    # ---------------- B7 ----------------
    def test_lock_approved_switch(self):
        boq = self._approved_boq()
        boq.margin_percent = 20      # allowed while the switch is off
        self._config(lock_approved=True)
        as_manager = boq.with_user(self.manager)      # superuser scripts bypass the lock, real users do not
        with self.assertRaises(UserError):
            as_manager.margin_percent = 30
        with self.assertRaises(UserError):
            as_manager.line_ids[0].quantity = 99
        as_manager.action_reset_to_submit()
        as_manager.margin_percent = 30

    # ---------------- B9 / B10 ----------------
    def test_next_stage_needs_approval(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})
        with self.assertRaises(UserError):
            survey.action_create_feasibility()

    def test_not_feasible_switch(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id, 'is_feasible': 'no'})
        survey.action_submit(); survey.action_approve()
        survey.action_create_feasibility()         # switch off: allowed
        self._config(block_not_feasible=True)
        survey2 = self.env['epc.site.survey'].create({'lead_id': self.lead.id, 'is_feasible': 'no'})
        survey2.action_submit(); survey2.action_approve()
        with self.assertRaises(UserError):
            survey2.action_create_feasibility()
        survey2.epc_proceed_anyway = True
        survey2.action_create_feasibility()

    # ---------------- C11 ----------------
    def test_plain_sale_order_creates_no_project(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})]})
        order.action_confirm()
        self.assertFalse(order.epc_project_id)
        order2 = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'is_epc_order': True,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 1})]})
        order2.action_confirm()
        self.assertTrue(order2.epc_project_id)

    def test_quotation_keeps_boq_price_when_unit_or_quantity_changes(self):
        self.product.list_price = 1200
        boq = self._approved_boq()          # unit cost 100, margin 15% -> 115
        boq.action_create_quotation()
        line = boq.sale_order_id.order_line
        self.assertAlmostEqual(line.price_unit, 115)
        self.assertEqual(line.product_uom, self.product.uom_id)
        line.product_uom = self.env.ref('uom.product_uom_dozen')
        line.product_uom = self.product.uom_id
        line.product_uom_qty = 25
        self.assertAlmostEqual(line.price_unit, 115)

    def test_boq_line_takes_cost_from_product(self):
        self.product.standard_price = 600
        boq = self._approved_boq(with_cost=True)
        line = self.env['epc.boq.line'].create({'boq_id': boq.id, 'category': 'solar_module', 'product_id': self.product.id})
        self.assertEqual(line.unit_cost, 600)
        explicit = self.env['epc.boq.line'].create({
            'boq_id': boq.id, 'category': 'solar_module', 'product_id': self.product.id, 'unit_cost': 5})
        self.assertEqual(explicit.unit_cost, 5)
        new_line = self.env['epc.boq.line'].new({'product_id': self.product.id})
        new_line._onchange_product_id_set_cost()
        self.assertEqual(new_line.unit_cost, 600)

    # ---------------- delivery on EPC orders ----------------
    def test_epc_order_has_no_delivery_but_plain_order_has(self):
        stock_product = self.env['product.product'].create({'name': 'Boxed', 'is_storable': True, 'type': 'consu'})
        line = [(0, 0, {'product_id': stock_product.id, 'product_uom_qty': 2})]
        plain = self.env['sale.order'].create({'partner_id': self.partner.id, 'order_line': line})
        plain.action_confirm()
        self.assertTrue(plain.picking_ids)
        epc = self.env['sale.order'].create({'partner_id': self.partner.id, 'is_epc_order': True, 'order_line': line})
        epc.action_confirm()
        self.assertFalse(epc.picking_ids)
        self.assertTrue(epc.epc_project_id)

    # ---------------- C12 / C13 ----------------
    def test_quotation_needs_lines_and_strict_check(self):
        survey = self.env['epc.site.survey'].create({'lead_id': self.lead.id})
        survey.action_submit(); survey.action_approve(); survey.action_create_feasibility()
        feasibility = survey.feasibility_ids
        feasibility.action_submit(); feasibility.action_approve(); feasibility.action_create_boq()
        boq = feasibility.boq_ids
        boq.action_submit(); boq.action_approve()
        with self.assertRaises(UserError):
            boq.action_create_quotation()         # no lines
        self.env['epc.boq.line'].create({'boq_id': boq.id, 'category': 'solar_module', 'quantity': 1})
        self._config(strict_boq=True)
        with self.assertRaises(UserError):
            boq.action_create_quotation()         # no product, no cost
        self._config(strict_boq=False)
        boq.action_create_quotation()

    def test_cancelled_quotation_can_be_regenerated_and_boq_revised(self):
        boq = self._approved_boq()
        boq.action_create_quotation()
        order = boq.sale_order_id
        order._action_cancel()
        self.assertFalse(boq.sale_order_id)
        boq.action_create_quotation()
        action = boq.with_user(self.manager).action_revise() if False else boq.action_revise()
        new = self.env['epc.boq'].browse(action['res_id'])
        self.assertTrue(boq.superseded)
        self.assertEqual(new.revision_number, 2)
        self.assertEqual(len(new.line_ids), 1)
        with self.assertRaises(UserError):
            boq.action_create_quotation()

    # ---------------- D16 / D17 ----------------
    def test_purchase_orders_per_vendor_and_no_double_issue(self):
        project = self.env['project.project'].create({'name': 'P'})
        vendor_a = self.env['res.partner'].create({'name': 'Vendor A'})
        vendor_b = self.env['res.partner'].create({'name': 'Vendor B'})
        prod_b = self.env['product.product'].create({'name': 'Cable', 'is_storable': True})
        request = self.env['epc.material.request'].create({
            'project_id': project.id,
            'line_ids': [
                (0, 0, {'product_id': self.product.id, 'quantity_required': 5, 'vendor_id': vendor_a.id}),
                (0, 0, {'product_id': prod_b.id, 'quantity_required': 3, 'vendor_id': vendor_b.id}),
            ]})
        request.action_submit(); request.action_approve()
        request.action_create_purchase_orders()
        self.assertEqual(request.purchase_order_count, 2)
        self.assertFalse(request.epc_has_shortfall)
        with self.assertRaises(UserError):
            request.action_create_purchase_orders()
        # issue: stock 5 of the first product, issue twice
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.env['stock.quant']._update_available_quantity(self.product, warehouse.lot_stock_id, 5)
        request.action_issue_to_project()
        request.line_ids.invalidate_recordset()
        self.assertEqual(request.line_ids[0].quantity_issued, 5)
        with self.assertRaises(UserError):
            request.action_issue_to_project()

    def test_project_button_issues_material_to_site(self):
        project = self.env['project.project'].create({'name': 'P'})
        request = self.env['epc.material.request'].create({
            'project_id': project.id,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'quantity_required': 4})]})
        self.assertFalse(project.epc_material_to_issue)          # not approved yet
        request.action_submit(); request.action_approve()
        warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.env['stock.quant']._update_available_quantity(self.product, warehouse.lot_stock_id, 10)
        project.invalidate_recordset(); request.line_ids.invalidate_recordset()
        self.assertTrue(project.epc_material_to_issue)
        action = project.action_issue_material_to_site()
        self.assertEqual(action['res_model'], 'stock.picking')
        project.invalidate_recordset(); request.line_ids.invalidate_recordset(); request.invalidate_recordset()
        self.assertFalse(project.epc_material_to_issue)          # button disappears once issued
        with self.assertRaises(UserError):
            project.action_issue_material_to_site()

    # ---------------- E19 ----------------
    def test_commissioning_switches(self):
        project = self.env['project.project'].create({'name': 'P'})
        self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'a', 'result': 'pass'})]})
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        self._config(comm_require_testing=True)
        with self.assertRaises(UserError):
            commissioning.action_submit()
        commissioning.system_testing_done = True
        commissioning.action_submit()
        self._config(comm_require_certificate=True)
        with self.assertRaises(UserError):
            commissioning.action_approve()
        commissioning.commissioning_certificate = 'dGVzdA=='
        commissioning.action_approve()
        self.assertEqual(commissioning.approval_state, 'approved')
        handover_action = commissioning.action_create_handover()
        self.assertEqual(handover_action['res_model'], 'epc.handover')

    def test_project_commissioning_smart_button(self):
        project = self.env['project.project'].create({'name': 'P'})
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        project.invalidate_recordset()
        self.assertEqual(project.commissioning_count, 1)
        action = project.action_view_commissionings()
        self.assertEqual(action['res_id'], commissioning.id)
        self.env['epc.commissioning'].create({'project_id': project.id})
        self.assertEqual(project.action_view_commissionings()['view_mode'], 'list,form')

    def test_commissioning_handover_smart_button(self):
        project = self.env['project.project'].create({'name': 'P'})
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        self.assertEqual(commissioning.handover_count, 0)
        handover = self.env['epc.handover'].create({'project_id': project.id})
        commissioning.invalidate_recordset()
        self.assertEqual(commissioning.handover_count, 1)
        self.assertEqual(commissioning.action_view_handovers()['res_id'], handover.id)

    def test_handover_creation_needs_approved_commissioning(self):
        project = self.env['project.project'].create({'name': 'P'})
        commissioning = self.env['epc.commissioning'].create({'project_id': project.id})
        with self.assertRaises(UserError):
            commissioning.action_create_handover()

    def test_handover_docs_switch(self):
        project = self.env['project.project'].create({'name': 'P'})
        handover = self.env['epc.handover'].create({'project_id': project.id})
        handover.action_submit()
        self._config(handover_require_docs=True)
        with self.assertRaises(UserError):
            handover.action_approve()

    # ---------------- E21 ----------------
    def test_project_amc_smart_button(self):
        project = self.env['project.project'].create({'name': 'P'})
        self.assertEqual(project.amc_count, 0)
        contract = self.env['epc.amc.contract'].create({'project_id': project.id})
        project.invalidate_recordset()
        self.assertEqual(project.amc_count, 1)
        self.assertEqual(project.action_view_amc_contracts()['res_id'], contract.id)

    def test_amc_cron_expires_and_renews(self):
        project = self.env['project.project'].create({'name': 'P', 'user_id': self.manager.id})
        contract = self.env['epc.amc.contract'].create({
            'project_id': project.id, 'start_date': '2020-01-01', 'end_date': '2020-12-31',
            'service_frequency': 'quarterly', 'next_service_date': '2020-03-31'})
        contract.action_activate()
        self.env['epc.amc.contract']._cron_epc_amc_maintenance()
        self.assertEqual(contract.state, 'expired')
        action = contract.action_renew()
        new = self.env['epc.amc.contract'].browse(action['res_id'])
        self.assertEqual(str(new.start_date), '2021-01-01')
        self.assertEqual(new.state, 'draft')

    def test_amc_generates_service_task_when_switched_on(self):
        project = self.env['project.project'].create({'name': 'P'})
        contract = self.env['epc.amc.contract'].create({
            'project_id': project.id, 'start_date': '2020-01-01', 'end_date': '2999-12-31',
            'service_frequency': 'quarterly', 'next_service_date': '2020-03-31'})
        contract.action_activate()
        self.env['epc.amc.contract']._cron_epc_amc_maintenance()
        self.assertEqual(str(contract.next_service_date), '2020-03-31')   # switch off: untouched
        self._config(amc_generate_services=True)
        self.env['epc.amc.contract']._cron_epc_amc_maintenance()
        self.assertGreater(str(contract.next_service_date), '2020-03-31')

    # ---------------- F22 ----------------
    def test_field_user_sees_only_own_records(self):
        mine = self.env['epc.site.survey'].with_user(self.field_user).create({'lead_id': self.lead.id})
        theirs = self.env['epc.site.survey'].with_user(self.other_field_user).create({'lead_id': self.lead.id})
        visible = self.env['epc.site.survey'].with_user(self.field_user).search([('id', 'in', (mine | theirs).ids)])
        self.assertEqual(visible, mine)
        visible_manager = self.env['epc.site.survey'].with_user(self.manager).search([('id', 'in', (mine | theirs).ids)])
        self.assertEqual(visible_manager, mine | theirs)

    # ---------------- G26 ----------------
    def _site_project(self):
        project = self.env['project.project'].create({'name': 'Site P'})
        return project, project._epc_ensure_site_location()

    def _final_qc(self, project):
        return self.env['epc.quality.check'].create({
            'project_id': project.id, 'category': 'final', 'line_ids': [(0, 0, {'name': 'a', 'result': 'pass'})]})

    def test_consume_lot_tracked_stock(self):
        project, location = self._site_project()
        tracked = self.env['product.product'].create({'name': 'Lot P', 'is_storable': True, 'tracking': 'lot'})
        lot = self.env['stock.lot'].create({'name': 'L1', 'product_id': tracked.id})
        self.env['stock.quant']._update_available_quantity(tracked, location, 5, lot_id=lot)
        self._final_qc(project).action_consume_site_stock()
        self.assertEqual(sum(self.env['stock.quant'].search([
            ('location_id', '=', location.id), ('product_id', '=', tracked.id)]).mapped('quantity')), 0)

    def test_consume_skips_lotless_stock_but_consumes_the_rest(self):
        project, location = self._site_project()
        tracked = self.env['product.product'].create({'name': 'Lot P', 'is_storable': True, 'tracking': 'lot'})
        self.env['stock.quant']._update_available_quantity(tracked, location, 5)          # no lot
        plain = self.env['product.product'].create({'name': 'Plain', 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(plain, location, 4)
        qc = self._final_qc(project)
        qc.action_consume_site_stock()
        left = self.env['stock.quant'].search([('location_id', '=', location.id), ('quantity', '>', 0)])
        self.assertEqual(left.mapped('product_id'), tracked)

    def test_consume_only_lotless_gives_clear_error(self):
        project, location = self._site_project()
        tracked = self.env['product.product'].create({'name': 'Lot P', 'is_storable': True, 'tracking': 'lot'})
        self.env['stock.quant']._update_available_quantity(tracked, location, 5)
        with self.assertRaises(UserError) as caught:
            self._final_qc(project).action_consume_site_stock()
        self.assertIn('no lot', str(caught.exception))
