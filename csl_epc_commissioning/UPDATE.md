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

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **A5:** *Needs Final QC*, *Submit* and *Consume Site Stock* use the **latest** Final QC of the project, which must be Pass.
- **E19 (all optional, OFF by default):** switches for *Testing Done*, *Customer Walkthrough*, *Verified Generation* (before submit) and *Customer Approved*, *Certificate Uploaded* (before approve), and **One Commissioning per Project** (a rejected one does not count).
- **Notes on approval (always):** a chatter note if material is still at site or punch items are open.
- **Punch list (new):** *Punch List* tab with snags (what, who, closed); open items are counted.
- **B9:** *Proceed to Handover* needs an approved commissioning.
- **Handover link:** with the switch **Handover Needs Approved Commissioning** on, a handover cannot be approved before commissioning is.
- **Visibility (F22):** Field Users see commissioning records they created; managers see all.
- Lookups that must see other users' records (Final QC, handover) run with elevated rights so Field Users are not wrongly blocked.

### Impact
Only the "latest Final QC" rule changes behaviour by default (an old pass no longer counts after a newer fail).

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 3
- **Commissioning smart button** on the Project form (next to Sales Order / Quality Checks / Material Requests): shows how many commissioning records the project has and opens them (straight into the record when there is one). Hidden while there are none.
- **Handover smart button** on the Commissioning form: shows the project's handover count and opens it (straight into the record when there is one). Hidden until a handover exists; *Proceed to Handover* is still the button that creates it.
- **Failed Final QC shown on the Commissioning record:** when a Final QC of the project fails, the failure (check link, failed items, reason) is also written in the chatter of the project's commissioning record(s) as an internal note. (`models/epc_quality_check.py`, hooks into the quality module's `_epc_failure_documents`.)

### Update 5 (2026-10-19) — Commissioning dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: awaiting customer approval, open punch items (and how many are over 14 days old, `PUNCH_OLD_DAYS`), commissioning-to-handover days, verified generation, certificates uploaded.
- Charts: sign-off steps funnel, verified generation by project, open punch items by owner, punch item ageing, commissionings per month.
- Table: commissionings not signed off yet, showing which step each one is waiting on.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_commissioning`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 6 (2026-10-19) — drill-down lists for the dashboard
**Problem:** clicking a dashboard tile or bar for open punch items by owner and age opened a list showing only the record ID, because `epc.commissioning.punch` had no list view of its own.
**Fix:** added list, form (read-only) and search views for `epc.commissioning.punch` in `views/epc_dashboard_views.xml` (no new menu, nothing else changes). The list is read-only (no create/delete), can be grouped, and shows the useful columns.
**Upgrade:** `-u csl_epc_commissioning`.

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.

### Update 11 (2026-10-21) — lists behind the "Commissioning to handover" and "Verified generation" tiles
**Problem:** the *Commissioning to handover* tile (average days) opened a Handover list that showed neither the commissioning date nor the number of days, only the approval turnaround, so the figure could not be checked. The *Verified generation* tile opened a Commissioning list with no generation column.
**Fix:**
- The Handover list now also shows **Commissioned On** and **Days After Commissioning** (closure date minus the project's commissioning date, the same rule as the tile), with an **Average** at the foot equal to the tile. New non-stored fields on `epc.handover` in `models/epc_handover.py`; list added in `views/epc_commissioning_views.xml`.
- The Commissioning list now has a **Verified Generation (kWh)** column with a **Total** at the foot equal to the tile.
Upgrade: `-u csl_epc_commissioning`.
