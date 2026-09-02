# CSL Solar EPC

An Odoo 18 Enterprise app covering a solar EPC (Engineering, Procurement,
Construction) company's whole journey with a customer — from the first
sales enquiry all the way through building the system, handing it over,
and looking after it afterwards under a maintenance contract.

This app was built to match the process laid out in `chirayu.png` (in this
same folder) — 18 stages, plus 5 things (Documents, Approvals,
Communication, Activities, Calendar) that apply at every single stage.

For a full, plain-language, step-by-step account of **what was built, why,
and its impact** — read `LOG.md`. This file is just the overview and the
"how do I run it" instructions.

## What's in the app

| Stage | What it does |
|---|---|
| 1. Lead / CRM | Solar-specific questions added to the normal CRM lead screen (capacity, roof type, sanctioned load, etc.) |
| 2. Site Survey | Records what an engineer finds on a visit to the customer's site |
| 3. Technical Feasibility | Turns survey measurements into a concrete system design and generation estimate |
| 4. BOQ & Costing | An itemised costing sheet; one click turns it into a real Sales Quotation |
| 5-6. Quotation / Sales Order | Solar-specific commercial terms (warranty, delivery, payment, certifications) on the normal Sales screens |
| 7. Project Creation | Confirming the Sales Order automatically creates a real Project, with starter milestones |
| 8A. Procurement | A shortage list against a project turns straight into real Purchase Orders |
| 8B. Inventory & Logistics | Uses Odoo's own Inventory app, already linked to the project |
| 9-10. Planning & Site Execution | Gantt planning plus a Site Checklist (civil, structure, cabling, earthing, testing) on every task |
| 11. Daily Progress Report | One short diary entry per project per day |
| 12. Quality Checks | Covers all 4 QC categories from the diagram: Incoming Material, Installation, Electrical, Final |
| 13. Commissioning | The formal switch-on record, with a certificate |
| 14. Handover | Final documents, customer training, and project closure |
| 15-16. Billing & Payments | Rides on Odoo's own Milestone Billing + Accounting apps |
| 17. O&M / AMC | The maintenance contract itself, plus complaint tickets that flow into Odoo's own Helpdesk + Field Service apps |
| 18. Analytics & Reports | A live, click-through dashboard — see below |

Everywhere in the app: every field has a plain-language help tooltip, and
every document has a comment thread, file attachments, and reminders for
free — those are Odoo's own built-in Chatter/Activities, not something
this app had to build.

## The Dashboard

Menu: **Solar EPC → Dashboard**. Every number on it is a live query
against the real data — nothing is a static picture or a spreadsheet that
needs manually rebuilding. Click any tile or chart bar to open the exact
underlying records.

## How to run it

A dedicated config file and test database are already set up:

```bash
cd /home/csl/odoo_18_dev/odoo
/home/csl/odoo_18_dev/env/bin/python odoo-bin -c /home/csl/odoo_18_dev/odoo_csl_solar_epc.conf
```

Then open **http://localhost:8074**, database `csl_solar_epc_test`,
log in as `admin` / `admin`.

To re-install from scratch (wipes the test database):

```bash
PGPASSWORD=odoo18 dropdb -U odoo -h localhost --if-exists csl_solar_epc_test
PGPASSWORD=odoo18 createdb -U odoo -h localhost csl_solar_epc_test
cd /home/csl/odoo_18_dev/odoo
/home/csl/odoo_18_dev/env/bin/python odoo-bin -c /home/csl/odoo_18_dev/odoo_csl_solar_epc.conf -i csl_solar_epc --stop-after-init
```

That loads a full demo story — a 500 kW commercial rooftop project for
"Suryoday Textiles Pvt Ltd" — walked through every stage from enquiry to
an active AMC contract, so there's something real to look at immediately.

## Who can see what

Three access levels (Settings → Users → Groups → Solar EPC): **Field
User** (create/edit their own records), **Project Manager** (also
approves documents and sees every project), **Administrator** (also
manages AMC contracts and configuration). Whoever installs the app is
made an Administrator automatically.

## Notes for whoever picks this up next

- This app depends only on standard Odoo Enterprise apps (CRM, Sales,
  Purchase, Inventory, Project, Field Service, Planning, Helpdesk,
  Accounting) — nothing here needs the `ibsolar` or `grando_solar`
  projects installed; those were only used as design references (see
  `LOG.md` Step 1 for exactly what was and wasn't borrowed from them).
- `LOG.md` explains every design decision and why it was made that way —
  read it before changing the architecture, so you're not re-deciding
  something that was already deliberately chosen.
