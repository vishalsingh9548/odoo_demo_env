from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProjectExpense(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # An employee without a user, so the current user can approve their expenses.
        cls.employee = cls.env["hr.employee"].create({"name": "Site Crew"})
        cls.project_a = cls.env["project.project"].create({"name": "Job A"})
        cls.project_b = cls.env["project.project"].create({"name": "Job B"})
        for project in cls.project_a | cls.project_b:
            if not project.account_id:
                project._create_analytic_account()
        cls.task_a = cls.env["project.task"].create({"name": "Span 1", "project_id": cls.project_a.id})
        cls.category = cls.env["product.product"].create({
            "name": "Site travel", "type": "service", "can_be_expensed": True,
            "standard_price": 0.0, "expense_policy": "no", "supplier_taxes_id": [(6, 0, [])],
        })

    def _expense(self, **vals):
        return self.env["hr.expense"].create(dict({
            "name": "Cab to site", "employee_id": self.employee.id,
            "product_id": self.category.id, "total_amount_currency": 1200.0,
        }, **vals))

    def _account_key(self, project):
        return str(project.account_id.id)

    def test_01_project_sets_analytic(self):
        expense = self._expense(project_id=self.project_a.id)
        self.assertEqual(expense.analytic_distribution, {self._account_key(self.project_a): 100})
        # Saved in the database, not only in the cache.
        self.env.flush_all()
        self.env.cr.execute("SELECT analytic_distribution FROM hr_expense WHERE id = %s", (expense.id,))
        self.assertEqual(self.env.cr.fetchone()[0], {self._account_key(self.project_a): 100})

    def test_02_task_sets_project_and_analytic(self):
        expense = self._expense(task_id=self.task_a.id)
        self.assertEqual(expense.project_id, self.project_a)
        self.assertEqual(expense.analytic_distribution, {self._account_key(self.project_a): 100})

    def test_03_changing_project_follows_while_draft(self):
        expense = self._expense(project_id=self.project_a.id)
        expense.project_id = self.project_b
        self.assertEqual(expense.analytic_distribution, {self._account_key(self.project_b): 100})

    def test_04_project_without_account_gets_one(self):
        project = self.env["project.project"].create({"name": "Job without account"})
        project.account_id = False
        expense = self._expense(project_id=project.id)
        self.assertTrue(project.account_id, "An analytic account is created for the project.")
        self.assertEqual(expense.analytic_distribution, {self._account_key(project): 100})

    def test_05_task_must_belong_to_project(self):
        with self.assertRaises(ValidationError):
            self._expense(project_id=self.project_b.id, task_id=self.task_a.id)

    def test_06_counts_and_buttons(self):
        self._expense(task_id=self.task_a.id)
        self._expense(project_id=self.project_a.id)
        self.assertEqual(self.project_a.drone_expense_count, 2)
        self.assertEqual(self.task_a.drone_expense_count, 1)
        action = self.task_a.action_view_drone_expenses()
        self.assertEqual(action["context"]["default_task_id"], self.task_a.id)
        self.assertEqual(action["context"]["default_project_id"], self.project_a.id)
        action = self.project_a.action_view_drone_expenses()
        self.assertEqual(action["domain"], [("project_id", "=", self.project_a.id)])
        self.assertEqual(action["views"][0][1], "list", "The button opens on the list view.")

    def test_07_new_from_task_button_is_linked(self):
        context = self.task_a.action_view_drone_expenses()["context"]
        with Form(self.env["hr.expense"].with_context(**context)) as form:
            form.name = "Diesel"
            form.employee_id = self.employee
            form.product_id = self.category
            form.total_amount_currency = 500.0
        expense = form.save()
        self.assertEqual(expense.task_id, self.task_a)
        self.assertEqual(expense.project_id, self.project_a)
        self.assertEqual(expense.analytic_distribution, {self._account_key(self.project_a): 100})

    def test_08_profitability_sees_project_expense(self):
        expense = self._expense(project_id=self.project_a.id)
        sheet = expense._create_sheets_from_expense()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        self.assertEqual(sheet.state, "approve")
        sheet.action_sheet_move_post()
        self.assertEqual(sheet.state, "post")
        costs = self.project_a._get_profitability_items(False)["costs"]["data"]
        expenses = [d for d in costs if d["id"] == "expenses"]
        self.assertTrue(expenses)
        self.assertAlmostEqual(expenses[0]["billed"], -1200.0)

    def test_09_new_expense_buttons(self):
        for record, expected in ((self.task_a, (self.task_a, self.project_a)),
                                 (self.project_a, (self.env["project.task"], self.project_a))):
            action = record.action_new_drone_expense()
            self.assertEqual(action["res_model"], "hr.expense")
            self.assertEqual(action["views"], [(False, "form")])
            with Form(self.env["hr.expense"].with_context(**action["context"])) as form:
                form.name = "Toll"
                form.employee_id = self.employee
                form.product_id = self.category
                form.total_amount_currency = 300.0
            expense = form.save()
            self.assertEqual((expense.task_id, expense.project_id), expected)
            self.assertEqual(expense.analytic_distribution, {self._account_key(self.project_a): 100})

    def test_10_only_drone_users_see_it(self):
        drone_group = self.env.ref("drone_sales_crm.group_drone_user")
        base_groups = (self.env.ref("base.group_user") | self.env.ref("project.group_project_user")
                       | self.env.ref("hr_expense.group_hr_expense_user"))
        plain = self.env["res.users"].create({
            "name": "Plain user", "login": "plain_expense_user", "groups_id": [(6, 0, base_groups.ids)]})
        drone = self.env["res.users"].create({
            "name": "Drone user", "login": "drone_expense_user",
            "groups_id": [(6, 0, (base_groups | drone_group).ids)]})
        for user, visible in ((plain, False), (drone, True)):
            expense_form = self.env["hr.expense"].with_user(user).get_views([(False, "form")])["views"]["form"]["arch"]
            project_form = self.env["project.project"].with_user(user).get_views([(False, "form")])["views"]["form"]["arch"]
            task_form = self.env["project.task"].with_user(user).get_views([(False, "form")])["views"]["form"]["arch"]
            self.assertEqual('name="project_id"' in expense_form, visible)
            self.assertEqual("action_new_drone_expense" in project_form, visible)
            self.assertEqual("action_view_drone_expenses" in project_form, visible)
            self.assertEqual("action_new_drone_expense" in task_form, visible)
