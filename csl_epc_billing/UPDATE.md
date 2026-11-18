# UPDATE — csl_epc_billing (Milestone Billing)

> New module, added 2026-11-18. Gap #6. Own home-screen tile: *Milestone Billing* (managers); plans under *Configuration → Payment Plans*.

## Why this change was made
There was only a basic payment-structure drop-down on the order. Solar projects are billed in stages (advance, delivery, commissioning, retention) and the competitor raises these automatically.

## What this module does (functionality)
- **Payment Plan** master (`epc.payment.plan`): stages with percentage, trigger and optional delay; the stages must add up to 100%.
- **Sales Order → Milestone Billing tab**: choose a plan, *Load Stages from Plan* (also done at confirmation), edit the stages if needed. Shows total % and amount billed.
- **Triggers** that raise the stage invoice: order confirmed · all material delivered (last delivery validated) · installation complete (project milestone "Structure & Module Installation Complete" reached) · commissioning approved · handover approved · manual. A *days after* delay (e.g. retention 90 days after handover) is scheduled and raised by a daily job.
- **Invoices are DRAFT only**, created with Odoo's own down-payment invoicing, so taxes work normally. Nobody's invoice is posted automatically.
- A failure never blocks the real action (delivery, approval, confirmation): it is logged and a note is written on the order; the stage keeps a *Raise Invoice* button.
- Stage list + pivot (billed vs pending, retention held).

## Dependencies
`csl_epc_commissioning`, `csl_epc_handover`.

## Only plan users are affected
Everything is skipped for orders without a Payment Plan, so all existing orders, deliveries, approvals and milestones behave as before.

## Impact
- Extended (original always called first): `sale.order.action_confirm`, `stock.picking._action_done`, `project.milestone.write`, `epc.commissioning.action_approve`, `epc.handover.action_approve`.
- Stage invoices use down-payment lines, so the final regular invoice of the order deducts them.
- One new scheduled job (daily).

## Install / upgrade notes
Install after the commissioning and handover modules. Create a plan first. Installation trigger relies on the seeded milestone name; use the manual button if it was renamed.

## Tested note
Verified: advance invoice on confirm (draft, correct 30%), installation / commissioning / handover triggers, 90-day retention scheduled then raised by the daily job, delivery trigger on the last validated delivery. An order without a plan is untouched.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **Milestone Billing** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Starter data for production (added 2026-11-18)
**Two payment plans** — *Residential 50-40-10* (advance, delivery, commissioning) and *Commercial / Industrial 30-30-10-20-10* (advance, delivery, installation, commissioning, 10% retention 90 days after handover) — `data/payment_plan_data.xml`.

- **Why:** so a new installation is usable straight after installing the module, with no typing of master data.
- **How it loads:** from the module's `data/` folder when the module is installed. The records are `noupdate`, so anything edited later in the screens is never overwritten by an upgrade.
- **Impact:** only adds master records. No existing record or behaviour is changed. If a record with the same name was typed by hand before installing, delete or rename it first, because names must be unique for DISCOMs.
- **Status:** files checked for correct XML only; not yet installed anywhere (install is done by the owner).
