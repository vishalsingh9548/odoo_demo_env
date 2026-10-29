# UPDATE — csl_epc_feasibility (Technical Feasibility)

> Part of the Solar EPC split. Pipeline stage 3. Own app icon: **Feasibility**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Technical Feasibility** studies (`epc.feasibility`): created from an approved Site Survey. Captures proposed capacity (kW), system type, module tilt angle and orientation, plant layout upload, annual generation estimate (kWh), performance ratio, financial benefits, feasibility report, and the final technical verdict (whether to proceed to costing). Approval workflow, chatter, sequence `TF/<year>/00001`.
- **On the Site Survey**: *Create Feasibility Study* button (shown once the survey is approved and has no study yet) and a *Feasibility Studies* smart button.
- **On the CRM lead**: Feasibility study link and count fields.

## Dependencies
`csl_epc_site_survey`.

## Views, menus and screens
- `views/epc_feasibility_views.xml` — list, form, search, window action.
- `views/epc_site_survey_views.xml` — extension of the Site Survey form (button + smart button).

- Top-level app **Feasibility** → submenu *Feasibility Studies*.

## Data and security
Sequence `seq_epc_feasibility`.

`security/ir.model.access.csv` — Field User read/write/create; Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_feasibility.py`, its views and sequence.

**Edits while splitting:**
- The Survey → Feasibility link (`feasibility_ids`, `feasibility_count`, `action_create_feasibility`, `action_view_feasibility`) and the two form buttons were lifted out of the Site Survey module into this one, as an extension of `epc.site.survey`. Otherwise Site Survey would have had to depend on a later stage.
- The Feasibility → BOQ link and buttons moved on to `csl_epc_boq` for the same reason.
- The lead's `feasibility_ids` / `feasibility_count` fields live here.

## Impact
- Behaviour is identical; the Feasibility icon only exists when this module is installed, and Site Survey works without it.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Stage check (B9):** a BOQ can only be created from an approved study.
- **Not feasible (B10):** *Mark Lead Lost* button; optional **Proceed Anyway** override with the *Stop Work on "Not Feasible"* switch (same behaviour as the survey).
- **Visibility (F22):** Field Users see studies they created or whose survey they are the engineer on; managers see all.

### Why / Impact
Same as Site Survey: server-side gating and a way to stop work on a not-feasible project. No change unless the switch is on.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 5 (2026-10-19) — Feasibility dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: capacity under study (kWp/MWp), average performance ratio vs the 80% target (`PR_TARGET` in the Python file), expected yearly generation, specific yield (kWh per kWp), survey to feasibility conversion.
- Charts: system type, proposal size bands, module orientation, capacity vs yearly generation (scatter, click a dot to open the proposal), performance-ratio spread.
- Table: best-yield proposals.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_feasibility`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.

### Update 11 (2026-10-21) — Feasibility list shows the figures the tiles add up
**Problem:** the *Capacity under study* tile (4.5 MWp over 19 proposals) opened a list that showed each proposed capacity but no total, so the relation to the tile was not visible. The *Expected generation* and *Avg performance ratio* tiles had no matching columns at all.
**Fix:** the Feasibility Studies list now has a **Total** under *Proposed Capacity (kW)* (equals the tile, in kW: 4.5 MWp = 4,500+ kW), a new **Annual Generation (kWh)** column with a **Total** (equals *Expected generation*) and a **Performance Ratio** column with an **Average** (equals *Avg performance ratio* when opened from that tile). File: `views/epc_feasibility_views.xml`. Upgrade: `-u csl_epc_feasibility`.

### Update 12 (2026-10-21) — Specific Yield per proposal
The Feasibility Studies list now has a **Specific Yield (kWh/kWp)** column (estimated annual generation ÷ proposed capacity) so each proposal can be compared with the dashboard's overall *Specific yield* tile (total generation ÷ total capacity). It has no footer on purpose: the tile is a ratio of the two totals, not an average of the rows. New non-stored field `specific_yield` in `models/epc_feasibility.py`; column in `views/epc_feasibility_views.xml`. Upgrade: `-u csl_epc_feasibility`.

### Update 13 (2026-10-21) — "Survey to feasibility" tile opens all surveys
**Problem:** the tile showed 61.3% (19 of 31 surveys studied) but opened only the 19 surveys that have a feasibility study, so the 12 behind the rest of the percentage were missing.
**Fix:** the tile now opens every site survey (31), and the Site Surveys list has a new **Feasibility Studies** column (how many studies were created from each survey; 0 = not studied yet). Surveys with a number above 0 are the 19 in the tile. Files: `models/epc_stage_dashboard.py`, `views/epc_site_survey_views.xml`. Upgrade: `-u csl_epc_feasibility`.

### Update 14 (2026-10-29) — CRM no longer fails for users without Solar EPC access
**Problem:** a user without any Solar EPC group (for example a plain Sales user) got an *Access Error* ("You are not allowed to access 'Solar Site Survey' (epc.site.survey) records") when opening CRM, because the Feasibility count and link added to the CRM lead was computed for every user and read a model they have no access to.
**Fix:** `feasibility_count` and `feasibility_ids` on `crm.lead` now carry `groups='csl_epc_core.group_epc_user'`, so they are not read for other users. File: `models/crm_lead.py`. Users with the Solar EPC *Field User* group (or higher) see no difference; everyone else can open CRM normally.
Upgrade: `-u csl_epc_feasibility`, then restart the server.
