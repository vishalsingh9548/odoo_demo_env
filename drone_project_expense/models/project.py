from odoo import api, fields, models

# Refused expenses are not counted on projects and tasks.
COUNTED_STATES = ("draft", "reported", "submitted", "approved", "done")


def _expense_list_action(env, name, domain, context):
    """Expenses action that opens on the list view (the standard one opens on a graph)."""
    action = env["ir.actions.act_window"]._for_xml_id("hr_expense.hr_expense_actions_all")
    list_view = env.ref("hr_expense.hr_expense_view_expenses_analysis_tree")
    action.update({
        "name": name,
        "domain": domain,
        "context": context,
        "view_mode": "list,form,kanban,pivot,graph",
        "views": [(list_view.id, "list"), (False, "form"), (False, "kanban"),
                  (False, "pivot"), (False, "graph")],
    })
    action.pop("view_id", None)
    return action


def _new_expense_action(env, context):
    """Open a new expense form, already linked to the project / task."""
    return {
        "type": "ir.actions.act_window",
        "name": env._("New Expense"),
        "res_model": "hr.expense",
        "view_mode": "form",
        "views": [(False, "form")],
        "target": "current",
        "context": context,
    }


class ProjectProject(models.Model):
    _inherit = "project.project"

    drone_expense_ids = fields.One2many("hr.expense", "project_id", string="Expenses")
    drone_expense_count = fields.Integer(compute="_compute_drone_expense_count", string="Expenses")

    def _compute_drone_expense_count(self):
        counts = dict(self.env["hr.expense"]._read_group(
            [("project_id", "in", self.ids), ("state", "in", COUNTED_STATES)],
            ["project_id"], ["__count"],
        ))
        for project in self:
            project.drone_expense_count = counts.get(project, 0)

    def action_view_drone_expenses(self):
        self.ensure_one()
        return _expense_list_action(
            self.env, self.env._("Expenses"),
            [("project_id", "=", self.id)],
            {"default_project_id": self.id},
        )

    def action_new_drone_expense(self):
        self.ensure_one()
        return _new_expense_action(self.env, {"default_project_id": self.id})


class ProjectTask(models.Model):
    _inherit = "project.task"

    drone_expense_ids = fields.One2many("hr.expense", "task_id", string="Expenses")
    drone_expense_count = fields.Integer(compute="_compute_drone_expense_count", string="Expenses")

    @api.depends("drone_expense_ids.state")
    def _compute_drone_expense_count(self):
        counts = dict(self.env["hr.expense"]._read_group(
            [("task_id", "in", self.ids), ("state", "in", COUNTED_STATES)],
            ["task_id"], ["__count"],
        ))
        for task in self:
            task.drone_expense_count = counts.get(task, 0)

    def action_view_drone_expenses(self):
        self.ensure_one()
        return _expense_list_action(
            self.env, self.env._("Expenses"),
            [("task_id", "=", self.id)],
            {"default_task_id": self.id, "default_project_id": self.project_id.id},
        )

    def action_new_drone_expense(self):
        self.ensure_one()
        return _new_expense_action(
            self.env, {"default_task_id": self.id, "default_project_id": self.project_id.id})
