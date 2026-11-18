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
