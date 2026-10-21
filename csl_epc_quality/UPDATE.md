# UPDATE — csl_epc_quality (Quality Checks, QC Checkpoints and DPR)

> Part of the Solar EPC split. Stages 10 and 12. Own app icon: **Quality Checks**. **This is custom code, not Odoo's built-in Quality app** — it is the same custom QC that existed in the old module.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Quality Checks** (`epc.quality.check` + lines `epc.quality.check.line`): two categories — *Incoming Material QC* (tied to a receipt) and *Final QC* (before handover). Lines are filled from the configurable checkpoints; the overall result is Pending / Pass / Fail. A passed Final QC can **consume the remaining material at the site** (moves stock to the *Installed / Consumed Material* location).
- **QC Checkpoints** (`epc.quality.checkpoint`): the checklist templates per category, editable under *Configuration → QC Checkpoints*, with starter data.
- **Receipt guard** (`stock.picking` extension): a project's incoming receipt cannot be validated until an Incoming Material QC has been logged against it and has passed. A *Log Quality Check* button on the receipt opens a pre-filled QC form.
- **Daily Progress Reports** (`epc.dpr`): per-project daily report (date, reported by, weather, manpower deployed, work progress summary, material received/consumed, equipment deployed, site photo, issues/risks, tomorrow's plan), with a *DPR* smart button on the project. *(DPR is not quality-related; it lives here because it is Stage-10 site-execution data with no better home. It can be split later.)*
- **Project**: *Daily Progress Reports* and *Quality Checks* smart buttons with counts.

## Dependencies
`csl_epc_core` (and through it `stock`, `hr_timesheet`, projects).

## Views, menus and screens
- `views/epc_quality_check_views.xml`, `views/epc_quality_checkpoint_views.xml`, `views/epc_dpr_views.xml`, `views/stock_picking_views.xml`, `views/project_project_views.xml`.

- Top-level app **Quality Checks** → *Quality Checks*.
- *Configuration → QC Checkpoints* (under the Solar Dashboard app, Administrator only).

## Data and security
Sequences `seq_epc_dpr` (`DPR/<year>/`), `seq_epc_quality_check` (`QC/<year>/`); starter QC checkpoints (`noupdate`); the stock location *Installed / Consumed Material* (`epc_location_consumed`).

`security/ir.model.access.csv` — DPR, quality check, lines: Field User read/write/create; Project Manager full. Checkpoints: Field User read only; Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_quality_check.py`, `epc_quality_checkpoint.py`, `epc_dpr.py`, `stock_picking.py`, their views, data files and sequences, plus the DPR / quality part of `project_project.py`.

**Why a separate module:** you asked for QA to stay as it is. The Commissioning module checks whether a Final QC passed, so the QC models must exist before Commissioning installs; keeping them inside the parent would have created a circular dependency.

**Edits while splitting:**
- The `epc_location_consumed` reference is now `csl_epc_quality.epc_location_consumed`.
- The receipt-blocking message now says "Open the Quality Checks app" (QC is no longer a submenu of Solar EPC).
- DPR/quality project counts have their own compute methods.

## Impact
- QC logic and the receipt guard behave exactly as before.
- **Installing this module changes how project receipts validate** (they require a passed Incoming QC) — same as the original module.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **A1 (bug):** "Not Applicable" lines are ignored when working out the result. Pass + N/A = Pass; only-N/A stays Pending.
- **A2 (fail path):**
  - A failed check sends a to-do to the project manager (or approvers) and writes a chatter note, once.
  - **Re-inspect** button on a failed check: creates a new check of the same kind/receipt carrying only the failed items, linked to the old one (*Re-inspection Of*).
  - Optional switch **Failed Items Need a Remark**.
- **A3 (receipt guard):** a project's incoming receipt validates only if the **newest** Incoming QC on it has passed (an older fail followed by a passing re-inspection is fine).
- **A4:** optional switch **Lock Finished Quality Checks** (only managers can change items of a Pass/Fail check).
- **A5:** Commissioning uses the **latest** Final QC (see Commissioning). Consuming site stock is refused while a newer Final QC has not passed.
- **G26 (Consume Site Stock):** rewritten so it no longer fails with "supply a Lot/Serial number":
  - consumes only free stock (not what is reserved for other transfers) and keeps the lot/serial and package of each quantity;
  - works per product: what can be consumed is consumed, anything else (no lot recorded, reserved elsewhere, fractional serial stock) is left at site and listed in the chatter;
  - if nothing can be consumed, a clear message names the product and the reason.
- **Visibility (F22):** Field Users see checks they created or inspected, and DPRs they created or reported.

### Why / Impact
Fixes the QC logic bug and gives a real path after a Fail. The receipt guard is stricter on one case: a receipt whose newest check is not Pass is blocked even if an older check passed.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

### Update 3 — every failed check is logged, with the reason
- New field **Reason for Failure** on the quality check. It appears (and is **required in the form**) whenever the overall result is Fail, and is tracked in the chatter.
- Every time a check fails, the chatter gets a message: *Quality check failed*, the failed items (with their remarks) and the reason. If no reason was given, the message says so, and the inspector gets a to-do "Write why quality check … failed". The project manager / approvers still get the to-do.
- A check that is fixed and then fails again is logged again.
- The notification now runs once after all changes of one save are written, and not while the check is being created (that caused the "a partner cannot follow twice the same object" error).

- **Chatter formatting fix:** the failed-check and consume messages (and the material-request over-BOQ warning) showed raw `<b>`/`<ul>` tags; they now render as proper bold text and lists.
- **Failed Incoming QC shown on the receipt and the purchase order:** when an Incoming Material check fails, the failure (check link, failed items, reason) is also written in the chatter of the receipt it was done against and of that receipt's purchase order (as an internal note, no emails), so warehouse and buyer see it.
- The "also write it elsewhere" step is now a hook (`_epc_failure_documents`) so other modules can add places; Commissioning uses it for Final QC.

### Update 5 (2026-10-19) — Quality dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: first-pass yield, failed this month, failures not yet re-inspected, days from fail to pass, site issues reported in daily progress reports (last 30 days).
- Charts: passed/failed per week (8 weeks), pass rate by stage, most failed checkpoints, workers on site per daily report, weather on site.
- Table: recent failures with the reason given and whether they were re-inspected.
- Daily progress reports live in this module, so their charts are here too.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_quality`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 6 (2026-10-19) — drill-down lists for the dashboard
**Problem:** clicking a dashboard tile or bar for most failed checkpoints opened a list showing only the record ID, because `epc.quality.check.line` had no list view of its own.
**Fix:** added list, form (read-only) and search views for `epc.quality.check.line` in `views/epc_dashboard_views.xml` (no new menu, nothing else changes). The list is read-only (no create/delete), can be grouped, and shows the useful columns.
**Upgrade:** `-u csl_epc_quality`.

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 7 (2026-10-19) — Daily Progress Reports can be created from the project
**Problem:** there was no way to write the first Daily Progress Report. The *Daily Progress Reports* smart button on the Project form was hidden while the project had none, and the Quality app had no menu for them, so managers could not fill them in (the dashboard's "Site issues reported" and "Workers on site" read from them).
**Fix:** the *Daily Progress Reports* and *Quality Checks* smart buttons on the Project form are now always visible (showing 0 until there are records); clicking opens the list with the project already filled in for a new report. A **Daily Progress Reports** menu was also added under the Quality app. Files: `views/project_project_views.xml`, `views/epc_menus.xml`. Upgrade: `-u csl_epc_quality`.

### Update 8 (2026-10-19) — workers on site chart totals per day
The *Workers on site* chart on the Quality dashboard plotted one dot per daily report, so two reports on the same day (different projects) showed as two separate, lower dots with the same date. It now adds up the workers of all reports on a day, over the last 14 days that have reports, and clicking a point opens that day's reports. File: `models/epc_stage_dashboard.py`. Restart the server (Python change) — no module upgrade needed.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.

### Update 11 (2026-10-21) — "First-pass yield" tile now opens all first inspections
**Problem:** the tile showed 69.2% (45 of 65 first inspections passed) but clicking it opened only the 45 passed checks, so the list looked like 100% pass and did not explain the figure.
**Fix:** the tile now opens every first inspection (passed and failed, 65 records), the same set the percentage is calculated over. Group by *Overall Result* to see the 45 / 20 split. File: `models/epc_stage_dashboard.py`. Restart the server (Python change) — no module upgrade needed.

### Update 12 (2026-10-21) — "Days from fail to pass" can now be checked in the list
**Problem:** the tile showed 2.2 d, but the list it opened gave no way to see where that came from.
**Fix:** the Quality Checks list now has three columns — *Re-inspection of* (the failed check), *Failed On* (its date) and *Days After Fail* — with an **Average** at the foot that equals the tile (the dashboard uses the same rule: re-inspection date minus failed-check date, for passed re-inspections). New non-stored fields `previous_check_date` and `days_after_fail` in `models/epc_quality_check.py`; list in `views/epc_quality_check_views.xml`. Upgrade: `-u csl_epc_quality`.

### Update 13 (2026-10-21) — weekly chart shows the whole week
The *Passed and failed, weekly* chart labelled each bar with the Monday the week starts on (e.g. "31 Aug"), so checks dated 5–6 Sep looked out of place under it. Bars are now labelled with the full range ("31 Aug – 6 Sep"), the axis heading reads "Week (Monday to Sunday)", and the list that opens shows the same range in its title. Counts are unchanged. File: `models/epc_stage_dashboard.py`. Restart the server (Python change) — no module upgrade needed.
