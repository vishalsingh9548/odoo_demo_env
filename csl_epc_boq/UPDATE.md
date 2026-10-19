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

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Quotation checks (C12):** a quotation needs an approved, non-superseded BOQ with at least one line. Optional switch **Strict BOQ Check**: every line needs a product (service categories excepted) and a unit cost, or the new **Zero Cost Is Correct** tick on the line.
- **Quotation lifecycle (C13):**
  - Cancelling the quotation clears the link so a new quotation can be created.
  - **Refresh Quotation from BOQ** (while the quotation is still a draft).
  - **Revise BOQ** (managers): makes revision N+1 as an editable copy with its lines, marks the old one **Superseded** (no quotation can be created from it).
  - New fields: Revision, Revision Of, Superseded, Quotation Status.
- **EPC order flag (C11):** quotations created from a BOQ are ticked *Solar EPC Order*; a BOQ order always creates the project.
- **Lock (B7):** with *Lock Approved Documents* on, BOQ lines cannot be added/changed/removed once the BOQ is approved.
- **Stage check (B9):** *Create BOQ* on the feasibility study requires an approved study.
- **Visibility (F22):** Field Users see only BOQs (and their lines) they created.

### Why / Impact
Stops empty or incomplete quotations, lets a BOQ be corrected after a cancelled quotation, and keeps history of revisions. Strict line checks are off by default so existing BOQs keep working.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 3
- **Unit cost fills in automatically** from the product's cost when a product is picked on a BOQ line (also for lines created without a cost); a cost typed in by hand is kept.
- The **Unit Cost** and **Subtotal** columns are now always visible on the BOQ lines (no longer hidden optional columns). Existing lines with cost 0 are not changed — pick the product again or type the cost.
- **Quotation price stays as the BOQ price:** the quotation lines created from a BOQ now carry the product's unit of measure when the BOQ line has none, and are marked as manually priced, so changing the unit of measure or the quantity on the quotation no longer resets the price to the product's list price. (Quotations created before this fix keep the price they have; recreate them or retype the price.)
