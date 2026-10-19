# UPDATE — csl_epc_boq (BOQ & Costing)

> Part of the Solar EPC split. Pipeline stage 4. Own app icon: **BOQ & Costing**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Bill of Quantities** (`epc.boq`) with **BOQ lines** (`epc.boq.line`: category, product, description, quantity, UoM, unit cost, subtotal): costing sheet created from an approved Feasibility study. Shows total cost, margin % and total sell price, and takes capacity (kW) from the study. Approval workflow, sequence `BOQ/<year>/00001`.
- **Create Quotation**: generates a Sales Order from the BOQ and keeps the link (`sale_order_id`); *Quotation* smart button.
- **Sale Order**: *Source BOQ* field on the Solar EPC Terms tab.
- **Project**: Source BOQ, System Capacity (kW) and hidden budgeted cost / contract revenue pulled live from the BOQ; the project created from a confirmed order starts with its BOQ attached.
- **On Feasibility**: *Create BOQ* button and *BOQs* smart button. **On the CRM lead**: BOQ link and count.

## Dependencies
`csl_epc_feasibility`.

## Views, menus and screens
- `views/epc_boq_views.xml` — list, form (with lines), search, window action.
- `views/epc_feasibility_views.xml` — Create BOQ button and BOQs smart button on the Feasibility form.
- `views/sale_order_views.xml` — *Source BOQ* on the order.
- `views/project_project_views.xml` — BOQ fields in the project's Solar EPC group.

- Top-level app **BOQ & Costing** → submenu *BOQ & Costing*.

## Data and security
Sequence `seq_epc_boq`.

`security/ir.model.access.csv` — BOQ and BOQ line: Field User read/write/create (lines also delete); Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_boq.py`, its views and sequence, the `boq_id` field of the Sale Order, the BOQ fields of the Project and the BOQ links on the CRM lead.

**Edits while splitting:**
- `sale_order.py` here only adds `boq_id` and overrides the new core hook `_epc_project_vals()` to add `boq_id` to the project that is created on confirmation.
- The Feasibility → BOQ link (`boq_ids`, `boq_count`, `action_create_boq`, `action_view_boq`) lives here as an extension of `epc.feasibility`.
- Project BOQ fields and their view part were extracted from the old `project_project.py` / `project_project_views.xml`.

## Impact
- Quotation creation and project hand-off work exactly as before.
- Without this module installed, projects have no BOQ and Material Requests cannot pre-fill from a BOQ (Material Request depends on it).

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.
