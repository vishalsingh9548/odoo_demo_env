# UPDATE — csl_epc_amc (O&M / AMC Contracts)

> Part of the Solar EPC split. Stage 17. Own app icon: **AMC Contracts** (visible to Project Manager and above).

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **AMC Contracts** (`epc.amc.contract`, chatter): project, customer, start/end date, contract value, service frequency, next service date, SLA response hours, preventive-maintenance plan, helpdesk team. Service frequency: monthly, quarterly, half-yearly or yearly. States: Draft → Active → Expired / Terminated (*Activate*, *Terminate* buttons).
- **Complaints**: *Log Complaint* opens a new Helpdesk ticket pre-filled with the contract's team, customer and contract; *Tickets* smart button. Helpdesk tickets have an *AMC Contract* field. From there the standard `helpdesk_fsm` flow handles field-service visits and parts.
- Seeded Field Service project (*Solar O&M Field Service*) and Helpdesk team (*Solar AMC Support*, Field Service on).

## Dependencies
`csl_epc_core`, `helpdesk`, `helpdesk_fsm`, `industry_fsm`, `industry_fsm_sale`, `industry_fsm_stock`.

## Views, menus and screens
- `views/epc_amc_contract_views.xml` — list, form, search, window action.
- `views/helpdesk_ticket_views.xml` — AMC Contract field on the ticket.

- Top-level app **AMC Contracts** (Project Manager and above).
- *Configuration → AMC Support Teams* (opens the standard Helpdesk teams; Administrator only).

## Data and security
Sequence `seq_epc_amc_contract` (`AMC/<year>/`); data records `epc_fsm_project` and `epc_helpdesk_team`.

`security/ir.model.access.csv` — Field User read; Project Manager read/write/create; Administrator full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_amc_contract.py`, `helpdesk_ticket.py`, their views, sequence and the helpdesk/FSM seed data.

**Edits while splitting:** the Helpdesk/FSM enterprise dependencies moved from the old single manifest into this module, so they are only required if AMC is installed. Demo data references `csl_epc_amc.epc_helpdesk_team`.

## Impact
- No functional change. Helpdesk and Field Service apps are pulled in only by this module.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.
