# UPDATE — csl_epc_site_survey (Site Survey)

> Part of the Solar EPC split. Pipeline stage 2. Own app icon: **Site Surveys**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Site Survey** records (`epc.site.survey`, with chatter and activities): linked to a CRM lead/opportunity and customer. Captures survey date, engineer, site address, roof/land type, available area (sq ft), sanctioned load, transformer and grid availability, shadow analysis, site photo, survey report, and the engineer's verdict on whether the site is feasible.
- Reference numbers from a sequence (`SS/<year>/00001`).
- Uses the shared approval workflow (submit → approve/reject; approval is for Project Managers).
- **On the CRM opportunity**: a *Schedule Site Survey* header button (opportunities only, Field User and above) and a *Surveys* smart button with the count.

## Dependencies
`csl_epc_core`.

## Views, menus and screens
- `views/epc_site_survey_views.xml` — list, form, search and window action.
- `views/crm_lead_views.xml` — the CRM button and smart button.

- Top-level app **Site Surveys** (icon, sequence 46) → submenu *Site Surveys*.

## Data and security
Sequence `seq_epc_site_survey`.

`security/ir.model.access.csv` — Field User: read/write/create; Project Manager: full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_site_survey.py`, its views and sequence, and the Site Survey part of `crm_lead.py` / `crm_lead_views.xml`.

**Edit while splitting:** the *Create Feasibility Study* button, the *Feasibility* smart button, the `feasibility_ids` link and `action_create_feasibility` were removed from this module (they point at a later stage) and now live in `csl_epc_feasibility` as an extension of `epc.site.survey`.

## Impact
- Survey screens look and behave exactly as before.
- Site Surveys is now a separate top-level app icon instead of a submenu of Solar EPC.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Stage check (B9):** the next stage can only be started from an approved survey (enforced in Python, not just by button visibility).
- **Not feasible (B10):** *Mark Lead Lost* button on the survey (opens the standard CRM Lost wizard). Optional switch *Stop Work on "Not Feasible"*: a survey with verdict "no" cannot lead to a Feasibility Study unless a manager ticks **Proceed Anyway**.
- **Visibility (F22):** Field Users see only surveys they created or are the engineer on; Project Managers/Administrators see all (`security/epc_rules.xml`).

### Why / Impact
Prevents skipping approval through direct calls and gives a clean way to close a lead that is not feasible. With the switch off, the "no" verdict behaves as before.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 5 (2026-10-19) — Site Survey dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: surveys this month (vs last month), feasible rate, average usable area, sanctioned load surveyed, surveys waiting for a decision (with how many wait over 5 days).
- Charts: surveys per month, outcome of surveys, site type mix, grid and transformer readiness, surveys per engineer.
- Table: surveys waiting for approval (oldest first), with days waiting and an Overdue pill after 5 days.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_survey`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 7 (2026-10-19) — Feasible? moved up on the survey form
**Problem:** *Feasible?* sat on the *Survey Report* tab outside any group, so it had no label and was far down the page; *Proceed anyway* was hidden there too.
**Fix:** *Feasible?* (and, for Project Managers, *Proceed anyway* when the answer is No) now sit in the **Site Details** group at the top of the form, with their labels. The **Survey Report** tab holds only the written report (rich-text box) for anyone who wants to add detail. Same fields, same behaviour and rules. File: `views/epc_site_survey_views.xml`. Upgrade: `-u csl_epc_site_survey` (the feasibility module's survey view extension is unaffected).

### Update 8 (2026-10-19) — list shows the figures behind the dashboard tiles
The Site Surveys list now has **Usable Area (sq ft)** and **Sanctioned Load (kW)** columns. The footer under *Usable Area* shows the **Average** (the "Avg usable area" tile) and the footer under *Sanctioned Load* shows the **Total** (the "Sanctioned load surveyed" tile), so a click on either tile lets you check the figure against the rows. (Odoo shows one footer figure per column; the total area is the average × number of rows. Tick rows to get the figure for just those.) File: `views/epc_site_survey_views.xml`. Upgrade: `-u csl_epc_site_survey`.

### Update 9 (2026-10-19) — "Avg usable area" now matches the list footer
**Problem:** the tile showed 11,306 but the list it opens showed an average of 10,576. Two surveys had no area filled in: the tile left them out, while the list counted them as 0.
**Fix:** the tile averages only surveys that have an area, and opens a list of exactly those surveys, so tile and list footer show the same figure. The tile's sub-line says how many surveys it covers. "Sanctioned load surveyed" is still the total over all surveys. File: `models/epc_stage_dashboard.py`. Restart the server (Python change only).
