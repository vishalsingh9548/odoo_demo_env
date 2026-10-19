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
