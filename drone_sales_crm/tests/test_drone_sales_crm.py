from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDroneSalesCrm(TransactionCase):

    # 12 spans, mixed river / farmland, 300-900 m: 7.085 km in total
    SPANS = [
        (1, 620.0, "farmland"), (2, 845.0, "river"), (3, 410.0, "farmland"),
        (4, 380.0, "farmland"), (5, 900.0, "river"), (6, 515.0, "farmland"),
        (7, 300.0, "farmland"), (8, 760.0, "river"), (9, 450.0, "farmland"),
        (10, 690.0, "farmland"), (11, 880.0, "river"), (12, 335.0, "farmland"),
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "KPIL"})
        cls.template_project = cls.env.ref("drone_sales_crm.project_stringing_job_template")
        cls.km_product = cls.env.ref("drone_sales_crm.product_drone_stringing_km")
        cls.mob_product = cls.env.ref("drone_sales_crm.product_drone_mobilisation")
        cls.demob_product = cls.env.ref("drone_sales_crm.product_drone_demobilisation")
        cls.quotation_template = cls.env.ref("drone_sales_crm.sale_order_template_drone_stringing")
        cls.lead = cls.env["crm.lead"].create({
            "name": "KPIL - 765kV Nimrana-Bareilly",
            "type": "opportunity",
            "partner_id": cls.partner.id,
            "line_name": "765kV Nimrana-Bareilly",
            "voltage_kv": 765,
            "survey_span_ids": [
                (0, 0, {"name": str(no), "tower_from": "T%s" % no, "tower_to": "T%s" % (no + 1),
                        "length_m": length, "crossing_type": crossing})
                for no, length, crossing in cls.SPANS
            ],
        })

    def _create_order(self, qty=8.0):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "opportunity_id": self.lead.id,
            "order_line": [(0, 0, {
                "product_id": self.km_product.id, "product_uom_qty": qty, "price_unit": 100000.0,
            })],
        })
        order._onchange_opportunity_id_drone()
        return order

    def test_01_span_totals(self):
        self.assertEqual(self.lead.span_count, 12)
        self.assertAlmostEqual(self.lead.total_km, 7.085, places=3)

    def test_02_confirm_creates_span_tasks_once(self):
        order = self._create_order()
        order.action_confirm()
        project = order._drone_get_job_project()
        self.assertTrue(project, "Confirming the order should create the job project.")
        spans = self.env["project.task"].search([("project_id", "=", project.id), ("is_span", "=", True)])
        self.assertEqual(len(spans), 12)
        order._drone_create_span_tasks()
        spans_again = self.env["project.task"].search([("project_id", "=", project.id), ("is_span", "=", True)])
        self.assertEqual(len(spans_again), 12, "Span tasks must not be duplicated.")

    def test_03_certification_sets_delivered_km(self):
        order = self._create_order(qty=8.0)
        order.action_confirm()
        cert = self.env["drone.certification"].create({
            "sale_order_id": order.id, "certified_km": 5.0,
        })
        cert.action_confirm()
        line = order.order_line.filtered("is_stringing_km")
        self.assertEqual(line.qty_delivered, 5.0)
        over = self.env["drone.certification"].create({
            "sale_order_id": order.id, "certified_km": 4.0,
        })
        with self.assertRaises(UserError):
            over.action_confirm()

    def test_04_manual_delivered_edit_blocked(self):
        order = self._create_order()
        order.action_confirm()
        line = order.order_line.filtered("is_stringing_km")
        with self.assertRaises(UserError):
            line.write({"qty_delivered": 3.0})

    def test_05_invoice_marks_certification_invoiced(self):
        order = self._create_order(qty=8.0)
        order.action_confirm()
        cert = self.env["drone.certification"].create({
            "sale_order_id": order.id, "certified_km": 8.0,
        })
        cert.action_confirm()
        try:
            invoice = order._create_invoices()
        except UserError as error:
            self.skipTest("No accounting setup in this database: %s" % error)
        invoice.action_post()
        self.assertEqual(cert.state, "invoiced")
        self.assertEqual(cert.invoice_id, invoice)

    # --- Data created on install -------------------------------------------------------

    def _job_projects(self, order):
        """Every project generated for the order, archived ones included."""
        return self.env["project.project"].with_context(active_test=False).search(
            [("reinvoiced_sale_order_id", "=", order.id)])

    def test_06_products_installed(self):
        uom_km = self.env.ref("uom.product_uom_km")
        km = self.km_product
        self.assertEqual(km.default_code, "DS-KM")
        self.assertEqual(km.type, "service")
        self.assertEqual(km.invoice_policy, "delivery")
        self.assertEqual(km.service_type, "manual")
        self.assertEqual(km.uom_id, uom_km)
        self.assertEqual(km.uom_po_id, uom_km)
        self.assertEqual(km.service_tracking, "project_only")
        self.assertEqual(km.project_template_id, self.template_project)
        self.assertTrue(km.is_stringing_km)
        self.assertFalse(km.purchase_ok)
        for product in self.mob_product | self.demob_product:
            self.assertEqual(product.invoice_policy, "order")
            self.assertEqual(product.service_tracking, "no")
            self.assertEqual(product.uom_id, self.env.ref("uom.product_uom_unit"))
        self.assertEqual(
            self.template_project.type_ids.sorted("sequence").mapped("name"),
            ["Planned", "In progress", "Strung", "Certified"],
        )
        self.assertTrue(self.template_project.active)

    def test_07_quotation_template_lines(self):
        # The template field is only on the form for "Quotation Templates" users.
        self.env.user.groups_id |= self.env.ref("sale_management.group_sale_order_template")
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            order_form.sale_order_template_id = self.quotation_template
        order = order_form.save()
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(order.order_line.product_id, self.km_product | self.mob_product)
        self.assertEqual(order.sale_order_option_ids.product_id, self.demob_product)
        self.assertIn("certified by the client", str(order.note))

    def test_08_confirm_creates_named_project(self):
        order = self._create_order()
        order.action_confirm()
        projects = self._job_projects(order)
        self.assertEqual(len(projects), 1)
        self.assertEqual(
            projects.name, "%s - KPIL - 765kV Nimrana-Bareilly" % order.name)
        self.assertEqual(projects.partner_id, self.partner)
        self.assertEqual(order.order_line.filtered("is_stringing_km").project_id, projects)
        self.assertEqual(
            projects.type_ids.sorted("sequence").mapped("name"),
            ["Planned", "In progress", "Strung", "Certified"],
        )
        self.assertEqual(len(projects.task_ids.filtered("is_span")), 12)

    def test_09_reconfirm_keeps_one_project(self):
        order = self._create_order()
        order.action_confirm()
        project = self._job_projects(order)
        order._action_cancel()
        order.action_draft()
        order.action_confirm()
        self.assertEqual(len(project), 1)
        self.assertEqual(self._job_projects(order), project, "Re-confirming must not add a project.")
        self.assertEqual(order.order_line.filtered("is_stringing_km").project_id, project)
        self.assertEqual(len(project.task_ids.filtered("is_span")), 12)

    # --- Spec features added in 18.0.1.2.0 ---------------------------------------------

    def test_10_quotation_from_lead_copies_job(self):
        context = self.lead.action_new_quotation()["context"]
        order = self.env["sale.order"].with_context(**context).create({})
        self.assertEqual(order.opportunity_id, self.lead)
        self.assertEqual(order.line_name, "765kV Nimrana-Bareilly")
        self.assertEqual(order.voltage_kv, 765)
        self.assertEqual(order.span_count, 12)
        self.assertAlmostEqual(order.total_km, 7.085, places=3)

    def test_11_span_task_name(self):
        order = self._create_order()
        order.action_confirm()
        task = order._drone_get_job_project().task_ids.filtered(
            lambda t: t.survey_span_id.name == "1")
        self.assertEqual(task.name, "Span 1: T1 – T2")

    def test_12_project_certification_button(self):
        order = self._create_order(qty=8.0)
        order.action_confirm()
        project = order._drone_get_job_project()
        self.env["drone.certification"].create({"sale_order_id": order.id, "certified_km": 2.0})
        self.assertEqual(project.drone_certification_count, 1)
        action = project.action_view_drone_certifications()
        self.assertEqual(action["domain"], [("project_id", "=", project.id)])

    def test_13_pdf_unit_km_and_terms(self):
        self.env.company.drone_quote_terms = "<p>Crossing permissions arranged by the client.</p>"
        order = self._create_order(qty=8.0)
        # Even if the line's unit is changed, the PDF prints "km" for the per-km product.
        order.order_line.product_uom = self.env.ref("uom.product_uom_meter")
        html = str(self.env["ir.actions.report"]._render_qweb_html(
            "sale.action_report_saleorder", order.ids)[0])
        self.assertIn("Drone terms", html)
        self.assertIn("Crossing permissions arranged by the client.", html)
        self.assertIn(">km<", html)
        self.assertIn("Stringing job", html)

    def test_14_certified_km_invoiced_to_the_metre(self):
        order = self._create_order(qty=8.0)
        order.action_confirm()
        cert = self.env["drone.certification"].create({"sale_order_id": order.id, "certified_km": 2.255})
        cert.action_confirm()
        line = order.order_line.filtered("is_stringing_km")
        self.assertEqual(line.qty_delivered, 2.255)
        self.assertEqual(line.qty_to_invoice, 2.255)
        try:
            invoice = order._create_invoices()
        except UserError as error:
            self.skipTest("No accounting setup in this database: %s" % error)
        km_line = invoice.invoice_line_ids.filtered(lambda l: l.product_id == self.km_product)
        self.assertEqual(km_line.quantity, 2.255, "2.255 km must not be rounded to 2.26 km.")
        self.assertAlmostEqual(km_line.price_subtotal, 2.255 * 100000.0)

    def test_15_certification_pdf(self):
        order = self._create_order(qty=8.0)
        order.client_order_ref = "KPIL/PO/TEST"
        order.action_confirm()
        first = self.env["drone.certification"].create({"sale_order_id": order.id, "certified_km": 2.5})
        first.action_confirm()
        second = self.env["drone.certification"].create({
            "sale_order_id": order.id, "certified_km": 1.25, "client_engineer": "R. Sharma"})
        second.action_confirm()
        values = second._drone_report_values()
        self.assertAlmostEqual(values["previous_km"], 2.5)
        self.assertAlmostEqual(values["cumulative_km"], 3.75)
        self.assertAlmostEqual(values["balance_km"], 4.25)
        self.assertAlmostEqual(values["amount"], 125000.0)
        html = str(self.env["ir.actions.report"]._render_qweb_html(
            "drone_sales_crm.action_report_drone_certification", second.ids)[0])
        for text in (second.name, "KPIL/PO/TEST", "R. Sharma", "765kV Nimrana-Bareilly",
                     "Certified by this certificate", "Certified by the client"):
            self.assertIn(text, html)
        # Without a document layout, Odoo first asks to configure one (standard behaviour).
        self.env.company.external_report_layout_id = self.env.ref("web.external_layout_standard")
        action = second.action_print_certification()
        self.assertEqual(action["report_name"], "drone_sales_crm.report_drone_certification")

    def test_16_non_drone_order_keeps_standard_project_name(self):
        service = self.env["product.product"].create({
            "name": "Site survey (non-drone)", "type": "service", "invoice_policy": "order",
            "service_tracking": "project_only", "list_price": 1000.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "line_name": "Some line",
            "order_line": [(0, 0, {"product_id": service.id, "product_uom_qty": 1})],
        })
        order.action_confirm()
        project = order.order_line.project_id
        self.assertTrue(project)
        self.assertNotIn(" - KPIL - Some line", project.name,
                         "Only drone stringing orders get the drone project name.")
