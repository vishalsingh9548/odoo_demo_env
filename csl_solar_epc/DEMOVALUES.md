# Demo Walkthrough — Exact Values For Every Field

This is a start-to-finish walkthrough of **one** demo project through all 18
stages of the pipeline, written so you can follow it top to bottom and type
in exactly what's shown — no guessing what a "reasonable" value would be.

It follows the same customer/project the whole way through: **Metro
Textiles Pvt Ltd**, a 100 kW rooftop commercial installation in Pune. This
is separate from the module's own built-in demo data (which already tells
the story of "Suryoday Textiles") — this file is for typing things in by
hand, one screen at a time, to see the pipeline work.

Only fields worth actually typing something into are listed. Anything not
mentioned is either optional, or fills itself in automatically (an
auto-generated reference number, a computed total, a field copied from an
earlier stage) — don't hunt for those.

## Before you start: two lessons already learned the hard way

**1. Create your own products first — don't reuse Odoo's built-in demo
products.** While testing this app, a BOQ line was accidentally linked to
a stock Odoo demo product ("Furniture Delivery (Manual)"). That product
turned out to carry its own built-in pricing/automation behaviour
(explained in `LOG.md` Step 16) that silently overrode this app's own
price calculation and even triggered a second, unrelated project to be
created. Nothing wrong with this app's code — just the wrong product
picked. Avoid it entirely by creating a few plain products of your own
first, via **Inventory → Products → New** (or **Sales → Products**):

| Name | Product Type | Sales Price |
|---|---|---|
| Solar Module 540W | Goods | 9,500 |
| String Inverter 100kW | Goods | 450,000 |
| DC Cable (per metre) | Goods | 45 |
| AC Cable (per metre) | Goods | 220 |
| Mounting Structure Set | Goods | 3,500 |
| Earthing Kit | Goods | 4,500 |

Tick **Track Inventory** (sometimes shown as the "Storable" toggle) on each
one — without it, Odoo treats the product like a service with no real stock,
so receiving a Purchase Order for it will never actually create any stock on
hand, and Stage 8B's "Issue to Project" button will have nothing to issue.
Leave everything else on the product form at its default.

**2. Leave "Product" blank on pure cost lines.** BOQ lines like Civil
Work, Manpower, Logistics, Overheads and Margin aren't real stock items —
the Product field on a BOQ line is optional for exactly this reason.
Leaving it blank is correct, not incomplete.

---

## Stage 1 — Lead / CRM

**Where:** CRM app → **Leads** (or **New** from the CRM pipeline) →
**Solar Details** tab.

| Field | Value |
|---|---|
| Contact / Customer | Metro Textiles Pvt Ltd (create if it doesn't exist) |
| Customer Segment | Commercial |
| Proposed Capacity (kW) | 100 |
| Monthly Electricity Bill | 60,000 |
| Roof / Land Type | RCC Roof |
| Site Address | Plot 14, MIDC Industrial Area, Pune, Maharashtra |
| Site Latitude | 18.5204 |
| Site Longitude | 73.8567 |
| Sanctioned Load (kW) | 120 |
| Existing Transformer Available | ✓ (ticked) |
| Grid Access Available | ✓ (ticked) |
| Expected Closure Date | Today + 30 days |

**Button:** *Schedule Site Survey* — creates and opens the Stage 2 record.

---

## Stage 2 — Site Survey

**Where:** opened automatically from Stage 1, or Solar EPC → **Site
Surveys** → New.

| Field | Value |
|---|---|
| Lead / Opportunity | (already linked) |
| Survey Date | Today |
| Survey Engineer | any internal user |
| Roof / Land Type | RCC Roof |
| Available Area (sqft) | 8,000 |
| Sanctioned Load (kW) | 120 |
| Existing Transformer Available | ✓ |
| Grid Access Available | ✓ |
| Site Address | (already filled in from the lead) |

**Shadow Analysis & Photos tab:**
| Field | Value |
|---|---|
| Shadow Analysis | "No significant shadow from neighbouring structures; minor shading from a rooftop water tank before 9am, negligible for the rest of the day." |

**Survey Report tab:**
| Field | Value |
|---|---|
| Survey Report | "Roof is structurally sound RCC, flat with 8,000 sqft usable area. No major obstructions. Recommended for 100 kW rooftop installation." |
| Feasible? | Yes |

**Buttons, in order:** *Submit for Approval* → (as a Project Manager)
*Approve* → **Create Feasibility Study** (creates and opens the Stage 3
record — this button only appears once the survey is Approved).

---

## Stage 3 — Technical Feasibility

**Where:** opened automatically from Stage 2, or Solar EPC →
**Feasibility Studies** → New.

| Field | Value |
|---|---|
| Site Survey / Lead | (already linked) |
| Proposed Capacity (kW) | 100 |
| System Type | Rooftop |
| Module Tilt Angle (°) | 15 |
| Module Orientation | South |
| Estimated Annual Generation (kWh) | 146,000 |
| Performance Ratio (%) | 80 |
| Financial Benefits | "At current tariff, this system offsets roughly ₹9.5 lakh/year in electricity cost, paying back the investment in approximately 4.5 years." |
| Feasibility Report | "Site confirmed suitable for a 100 kW rooftop system. Recommended module tilt 15°, south-facing, no major shading." |
| Feasibility Result | Feasible |

**Buttons:** *Submit for Approval* → *Approve* → **Create BOQ** (creates
and opens the Stage 4 record).

---

## Stage 4 — BOQ & Costing

**Where:** opened automatically from Stage 3, or Solar EPC → **BOQ &
Costing** → New.

System Capacity shows 100 kW automatically (live from Stage 3). Margin
(%) defaults to 15 — leave it, or change it, your choice.

**BOQ Lines** (Add a line for each row):

| Category | Product | Description | Qty | UoM | Unit Cost |
|---|---|---|---|---|---|
| Solar Modules | Solar Module 540W | 540W Mono PERC modules | 185 | Units | 9,500 |
| Inverters | String Inverter 100kW | 100kW string inverter | 1 | Units | 450,000 |
| Mounting Structures | Mounting Structure Set | GI mounting structure | 100 | kg | 3,500 |
| DC Cables | DC Cable (per metre) | 4 sq mm DC cable | 500 | Units | 45 |
| AC Cables | AC Cable (per metre) | 16 sq mm AC cable | 150 | Units | 220 |
| LT Panels / DB | *(leave blank)* | LT distribution panel | 1 | Units | 65,000 |
| Earthing Material | Earthing Kit | Earthing kit, 6 sets | 6 | Units | 4,500 |
| Civil Work | *(leave blank)* | Foundation & civil work | 1 | Units | 150,000 |
| Manpower / Labour | *(leave blank)* | Installation labour | 1 | Units | 120,000 |
| Logistics | *(leave blank)* | Transport to site | 1 | Units | 35,000 |
| Overheads | *(leave blank)* | Project overheads | 1 | Units | 25,000 |

Total Cost and Total Sell Price calculate themselves — don't type
anything into them.

**Buttons:** *Submit for Approval* → *Approve* → **Create Quotation**
(creates and opens the Stage 5 Sales Quotation).

---

## Stage 5–6 — Quotation → Sales Order

**Where:** opened automatically from Stage 4 (a normal Sales
Quotation, with a **Solar EPC Terms** tab added).

**Solar EPC Terms tab:**
| Field | Value |
|---|---|
| Warranty Type | Both |
| Delivery Terms | Scheduled |
| Freight Terms | Freight Included |
| EPC Payment Structure | Milestone-wise |
| Cancellation Policy | Deduction on Cancellation |
| Certifications | IEC + BIS |
| Wattage Tolerance | Positive Tolerance |

Order Lines are already filled in, copied from the BOQ — no need to
re-enter them.

**Buttons:** *Send by Email* (optional) → **Confirm**.

Once confirmed, an **"EPC Project"** smart button appears at the top of
the order — **always use that one**, not any other "Tasks"/"Project"
button that might also appear. (Confirming an order with a service-type
product on it can make Odoo's own native Sales/Project integration create
a second, unrelated project automatically — see `LOG.md` Step 16. The
"EPC Project" button always points at the correct one, created by this
app.)

---

## Stage 7 — Project Creation

**Where:** click the **EPC Project** smart button on the confirmed Sales
Order.

Everything of note fills itself in automatically and stays live: Source
Lead, Source BOQ, EPC Sales Order, System Capacity (kW), Budgeted Cost,
Contract Revenue — plus 4 starter milestones (Material Procured,
Structure & Module Installation Complete, Electrical Wiring & Testing
Complete, Commissioning & Handover Complete).

The only thing worth setting by hand:
| Field | Value |
|---|---|
| Project Manager | any internal user |
| Planned Date (Start → End) | Today → Today + 60 days |

---

## Stage 8A — Procurement

**Where:** on the Project form, click **New Material Request** (visible
until the first one exists).

| Field | Value |
|---|---|
| Project | (already linked) |
| Request Date | Today |

**Lines** — pick your own products from the table at the top of this
file, quantities matching what the BOQ needs:

| Product | Quantity Required |
|---|---|
| Solar Module 540W | 185 |
| String Inverter 100kW | 1 |
| DC Cable (per metre) | 500 |
| AC Cable (per metre) | 150 |
| Mounting Structure Set | 100 |
| Earthing Kit | 6 |

**Buttons:** *Submit for Approval* → *Approve* → **Create Purchase
Orders** — this raises a real RFQ per vendor for whatever quantity isn't
already in stock (Quantity To Purchase). If a product has no vendor set
up yet, add one under the product's **Purchasing** tab first, or set
**Preferred Vendor** directly on the Material Request line.

---

## Stage 8B — Inventory & Logistics

Nothing to type in this app specifically — once a Purchase Order from
Stage 8A is confirmed, go to the **Inventory** app as normal: receive the
incoming shipment (Validate the receipt), then transfer stock out to the
project site the same way you would for any other delivery. Everything
here is standard Odoo Inventory, already linked to the project.

---

## Stage 9–10 — Planning & Site Execution

**Where:** Project app → open the project → **Tasks** (Gantt view for
planning, list/kanban for day-to-day use).

Create a task (or several — one per work package), assign it to a crew
member, and set Planned Start/End dates. As work actually happens on
site, tick these boxes on the task (each has a matching date field, fill
it in with the day the work was done):

| Checkbox | Suggested date |
|---|---|
| Civil Work & Foundation Done | Today + 5 days |
| Structure Installation Done | Today + 10 days |
| Module Installation Done | Today + 15 days |
| DC Cabling Done | Today + 17 days |
| AC Cabling Done | Today + 19 days |
| LT Panel / Inverter Installation Done | Today + 20 days |
| Earthing Done | Today + 21 days |
| Testing & Pre-Commissioning Done | Today + 25 days |

---

## Stage 11 — Daily Progress Report

**Where:** open the project → click **New Daily Progress Report** (header
button, next to Share Project) for the first one; after that, use the
**Daily Progress Reports** smart button that appears instead. **Reporting
→ DPR Report** prints every DPR across every project as a PDF. One per
project per day (the system won't let you create two for the same day).

| Field | Value |
|---|---|
| Project | (select your project) |
| Report Date | Today |
| Weather | Sunny |
| Manpower Deployed | 12 |
| Today's Work Progress | "Structure installation 60% complete on the east wing. On track against plan." |
| Material Received | "50 modules received from vendor." |
| Material Consumed | "40 modules installed." |
| Equipment Deployed | "1 mobile crane, 2 welding sets." |
| Issues / Risks | "None." |
| Tomorrow's Plan | "Continue structure installation on west wing." |

---

## Stage 12 — Quality Checks

**Where:** Solar EPC → **Quality Checks** → New. Create **one record per
category** (four total) — the checklist for each fills itself in the
moment you pick the category.

| Field | Value |
|---|---|
| Project | (select your project) |
| QC Category | pick one of the four, one record each: Incoming Material QC / Installation QC / Electrical QC / Final QC |
| Check Date | Today |
| Inspector | any internal user |

On each checklist line that appears, set **Result** to *Pass* (or *Fail*
if you want to test the failure path — the Overall Result field at the
top works it out automatically from the lines).

---

## Stage 13 — Commissioning

**Where:** Solar EPC → **Commissioning** → New.

| Field | Value |
|---|---|
| Project | (select your project) |
| Commissioning Date | Today + 26 days |
| Commissioning Checklist | "All electrical connections verified. Insulation, continuity and voltage tests passed. System synchronised with grid." |
| System Testing Done | ✓ |
| Verified Generation (kWh) | 410 (a plausible single day's output for a 100 kW system) |
| Customer Walkthrough Done | ✓ |
| Customer Approved | ✓ |

**Buttons:** *Submit for Approval* → *Approve*.

---

## Stage 14 — Handover & Closure

**Where:** Solar EPC → **Handover & Closure** → New.

| Field | Value |
|---|---|
| Project | (select your project) |
| Closure Date | Today + 28 days |
| Customer Training Done | ✓ |
| Customer Training Date | Today + 27 days |
| Project Closure Report | "100 kW rooftop system commissioned and handed over to Metro Textiles Pvt Ltd. All documentation, warranty certificates and O&M manual provided. Customer trained on system monitoring." |

**Buttons:** *Submit for Approval* → *Approve*.

---

## Stage 15–16 — Billing & Payment

**Correction:** the 4 milestones seeded on the project (Stage 7) are a
progress checklist only — they are not actually linked to any Sales
Order line, so ticking one off has no effect on invoicing. Milestone-wise
staged billing isn't wired up yet (tracked as an open item — see
`LOG.md`). What actually happens today: your order lines are plain
"Goods" products with the default "Ordered quantities" invoicing policy,
so the **full contract value becomes invoiceable the moment the order is
confirmed** — there's no staged gate.

**Where:** on the **Sales Order** (open it via the project's "EPC
Project" smart button, or directly from Sales), click **Create Invoice**.
- Choose **Regular Invoice** (not a down payment) to invoice everything in
  one go, or manually reduce the quantities/amount in the invoice wizard
  if you want to bill only part of it for now.
- Confirm the draft invoice (**Confirm** button) to post it.
- Register the customer's payment on the posted invoice (**Register
  Payment** button) — this is standard Accounting, nothing solar-specific
  to type in.

---

## Stage 17 — O&M / AMC

**Where:** Solar EPC → **AMC Contracts** → New (Project Manager access
required).

| Field | Value |
|---|---|
| Project | (select your project) |
| Start Date | Today + 30 days |
| End Date | Today + 395 days (1 year cover) |
| Contract Value | 25,000 |
| Preventive Service Frequency | Quarterly |
| Next Preventive Service Due | Today + 120 days |
| Preventive Maintenance Plan | "Module cleaning, connection tightness check, inverter fan/filter inspection, generation log review." |
| SLA Response Time (Hours) | 24 |
| Warranty End Date | Today + 1,825 days (5 years) |
| Support Team | Solar AMC Support (already set up by this app) |

**Button:** *Activate* once ready to start covering the customer.

To test the complaint flow: click **Log Complaint** on the contract —
this opens a pre-filled Helpdesk ticket. From there, standard Helpdesk +
Field Service screens take over: convert the ticket into a Field Service
task, assign an engineer, and log the visit/parts used exactly as you
would for any other Field Service job.

---

## Stage 18 — Analytics & Reports

**Where:** Solar EPC → **Dashboard** (also the first thing you see on
opening the app), or Solar EPC → **Reporting** for the individual
pivot/graph reports.

Nothing to type in — every number here is a live query against everything
entered in Stages 1-17. Click any tile or chart bar to open the exact
records behind it.

---

## Cross-cutting, at every stage

- **Documents:** the paperclip/chatter panel on the right of every record
  — drag and drop files there.
- **Approvals:** the *Submit for Approval* / *Approve* / *Reject* buttons
  on Survey, Feasibility, BOQ, Commissioning and Handover.
- **Communication:** *Send message* / *Log note* at the top of the
  chatter panel.
- **Activities:** the *Activities* button next to Send message — schedule
  a follow-up/reminder on any record.
- **Calendar:** anything scheduled as an Activity, or an FSM task with a
  date, shows up automatically in the Calendar app — nothing to set up.
