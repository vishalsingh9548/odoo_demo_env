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
