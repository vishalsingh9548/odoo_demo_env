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
