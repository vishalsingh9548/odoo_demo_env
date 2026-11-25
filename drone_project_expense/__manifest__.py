{
    "name": "Drone - Project & Task Expenses",
    "summary": "Pick the project or task on an expense: the analytic account is set automatically; Expenses buttons on projects and tasks",
    "description": """
Record expenses against a job without touching analytic accounts:

* Project and Task fields on expenses. Choosing a task sets its project; choosing a project sets
  the expense's analytic distribution to 100% of that project's analytic account (created if
  the project has none yet)
* Only expenses not yet submitted follow the project; submitted, approved and posted expenses
  keep their accounting
* "Expenses" smart buttons on projects and tasks: they list the linked expenses, and new
  expenses created from there are already linked
* Existing expenses whose analytic account belongs to a single project are linked to it on install
* Visible only to members of the Drone User group (drone_sales_crm)
""",
    "version": "18.0.1.2.0",
    "category": "Human Resources/Expenses",
    "author": "Abas",
    "license": "LGPL-3",
    "depends": [
        "drone_sales_crm",
        "hr_expense",
        "project",
        "project_hr_expense",
    ],
    "data": [
        "views/hr_expense_views.xml",
        "views/project_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
