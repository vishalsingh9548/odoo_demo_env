# UPDATE — csl_epc_subsidy (Subsidy)

> New module, added 2026-11-18. Gap #4. Own home-screen tile: *Subsidy*; schemes under *Configuration → Subsidy Schemes*.

## Why this change was made
Nothing tracked government subsidy (scheme, application, claimed / approved / paid). It is a large part of residential solar sales.

## What this module does (functionality)
- **Subsidy Scheme** master (`epc.subsidy.scheme`): authority, who it applies to, maximum system size, amount type (percentage of project cost / flat / per kW), amount, maximum subsidy, valid from/until, papers needed. **No scheme or rate is shipped or hard-coded** — the admin types the current rules.
- **Suggestion**: the lead and the quotation show the best matching scheme and expected subsidy. The quotation also shows *Customer pays after subsidy* — for information only; the order total is never changed.
- **Subsidy Application** (`epc.subsidy.application`, `SUB/<year>/00001`): Draft → Documents Ready → Applied → Approved → Disbursed (or Rejected); portal number, claimed / approved / disbursed amounts and dates, days pending, chatter.
  - Created automatically (as Draft) when an order is confirmed and a scheme fits; the scheme's papers are added to the project's document pack.
  - *Documents Ready* checks the scheme's papers are no longer pending; *Approved* needs the approved amount and portal number; *Disbursed* needs the paid amount.
- **Project**: *Subsidy* smart button. List, pivot and filters for money not yet received.

## Dependencies
`csl_epc_documents`, `csl_epc_boq` (project capacity).

## Not included
No accounting entries are made for the received subsidy. It is tracked on the application only, so existing invoices and accounts are not affected.

## Safety
Suggestion computations run with sudo, so ordinary Sales users who are not in the Solar EPC group can still open leads and orders. Auto-creation on confirmation is inside a savepoint with logging.

## Impact
- Lead *Solar Details* tab and the order's *Solar EPC Terms* tab get a small subsidy block (inherited views).
- `sale.order.action_confirm` is extended after the original has run.

## Install / upgrade notes
Install after `csl_epc_documents`. Create at least one scheme (e.g. the current PM Surya Ghar rates) before the suggestion shows anything.

## Tested note
*Customer pays after subsidy* is never shown below zero. Verified: suggestion on lead and quote, auto Draft application on confirm, scheme papers added to the document pack, full Draft → Disbursed flow.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **Subsidy** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Starter data for production (added 2026-11-18)
**One starter scheme: PM Surya Ghar (Residential)** — 30,000 per kW, capped at 78,000, up to 10 kW, valid until 2027-03-31, with its 4 papers attached — `data/subsidy_scheme_data.xml`. The note on the record says to verify the rates on the official portal before go-live. State schemes are not included because their rates could not be verified here.

- **Why:** so a new installation is usable straight after installing the module, with no typing of master data.
- **How it loads:** from the module's `data/` folder when the module is installed. The records are `noupdate`, so anything edited later in the screens is never overwritten by an upgrade.
- **Impact:** only adds master records. No existing record or behaviour is changed. If a record with the same name was typed by hand before installing, delete or rename it first, because names must be unique for DISCOMs.
- **Status:** files checked for correct XML only; not yet installed anywhere (install is done by the owner).

## Update (2026-11-19) — More starter subsidy schemes
Five more records added to `data/subsidy_scheme_data.xml` so the suggestion on the lead also works for larger and non-residential systems (before, the only scheme stopped at 10 kW, so e.g. a 450 kW lead showed nothing):

| Scheme | Applies to | Max size | Amount |
|---|---|---|---|
| PM Surya Ghar: Group Housing Society / RWA (Common Facilities) | Residential | 500 kW | 18,000 per kW |
| Sample: State Top-up Subsidy (Residential) | Residential | 10 kW | Flat 10,000 |
| Sample: Commercial Capital Subsidy | Commercial | 500 kW | 8,000 per kW, cap 20,00,000 |
| Sample: Industrial Capital Subsidy | Industrial | 1,000 kW | 6,000 per kW, cap 50,00,000 |
| Sample: Rooftop Solar Incentive (All Customers, % of cost) | All | no limit | 10% of cost, cap 3,00,000 |

- **Real vs sample:** only the Housing Society scheme follows a real scheme (verify on the official portal); the four "Sample:" ones are made-up test values and say so in their notes - replace or deactivate them before go-live.
- **How it loads:** `noupdate`, created on upgrade because they did not exist yet; the original PM Surya Ghar record and any edited rate are never overwritten.
- **Impact:** only adds master records. If several schemes fit, the one paying the most is suggested. A percentage scheme shows 0 on the lead (its amount is worked out on the quotation).
- **Tested:** upgraded `solar_epc_v2` with no errors; all 6 schemes present.

## Dashboard (added 2026-11-19)
- **What:** a live **Dashboard** screen for this module, the first entry of its menu, in the same look as the Commissioning and Handover dashboards (design was approved from a preview first). It uses the shared screen in `csl_epc_core`, so this module ships no JavaScript: only `models/epc_stage_dashboard.py` (method `_dashboard_subsidy`), `views/epc_dashboard_views.xml` (screen entry and menu) and one line in `models/__init__.py` and in the manifest.
- **Shows:** Money waiting (claimed, applied or approved), received this year (with change on last year), average days to money, stuck over 30 days, rejection rate, expected subsidy on open quotations. Charts: status funnel, claimed / approved / disbursed by month, share by scheme, ageing of open applications, days-to-money trend. Table: applications waiting longest.
- **Clicking** a tile or a chart bar opens the list of exactly the records that were counted. Numbers are read with the logged-in user's own access rights.
- **Reads from:** epc.subsidy.application. No new fields, no data changes.
- **Impact:** adds one menu entry ("Dashboard") and one client action. Nothing existing is changed; uninstalling the module removes it.
- **Tested:** on a throw-away copy of the database (never on the live one): each dashboard was built empty and with a full scenario, and its result checked to be sendable to the browser. Not yet viewed in a browser.
- **Install / upgrade notes:** the manifest changed, so **restart the Odoo server first**, then *Upgrade* this module (the server keeps each module's file list in memory until it restarts).

## Lead now uses its quotation's price for percentage schemes (2026-11-19)
- **What changed:** `models/crm_lead.py`. The lead's *Suggested Subsidy Scheme* and *Expected Subsidy* now take the untaxed total of the lead's latest non-cancelled quotation as the project cost. Before, the lead had no cost, so a percentage-of-cost scheme always showed 0 there while the quotation showed the real figure.
- **Why:** the lead and its quotation disagreed (0 against 17,158.58 in a real case).
- **Impact:** with no quotation yet, a percentage scheme still shows 0 (there is no price to take a percentage of); per-kW and flat schemes are unchanged. The scheme chosen can change once a quotation exists, if another scheme then pays more. No new fields, no data change, no upgrade needed.
- **Install / upgrade notes:** Python code changed, so **restart the Odoo server**; no module upgrade is required.

## Change (2026-11-20) — Screens restricted to Solar EPC Administrator
- This module's menus, fields, buttons and tabs now use `csl_epc_core.group_epc_admin` (only Administrator sees them). Upgrade the module to apply.

## Fix (2026-11-20) — reads `epc_document_ids`
- The project documents link was renamed in `csl_epc_documents` (see its UPDATE.md); the subsidy application now reads `project.epc_document_ids`.
