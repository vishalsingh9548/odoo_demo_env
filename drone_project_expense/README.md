# Drone - Project & Task Expenses (`drone_project_expense`)

Record an expense against a job without touching analytic accounts.

## What it adds

| Feature | Where |
|---|---|
| **Project** and **Task** fields on the expense | Expense form (under Category), expense lists (optional column), expense report lines |
| Choosing a **task** sets its **project** | Automatic |
| Choosing a **project** sets the **Analytic Distribution** to 100 % of the project's analytic account | Automatic; the project gets an analytic account if it has none |
| **Expenses** smart button with count | Project form and task form |
| New expense from a button is already linked (task + project, or project) | Automatic |
| Search and group expenses by project / task | Expenses search |
| On install, existing expenses whose analytic distribution is 100 % on one project's account are linked to that project | Automatic, once |

The project's **Profitability** keeps working as in standard Odoo: it reads the analytic
account, which this module now fills in for you.

## Rules

* The task must belong to the selected project.
* Only expenses not yet submitted (To Report / To Submit) follow the project. Changing the
  project on a submitted, approved or posted expense does not change its accounting.
* The analytic distribution can still be edited by hand (e.g. to split a shared cost), as long
  as you don't change the project afterwards.

## How to use

* From a **project**: Expenses button > New.
* From a **task** (e.g. a span): Expenses button > New.
* From **Expenses**: New, then pick the Project (and optionally the Task).

## Tests

Run on a separate port so an open browser tab cannot keep the test server alive:

```bash
odoo-bin -c debian/demo_nov24.conf -d <test_db> -u drone_project_expense \
  --http-port 8099 --gevent-port 8098 --test-enable --test-tags /drone_project_expense --stop-after-init
```
