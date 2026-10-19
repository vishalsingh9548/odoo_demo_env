# UPDATE — csl_solar_epc (Solar Dashboard — the parent module)

> Part of the Solar EPC split. The module you install. Its displayed name is **Solar Dashboard** (technical name still `csl_solar_epc`). Installing it installs all nine sub-modules.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
The parent now keeps only what spans every stage:
- **Dashboard** (`epc.dashboard` + the OWL screen in `static/`): live KPIs, portfolio phase, pipeline activity, AMC health, procurement status, upcoming services — each click-through.
- **Reporting**: Procurement, Inventory, DPR, Quality, Billing & Collection and O&M/AMC PDF reports, and *Download Today's Report* button on the project (daily progress PDF from timesheets).
- **Demo data** (`demo/epc_demo.xml`): one lead taken all the way from survey to AMC, so the app can be explored without entering data.

## Dependencies
`csl_epc_core`, `csl_epc_site_survey`, `csl_epc_feasibility`, `csl_epc_boq`, `csl_epc_material_request`, `csl_epc_quality`, `csl_epc_handover`, `csl_epc_commissioning`, `csl_epc_amc`.

## Views, menus and screens
- `views/project_project_views.xml` — the *Download Today's Report* button.
- `views/epc_reports_board.xml` — report actions/templates and the dashboard client action.

- Root menu **Solar Dashboard** (defined in core) with: *Dashboard*, *Reporting* (6 reports), and *Configuration*.
- Each stage's own app icon comes from its sub-module.

## Data and security
No data other than demo.

No access rules of its own (each module protects its models).

## What was moved / changed compared to the original single module
Remains here: `models/epc_dashboard.py`, a small `project_project.py` (print today's DPR), dashboard assets, reports board, menus, demo data, README/LOG/DEMOVALUES docs. Everything else was moved out into the sub-modules (see their UPDATE.md files).

**Edits made to what stayed here:**
- `__manifest__.py`: name changed to **Solar Dashboard**; `depends` is now the nine sub-modules only; `data` shrank to three view files; demo and assets kept.
- `epc_menus.xml`: only Dashboard and Reporting remain, now parented to `csl_epc_core.menu_epc_root`.
- `epc_dashboard.py`: group check now uses `csl_epc_core.group_epc_user`.
- `epc_demo.xml`: external IDs now carry the module prefix for records that moved (`csl_epc_amc.epc_helpdesk_team`, `csl_epc_quality...`).

## Impact
- Home screen now shows **one icon per stage** (Site Surveys, Feasibility, BOQ & Costing, Material Requests, Quality Checks, Commissioning, Handover & Closure, AMC Contracts) plus **Solar Dashboard**.
- Installing the parent installs the whole stack; individual stages can be installed alone only if their dependencies allow it (see each module's dependencies).

## Overall module map

```
csl_epc_core ─┬─ csl_epc_site_survey ─ csl_epc_feasibility ─ csl_epc_boq ─ csl_epc_material_request
              ├─ csl_epc_quality ───────┐
              ├─ csl_epc_handover ──────┴─ csl_epc_commissioning
              └─ csl_epc_amc
csl_solar_epc (Solar Dashboard) depends on all of the above
```

## Testing that was done
- Fresh database install of `csl_solar_epc` with demo data: all ten modules installed, no errors.
- Every list/form view of the EPC models and of the extended standard models (CRM lead, project, sale order, purchase order, stock picking, helpdesk ticket, task) loaded.
- Flow checked on demo data: lead → survey → feasibility → BOQ → project (BOQ attached on creation) → material request → commissioning action; dashboard returns data for the admin user.
- After the home-screen icon change the modules were upgraded on a database with no errors.

## Known environment note (not caused by this change)
If a database's admin time zone is saved as `Asia/Calcutta`, PostgreSQL here does not recognise that old name and the CRM pipeline fails. Set the time zone to `Asia/Kolkata` right after first login, before installing apps.

## Git note
The repo root is `odoo_demo_env/`. Stage the whole set with:
`git add -A csl_solar_epc csl_epc_*` from that folder; running `git add .` inside `csl_solar_epc/` misses the sibling modules.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.
