import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Link existing expenses to their project when their analytic distribution is 100% on
    an account used by exactly one project. Written in SQL so posted expenses keep their
    accounting untouched."""
    projects_by_account = {}
    for project in env["project.project"].with_context(active_test=False).search([("account_id", "!=", False)]):
        projects_by_account.setdefault(str(project.account_id.id), []).append(project.id)
    linked = 0
    for expense in env["hr.expense"].search([("project_id", "=", False), ("analytic_distribution", "!=", False)]):
        distribution = expense.analytic_distribution or {}
        if len(distribution) != 1:
            continue
        (account_key, percentage), = distribution.items()
        projects = projects_by_account.get(account_key, [])
        if float(percentage) == 100.0 and len(projects) == 1:
            env.cr.execute("UPDATE hr_expense SET project_id = %s WHERE id = %s", (projects[0], expense.id))
            linked += 1
    env["hr.expense"].invalidate_model(["project_id"])
    _logger.info("drone_project_expense: linked %s existing expenses to their project.", linked)
