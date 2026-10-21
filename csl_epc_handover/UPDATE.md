# UPDATE — csl_epc_handover (Handover & Closure)

> Part of the Solar EPC split. Stage 14. Own app icon: **Handover & Closure**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Handover** records (`epc.handover`, chatter + activities + approval workflow): project, customer, closure date, uploads for as-built drawing, test reports, O&M manual and warranty certificate, customer training done/date, and a project closure report, used to formally close an installation. Sequence `HO/<year>/00001`.
- Opened from an approved Commissioning record with *Proceed to Handover* (that button lives in `csl_epc_commissioning`).

## Dependencies
`csl_epc_core`.

## Views, menus and screens
- `views/epc_handover_views.xml` — list, form, search, window action.

- Top-level app **Handover & Closure** → submenu *Handover & Closure*.

## Data and security
Sequence `seq_epc_handover`.

`security/ir.model.access.csv` — Field User read/write/create; Project Manager full.

## What was moved / changed compared to the original single module
Moved unchanged from the old module: `epc_handover.py`, its view and sequence.

No code edits other than the group references (`csl_epc_core.group_epc_*`).

## Impact
- No functional change. It only depends on core, which is why Commissioning can depend on it (and not the other way round).

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- Optional switch **Handover Needs Documents**: the four documents and *Customer Training Done* must be present before a handover can be approved (OFF by default).
- Approval now goes through the shared approval checks (Project Manager only, correct state).
- **Visibility (F22):** Field Users see handovers they created; managers see all.
- **Not changed (decision):** approving a handover simply means *Completed* — no archiving, no project closure or stage change, and the Handover screen is unchanged.

### Impact
No behaviour change unless the switch is turned on.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 5 (2026-10-19) — Handover & Closure dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: document pack complete %, handovers missing documents, customer training done %, approval time, handovers closed this month.
- Charts: document checklist per project (green tick / red cross, click a row to open it), most often missing document, handovers per month, customer training, approval status.
- Table: handovers with missing documents.
- Documents are detected from the file-name fields (`as_built_drawing_filename`, `test_reports_filename`, `om_manual_filename`, `warranty_certificate_filename`).

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_handover`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 6 (2026-10-21) — "Customer training done" opens every handover
**Problem:** the tile shows a percentage of all handovers (for example 10 of 12 = 83.3%), but clicking it opened only the handovers with training done, so the list looked 100% complete and hid the pending ones.
**Fix:** the tile now opens the full list of handovers, so the ticked and the not-ticked *Customer Training Done* rows are both visible and add up to the percentage. The "Customer training" doughnut chart still opens just the Done or just the Pending group. File: `models/epc_stage_dashboard.py`. Restart the server (Python change only).

### Update 7 (2026-10-21) — Approval time can be checked in the list
The Handover list now has **Submitted**, **Approved** and **Days to Approve** columns (they can be hidden from the column picker). The footer under *Days to Approve* shows the **Average**, which is the "Approval time" tile. The tile now opens only the approved handovers that have both dates, so the rows and the average match the tile exactly (an approved handover missing either date is left out of both). Files: `models/epc_handover.py` (new computed, not stored, field `approval_days`), `views/epc_handover_views.xml`, `models/epc_stage_dashboard.py`. Upgrade: `-u csl_epc_handover`.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.
