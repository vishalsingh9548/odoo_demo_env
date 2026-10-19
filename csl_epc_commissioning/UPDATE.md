# UPDATE — csl_epc_commissioning (Commissioning)

> Part of the Solar EPC split. Stage 13. Own app icon: **Commissioning**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Commissioning** records (`epc.commissioning`, approval workflow): project, customer, commissioning date, checklist, system testing done, generation verification (kWh), customer walkthrough and approval, and the commissioning certificate upload. Sequence `COM/<year>/00001`. **Gate:** it cannot be submitted for approval until the project has a passed Final QC. Helper buttons: *Log Quality Check* (opens a pre-filled Final QC), *Consume Site Stock* (once Final QC has passed), and *Proceed to Handover* once approved.
- **Commissioning certificate** (PDF report, `Print Certificate`).
- **Project**: *Proceed to Commissioning* header button (shown only when every task on the project is done/cancelled and no commissioning exists), plus the commissioning count and *all tasks done* flag.

## Dependencies
`csl_epc_quality`, `csl_epc_handover`.

## Views, menus and screens
- `views/epc_commissioning_views.xml` — list, form, search, window action.
- `views/project_project_views.xml` — the *Proceed to Commissioning* button.
- `report/epc_commissioning_report.xml` — certificate template and report action.

- Top-level app **Commissioning** → submenu *Commissioning*.

## Data and security
Sequence `seq_epc_commissioning`.

`security/ir.model.access.csv` — Field User read/write/create; Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_commissioning.py`, its view, sequence and report, and the commissioning part of `project_project.py` and its view.

**Edits while splitting:** report names are now `csl_epc_commissioning.epc_commissioning_certificate_template`; `commissioning_count` and `epc_all_tasks_done` moved onto the project from this module (they are only used here).

## Impact
- No functional change. Depends on Quality (reads Final QC) and Handover (creates the next record).

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.
