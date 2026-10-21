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

### Update 5 (2026-10-19) — BOQ & Costing dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: average cost per kW, average margin, lowest margin (and how many BOQs are under the 12% floor, `MARGIN_FLOOR` in the Python file), revised BOQs, quotation created rate.
- Charts: cost by category, margin by BOQ (red when under the floor), cost per kW by month, versions per BOQ.
- Table: BOQs needing a pricing review (margin under the floor or version 3 and above).
- Only the latest version of each BOQ is counted (superseded revisions are ignored), except the Versions chart which shows all.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_boq`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 6 (2026-10-19) — drill-down lists for the dashboard
**Problem:** clicking a dashboard tile or bar for cost by category opened a list showing only the record ID, because `epc.boq.line` had no list view of its own.
**Fix:** added list, form (read-only) and search views for `epc.boq.line` in `views/epc_dashboard_views.xml` (no new menu, nothing else changes). The list is read-only (no create/delete), can be grouped, and shows the useful columns.
**Upgrade:** `-u csl_epc_boq`.

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.

### Update 11 (2026-10-21) — BOQ list shows the figures behind the tiles
**Problem:** the *Avg cost per kW* tile opened a list with only the capacity; Total Cost and Total Sell Price were hidden by default and there was no margin or cost-per-kW column, so none of the BOQ tiles (cost per kW, average margin, lowest margin) could be checked.
**Fix:** the BOQs list now shows, by default, **System Capacity** (with a Total), **Total Cost** (Total), a new **Cost per kW** (total cost ÷ capacity, per BOQ), **Margin (%)** (Average) and **Total Sell Price** (Total). The tile's figure is the Total Cost footer divided by the System Capacity footer, so the two footers explain it. New non-stored field `cost_per_kw` in `models/epc_boq.py`; list in `views/epc_boq_views.xml` (the old "hidden for now" note was removed). Upgrade: `-u csl_epc_boq`.

### Update 12 (2026-10-21) — money totals now show in the BOQ list footer
The **Total Cost** and **Total Sell Price** footers showed "—" because Odoo only adds up money columns when the list also loads the currency. The BOQs list now carries the (hidden) Currency column, so both totals appear (all current BOQs are in one currency). File: `views/epc_boq_views.xml`. Upgrade: `-u csl_epc_boq`.

### Update 13 (2026-10-21) — "Quotation created" tile opens all approved BOQs
**Problem:** the tile showed 91.7% (11 of 12 approved BOQs have a quotation) but opened only the 11 with a quotation, so the one still missing could not be seen.
**Fix:** the tile now opens every approved current BOQ (12), the set the percentage is calculated over, and the BOQs list has a new **Quotation** column; the BOQ with no quotation yet is the one with an empty cell. Files: `models/epc_stage_dashboard.py`, `views/epc_boq_views.xml`. Upgrade: `-u csl_epc_boq`.

### Update 14 (2026-10-21) — BOQ list shows Version and Superseded
**Problem:** a bar of the *Versions per BOQ* chart (e.g. v1 = 17) opened the right records, but the list did not show which version each record is, nor whether it has been replaced by a newer one, so the bar could not be understood.
**Fix:** the BOQs list now has **Version** and **Superseded** columns. The chart counts every BOQ record, including older versions that were replaced (22 records: 17 at v1, 3 at v2, 2 at v3); *Superseded* = ticked marks those older copies. Files: `views/epc_boq_views.xml`. Upgrade: `-u csl_epc_boq`.

### Update 15 (2026-10-21) — "Older Versions" smart button on the BOQ form
A BOQ that was revised from an earlier one now has an **Older Versions** smart button at the top of its form (hidden on a first version). It shows how many earlier versions there are (the whole chain, e.g. a v3 shows 2) and opens them: straight to the record when there is just one, otherwise to a list showing each version, with the old copies marked *Superseded*. New fields/methods `older_version_count`, `_older_versions`, `action_view_older_versions` in `models/epc_boq.py`; button in `views/epc_boq_views.xml`. Upgrade: `-u csl_epc_boq`.

### Update 16 (2026-10-21) — Projects list shows the BOQ, capacity and contract value
The Projects list (also opened from the Solar Dashboard's *Contract Value*, *Active Projects* and *Completed Projects* tiles) now has **BOQ**, **System Capacity** and **Contract Value** columns, the last two with a **Total** at the foot. Contract Value is the sell price of the BOQ linked to the project. File: `views/project_project_views.xml`. Upgrade: `-u csl_epc_boq`.
