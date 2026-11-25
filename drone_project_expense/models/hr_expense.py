from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Expense states in which the analytic distribution still follows the project.
# False: a new expense whose state is not computed yet.
EDITABLE_STATES = (False, "draft", "reported")


class HrExpense(models.Model):
    _inherit = "hr.expense"

    task_id = fields.Many2one(
        "project.task", string="Task", index="btree_not_null", tracking=True,
        help="Task the expense was for. Setting it also sets the project.",
    )
    project_id = fields.Many2one(
        "project.project", string="Project", index="btree_not_null", tracking=True,
        compute="_compute_project_id", store=True, readonly=False, precompute=True,
        help="The expense is charged to this project's analytic account automatically.",
    )

    @api.depends("task_id")
    def _compute_project_id(self):
        for expense in self:
            if expense.task_id:
                expense.project_id = expense.task_id.project_id

    @api.depends("product_id", "account_id", "employee_id", "project_id")
    def _compute_analytic_distribution(self):
        super()._compute_analytic_distribution()
        for expense in self:
            if expense.project_id and expense.state in EDITABLE_STATES:
                distribution = expense.project_id._get_analytic_distribution()
                if distribution:
                    expense.analytic_distribution = distribution

    @api.constrains("task_id", "project_id")
    def _check_task_project(self):
        for expense in self:
            if expense.task_id and expense.task_id.project_id != expense.project_id:
                raise ValidationError(_(
                    "Task %(task)s belongs to project %(task_project)s, not %(project)s.",
                    task=expense.task_id.display_name,
                    task_project=expense.task_id.project_id.display_name,
                    project=expense.project_id.display_name))

    def _drone_project_from_vals(self, vals):
        if vals.get("task_id"):
            return self.env["project.task"].browse(vals["task_id"]).project_id
        if vals.get("project_id"):
            return self.env["project.project"].browse(vals["project_id"])
        return self.env["project.project"]

    def _drone_prepare_project_vals(self, vals):
        """Make sure the project has an analytic account and put the matching analytic
        distribution in vals, so it is saved even when the compute doesn't write it."""
        project = self._drone_project_from_vals(vals)
        if not project:
            return vals
        if not project.account_id:
            project.sudo()._create_analytic_account()
        if "analytic_distribution" not in vals:
            distribution = project._get_analytic_distribution()
            if distribution:
                vals = dict(vals, analytic_distribution=distribution)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._drone_prepare_project_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if not (vals.get("project_id") or vals.get("task_id")):
            return super().write(vals)
        editable = self.filtered(lambda e: e.state in EDITABLE_STATES)
        result = True
        if editable:
            result = super(HrExpense, editable).write(self._drone_prepare_project_vals(vals))
        if self - editable:
            # Submitted, approved or posted expenses keep their accounting.
            result = super(HrExpense, self - editable).write(vals) and result
        return result
