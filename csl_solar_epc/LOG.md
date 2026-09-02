# CSL Solar EPC — Build Log

This file is a plain-language, step-by-step diary of everything done while
building this module: **what** was done, **why** it was done, and **what
effect** it has on the rest of the app. Read this top to bottom to understand
the whole history of the project without having to read the code.

For a general overview of what the app does and how to install/run it, see
`README.md` in this same folder.

---

## Step 1 — Read the spec image and studied two reference projects

**What:** Read `chirayu.png` (the client's process-flow diagram) closely: it
lays out 18 stages, from a sales Lead all the way through Site Survey,
Feasibility, Costing (BOQ), Quotation, Sales Order, Project Creation,
Procurement, Inventory, Planning, Site Execution, Daily Progress Reports,
Quality Checks, Commissioning, Handover, Billing, Payments, AMC/O&M service,
and Analytics — plus 5 things that apply at every stage (Documents,
Approvals, Communication, Activities, Calendar). Also studied two existing
projects on this machine purely as *pattern references* (nothing from them
was copied wholesale, and nothing in this module depends on them):
- `extra_addons/odoo_demo_env/grando_solar` — a small, basic module. Useful
  for simple ideas (numbering documents, "smart button" links between
  records) but it doesn't touch real Purchasing, Inventory or Quality at
  all — just informational fields and file uploads.
- `extra_addons/ibsolar` — a much bigger set of modules. Useful for a couple
  of specific ideas (turning a shortage list into a Purchase Order with a
  2-step approval, keeping a running history of price changes instead of
  overwriting old numbers). Its `csl_amc` module was checked and is **not**
  used as a reference — the user confirmed it's just a generic help-desk
  ticket app, not real AMC (maintenance contract) logic.

**Why:** Building "from scratch" without first checking what already exists
on this machine — both the client's requirements and Odoo's own built-in
apps — risks either missing a requirement or reinventing something Odoo
already does well (and better-tested).

**Impact:** Confirmed that most of the 18 stages can ride on standard,
already-installed Odoo Enterprise apps (Purchase, Inventory, Project,
Quality, Field Service, Planning, Helpdesk, Accounting) instead of being
built from zero. The real work is the handful of solar-specific documents
that don't exist in stock Odoo (Site Survey, Feasibility Study, BOQ &
Costing, Daily Progress Report, Commissioning, Handover, AMC Contract) and
the glue that chains everything together into one pipeline.

---

## Step 2 — Chose the overall architecture

**What:** Decided to build **one single app** called `csl_solar_epc` (not a
family of small modules) that depends on Odoo's `crm`, `sale_management`,
`sale_project`, `purchase` + `project_purchase`, `stock` + `project_stock`,
`project_enterprise`, `industry_fsm` (+ `_sale`/`_stock`), `planning`,
`helpdesk` + `helpdesk_fsm`, `account`, and `board`.

**Why:** The target folder is a single module, and Odoo already ships
production-quality apps for Purchasing, Inventory, Field Service, Planning,
Helpdesk and Accounting — reusing them means real transactional depth
(actual Purchase Orders, actual stock moves, actual invoices) instead of a
shallow custom copy, which is exactly what the user asked for ("more
flow-full like ibsolar inventory, not just logging details like grando
solar").

**Impact:** Every one of the custom documents this module adds will plug
into those real apps (e.g. a confirmed Sales Order creates a real `project`
with real Purchase Orders and Deliveries under it) rather than existing in
isolation.

---

## Step 3 — Built the module skeleton (Phase 0: Scaffolding)

**What:** Created the folder structure (`models/`, `views/`, `security/`,
`data/`, `demo/`), the `__manifest__.py` (the app's ID card — name, which
other apps it depends on, which files to load), a simple app icon, a
top-level "Solar EPC" menu, three permission groups (Field User, Project
Manager, Administrator — each one includes the permissions of the one
before it), and one reusable building block: `epc.approval.mixin`. This
mixin gives any document a Submit → Approve/Reject workflow (with who
submitted it, who approved/rejected it, and when) without having to write
that logic five separate times.

**Why:** The image shows "Approvals: Multi-Level Approvals" as something
that applies to *every* stage, not just one. Writing it once as a shared
building block, then reusing it on Site Survey, Feasibility, BOQ,
Commissioning and Handover, means it behaves identically everywhere and
only needs to be fixed in one place if something's wrong.

**Impact:** The app can now be installed on a blank database with no
errors (verified by running a real install, not just reading the code) —
this is the foundation everything else in later steps builds on top of.

**Test performed:** Created a fresh database `csl_solar_epc_test` and ran
`odoo-bin -i csl_solar_epc --stop-after-init` against it (config file
`odoo_csl_solar_epc.conf`, port `8074`). *(Result of this specific test run
is recorded in the next log entry once it finishes — first-time installs on
a brand-new database also have to install ~175 other standard Odoo modules
this app depends on, which takes several minutes.)*

---

## Step 4 — Drafted the Lead → BOQ document chain (Phase 1, in progress)

**What:** Wrote (not yet switched on in the app — see next entry once
installed and tested) three pieces:
- Extended the standard CRM Lead form with solar-specific questions
  (proposed capacity, roof/land type, sanctioned load, GPS location, whether
  a transformer/grid connection already exists) — this is Stage 1 in the
  image.
- A new **Site Survey** document (Stage 2) — one per site visit, capturing
  the roof/land measurements, shading notes, a site photo, and an
  engineer's yes/no feasibility opinion. Uses the Approval mixin from Step 3.
- A new **Technical Feasibility** document (Stage 3) — one per site,
  recording the recommended system size, tilt/orientation, a plant-layout
  drawing upload, estimated yearly generation, performance ratio, and the
  financial-savings case for the customer. Also uses the Approval mixin.

Each document has a "Create the next one" button (Lead → Create Site
Survey → Create Feasibility Study), following the same "smart button +
bridge action" pattern found in the `grando_solar` reference project, so a
user is never stuck wondering what to do next.

**Why:** These three documents are exactly what's missing from stock Odoo —
Odoo's CRM doesn't know what a "roof type" or a "performance ratio" is —
and they need to exist and be linked together *before* a price can be
quoted (Stage 4, BOQ, comes next).

**Impact so far:** No visible change yet — these files aren't wired into
the app's menu or install list yet. That happens once BOQ (Stage 4) is
written and the whole chain can be installed and tested together, so the
next log entry will report an install/test result for this whole batch, not
each file individually.

---

## Step 5 — Finished and tested the Lead → Quotation → Project chain (Stages 1-7)

**What:** Finished the BOQ document (Stage 4: itemised costing lines that
add up to a cost and, after adding a margin, a sell price) with a
"Create Quotation" button that copies every line straight onto a real Sales
Quotation. Added Solar EPC commercial terms (warranty, delivery, freight,
payment structure, cancellation policy, certifications, wattage tolerance)
onto the standard Sales Order screen (Stages 5-6). Made confirming that
Sales Order automatically create a real Project underneath it, pre-filled
with the customer, capacity and BOQ reference, plus four starter milestones
(Stage 7). Wired all of this into the app's menu and installed it.

**Why:** This is the backbone of the whole app — every later stage
(Procurement, Site Execution, Billing, AMC) needs a real Project to attach
itself to, and that Project needs to know where it came from.

**Impact:** Ran a real install against a throwaway test database
(`csl_solar_epc_test`, config `odoo_csl_solar_epc.conf`, port 8074) twice —
once for the bare skeleton (Step 3), once after adding all of the above —
and both times the app installed with **zero errors**. Also started the
actual Odoo server and confirmed the login page loads (HTTP 200), i.e. the
app genuinely runs, not just "installs without crashing." Caught and fixed
two real mistakes this way that would only have shown up when someone
actually used the screens: (1) a new field I added would have shown the
exact same label as an existing Odoo field on the same screen, which is
confusing in the UI — renamed mine to be clearer; (2) I tried to reuse a
field name that Odoo's own Sales-to-Project app already uses for something
slightly different — renamed mine to avoid silently fighting with it.

---

## Step 6 — Wrote Procurement, Site Execution, and Daily Progress Reports (Stages 8-11)

**What:**
- **Material Request** (Stage 8A): a shortage list against a project — for
  each material, how much is needed vs. how much is already in stock — with
  a manager approval step, and a button that raises real Purchase Orders
  (grouped by vendor) for exactly the shortfall.
- **Procurement & Inventory** (Stages 8A/8B): reused Odoo's own Purchasing
  and Inventory apps rather than rebuilding them — a Purchase Order now
  remembers which Material Request it came from, and deliveries/receipts
  already know which project they belong to (via the Purchase/Inventory
  apps this module depends on).
- **Project Planning & Site Execution** (Stages 9-10): added the standard
  installation checkpoints (civil work, structure, module mounting, DC
  cabling, AC cabling, LT panel/inverter, earthing, testing) as tick-boxes
  with dates directly on a project Task, and turned on Odoo's Field Service
  features for tracking site visits.
- **Daily Progress Report** (Stage 11): one short diary entry per project
  per day — weather, manpower on site, what got done, material
  received/consumed, a photo, issues, and tomorrow's plan. The app refuses
  to let two DPRs exist for the same project on the same day, to keep the
  diary honest.

**Why:** These are the stages where a project actually gets built. Reusing
Odoo's Purchase/Inventory apps (instead of a shallow custom copy) is
exactly what makes this "more flow-full" than a basic version — every
Purchase Order here is a real, working document with its own approval,
vendor communication and receiving process already built by Odoo, not a
static record.

**Impact:** All of these plug into the Project record from Step 5, so a
Project now has a working "shopping list → real purchase orders" flow and
a running site diary, both visible directly from the Project screen.

---

## Step 7 — Wrote Quality Checks, Commissioning, and Handover (Stages 12-14)

**What:**
- **Quality Check** (Stage 12): covers all four QC categories from the
  process diagram — Incoming Material, Installation, Electrical, Final —
  as one flexible checklist model. Odoo's own built-in Quality app was
  checked first and turned out to only work for warehouse deliveries (it
  insists on a stock document), which doesn't fit an on-site installation
  check, so this is a small purpose-built model instead. Picking a category
  auto-suggests the right checklist items (e.g. picking "Electrical"
  suggests Insulation Test, Continuity Test, Voltage Test) so nobody has to
  remember the list from scratch. The overall Pass/Fail is worked out
  automatically from the individual items — nobody has to remember to set
  it themselves.
- **Commissioning** (Stage 13): the formal switch-on record — checklist,
  system testing, measured generation, customer walkthrough, and the
  signed commissioning certificate — with the same Submit → Approve
  workflow as everything else.
- **Handover** (Stage 14): the closing paperwork — as-built drawings, test
  reports, O&M manual, warranty certificate, customer training, and a
  closure report.

**Why:** These are exactly the stages standard Odoo has no answer for at
all, so it was pointless to try and bend an existing app to fit — a small,
purpose-built model was the more honest and reliable choice here.

**Impact:** A project can now be traced end-to-end from "material arrived"
through to "customer signed off and was trained," with every step timestamped.

---

## Step 8 — Wrote Billing, O&M and AMC Management (Stages 15-17)

**What:**
- **Billing & Payments** (Stages 15-16): reused Odoo's own Sales-to-Project
  Milestones feature (already built into the Purchase/Project apps this
  module depends on) rather than writing custom invoicing logic — a
  project's milestones can be tied directly to a Sales Order line so
  invoicing happens automatically as milestones are reached.
- **AMC Contract** (Stage 17): the one document standard Odoo genuinely has
  no equivalent for — records the maintenance agreement itself (how often
  to service the system, until when, for how much, the SLA response time,
  the preventive maintenance plan). A "Log Complaint Ticket" button opens
  a pre-filled Helpdesk ticket. From there, the standard Helpdesk +
  Field Service apps (already dependencies of this module) take over
  automatically for Complaint → Engineer Visit → Parts Used — nothing
  custom was written for that part, because Odoo's own `helpdesk_fsm` app
  already does exactly this.
- Set up one dedicated Field Service project and one Helpdesk team,
  specifically for AMC service visits, separate from each customer's own
  installation project (since one O&M team looks after many completed
  installations at once).

**Why:** Building a whole custom ticketing/dispatch system from scratch
would have duplicated a lot of what Odoo's Helpdesk and Field Service apps
already do well — the only genuinely missing piece was the contract record
itself, so that's the only piece that was custom-built.

**Impact:** A completed project can now be handed off into an active
maintenance contract, and a customer complaint against that contract flows
straight into the same Field Service tools used during installation.

---

## Step 9 — Built Analytics & Reports, and finished cross-cutting features (Stage 18 + always-on features)

**What:**
- **Analytics & Reports** (Stage 18): a Project Dashboard, Project
  Profitability (budgeted cost vs. contract revenue), Procurement Report,
  Inventory Report, DPR Report, Quality Report, Billing & Collection
  Report, and O&M/AMC Report — each a real, live report (not a static
  picture), plus one combined "Solar EPC Dashboard" screen. Odoo's fancier
  Spreadsheet Dashboard app was deliberately **not** used for this, because
  its charts normally have to be hand-designed once inside Odoo's own
  Spreadsheet editor after installing — that can't be scripted and verified
  automatically, so it isn't something this build could guarantee works
  without a person sitting down and building it by hand afterward. Real
  working reports were chosen over an empty placeholder.
- **Cross-cutting features that apply at every stage** (from the "always
  applicable" column in the diagram): every document already has
  Documents (file attachments + a comment thread), Communication (that
  same comment thread), and Activities (scheduled reminders/to-dos) for
  free, because they all use Odoo's standard chatter — nothing custom
  needed. Calendar is likewise automatic (site visits and activities
  already show up there). Approvals is the one cross-cutting feature that
  needed real work, and it was built once, in Step 3, as a shared building
  block reused by five different documents, instead of five separate copies.

**Why:** The dashboard reuses real report data instead of a mock-up, so
the numbers on it are never out of date. The cross-cutting features were
checked explicitly against the diagram's own "Cross Cutting" column to
make sure nothing on that list was accidentally skipped.

**Impact:** Every one of the 18 numbered stages in the client's diagram,
plus all 5 cross-cutting features, now has a working screen somewhere in
this app.

---

## Step 10 — Wrote a full demo story covering every stage

**What:** A sample project — "Suryoday Textiles Pvt Ltd", a 500 kW
commercial rooftop system — walked all the way from first enquiry through
Site Survey, Feasibility, BOQ, Quotation, a confirmed Sales Order, a real
Project, a Material Request, two Daily Progress Reports, two Quality
Checks, Commissioning, Handover, and finally an active AMC contract with
one open complaint ticket.

**Why:** A brand-new app with zero data is hard for anyone to explore or
demo. Walking one realistic project through literally every stage means
anyone opening this app for the first time can see the whole pipeline
working end-to-end immediately, instead of having to create 15+ records by
hand just to see what a finished project looks like.

**Impact:** Installing this app with demo data turned on gives a fully
populated, realistic example to click through and learn from.

---

## Step 11 — Built a real dynamic dashboard (like ib_crm's), not a static picture

**What:** Replaced the placeholder "Solar EPC Dashboard" (which was just a
few standard Odoo pivot/graph screens glued together) with a proper custom
dashboard, built the same way as ibsolar's own CRM Manager Dashboard: a
small Python "data backend" model that gathers live numbers on request, and
a matching interactive on-screen component (KPI tiles, charts, tables) that
calls it. It shows: how many projects are active and what they're worth,
how much is still awaiting approval or attention (material requests,
quality checks), how many maintenance contracts are active, a breakdown of
every project by pipeline phase (Execution / Commissioned / Handed Over /
Under AMC), procurement spend per project, quality pass/fail by category,
budgeted cost vs. contract revenue per project, upcoming maintenance visits,
and the most recent site diary entries. Every tile and chart is clickable
and opens the exact underlying records — the number shown and the list that
opens always match, because they're built from the same query.

**Why:** The user specifically asked for a dashboard "of this type" — a
genuinely dynamic, functioning screen showing live EPC data, not a
picture or a bundle of separate stock report screens. Reusing the same
pattern already proven in the ibsolar codebase (rather than inventing a
new mechanism) also means it's built the way this team already knows how
to maintain.

**Impact:** Opening the dashboard now gives a true at-a-glance status of
the whole EPC operation, with every number a live query against the real
project/procurement/quality/AMC records, not something that needs
refreshing or was true only at some earlier snapshot in time.

---

## Step 12 — Full install + server test

**What:** Ran one complete install of the entire app, from every custom
model down to the new dashboard's frontend code, against a brand-new,
empty database — the most honest test available, since it's exactly what
someone installing this app for the first time would experience.

**Found and fixed one real bug this way:** the dedicated Field Service
project created for AMC service visits (Step 8) was missing its Company
field. Odoo's own Field Service app *requires* every Field-Service-enabled
project to belong to a specific company — my code didn't set one, so the
very first install failed outright with a database error instead of
completing. Added the missing field and re-ran the install from a fresh
database (the failed attempt had left the database in a half-built state,
so continuing on top of it would not have been a reliable test).

**Why this matters / impact:** This is exactly why "write the code, then
actually install it" is not optional — this mistake could not have been
found by reading the code, only by running it for real. See the next log
entry for the final, successful result.

---

## Step 13 — Tested the dashboard the way a real browser actually uses it, found and fixed two more bugs

**What:** A module installing cleanly only proves the *setup* works — it
says nothing about whether clicking around the app afterwards actually
works. So after the install succeeded, the real server was started and the
dashboard was exercised exactly the way the browser does it: logging in
over HTTP, then calling the dashboard's data method through the same
network request the browser's JavaScript sends — not a shortcut, the real
thing. This caught two genuine bugs that a successful install could never
have revealed:

1. **The dashboard's main method crashed on every single call.** Odoo has
   two different ways a background method can be invoked — "act on a
   specific record" vs. "just run this calculation, no particular record
   needed." The dashboard method was written as the first kind by mistake,
   so every request to it failed instantly with an unrelated-looking
   technical error. One missing marker (`@api.model`) was the fix.
2. **Nobody could actually open the dashboard even after fixing #1**,
   because it reads a summary across many different document types (BOQs,
   material requests, quality checks, AMC contracts...), and a regular
   Field User doesn't have full access to all of them individually by
   design (Step 3's access rules). Fixed by having the dashboard check
   once "is this person even an EPC app user at all?" and, if so, let it
   read the summary data — the same trade-off every real Odoo dashboard
   makes: a summary count is safe to show even to someone who can't edit
   every underlying record it's built from.

Also discovered along the way: the very first attempt to make the
installing admin an automatic member of the app's Administrator group
(Step 12) silently did nothing — proven by directly checking group
membership before/after in a live Python session, not by guessing. The
`<record>` XML tag used doesn't reliably update a record that belongs to a
different app (here, Odoo's own built-in admin user) — switched to the
`<function>` XML tag instead (the same mechanism already used successfully
elsewhere in this module for the BOQ-to-Quotation link), which is the
reliable way to do this.

**Why:** Anyone can write code that "looks right." The only way to know it
*is* right is to run it the way a real user would and watch what actually
happens — reading the code back to check for mistakes would not have
caught either of these two bugs, since both are about how Odoo's request
layer behaves at runtime, not about anything visibly wrong in the source.

**Impact:** Re-tested after each fix, over the same real HTTP path, until
the dashboard returned correct, fully-populated data with no errors. The
dashboard is now confirmed to actually work for a real logged-in user, not
just "install without crashing."

---

## Step 14 — Final proof: one more from-scratch install, fully verified

**What:** Dropped the test database entirely and re-ran the whole install
one final time, exactly as a brand-new customer installing this app for
the first time would experience it — no leftover state, no manual fixes
applied along the way. Then, with the real server running:
- Confirmed the module installed cleanly (no errors, no warnings).
- Confirmed the installing admin automatically had full Solar EPC access
  (the Step 13 fix, proven this time on a genuinely fresh database).
- Logged in over real HTTP, exactly like a browser, and called the
  dashboard's data method the same way the browser's JavaScript does —
  got back fully correct numbers for every KPI, chart and table, with the
  demo project correctly showing as "Under AMC" in the portfolio-phase
  breakdown, the right pass/pending split on Quality Checks, the right
  revenue/cost figures, and the right upcoming maintenance date.
- Confirmed the dashboard's own frontend code (the JS/XML/SCSS from Step
  11) is actually being served to the browser as part of the app.

**Why:** A test that only proves "it worked after I fixed it live" isn't
trustworthy — the only test that actually matters is "does it work from a
completely clean install," since that's what will really happen when
someone else picks this project up. Repeating the whole install one more
time, on a throwaway database, with zero manual patches in between, is
what makes this result something to actually trust.

**Impact:** Every one of the 18 stages in the client's diagram, all 5
cross-cutting features, the full demo story, and the dynamic dashboard are
now confirmed working — not just written — on a from-scratch install. The
app is left running live so it can be opened and clicked through directly.

---

## Step 15 — Manual click-through by a real person found two Site Survey screen bugs

**What:** Everything up to Step 14 was tested either by an automated
script or by me driving the browser myself. This time, the actual user
clicked through the app by hand — create a Lead, add a Site Survey,
Submit it, Approve it — and found two real problems that no automated
test had caught, because both are about how the *screen* is laid out, not
about whether the underlying calculation is correct:

1. **The "Shadow Analysis" field had no visible label.** The field was
   working fine and saving data correctly — it just looked broken,
   because in Odoo's form-building rules, a field placed loose on a page
   (not inside a labelled two-column group) shows up as a bare text box
   with no caption above it. Fixed by putting it inside its own group,
   the same way every other field on that screen already is.
2. **There was no way to move from an Approved Site Survey into a
   Feasibility Study.** This was the bigger find: the code to create a
   linked Feasibility Study from a survey (`action_create_feasibility`)
   already existed and worked — but the button that was supposed to call
   it was never actually added to the screen. So once a survey was
   approved, a user hit a dead end: no button, and the "Feasibility
   Studies" smart button stayed hidden too (it only appears once a linked
   feasibility study exists, which nothing was creating). Fixed by adding
   a "Create Feasibility Study" button to the Approve/Reject button bar,
   shown exactly when a survey is Approved and doesn't have one yet —
   the same pattern the BOQ screen already uses successfully for its own
   "Create Quotation" button.

**Why:** This is exactly the gap that automated HTTP/ORM testing (Steps
13-14) can't catch — those tests call the *methods* directly and never
discover that a working method was never wired to a clickable button, or
that a working field has no visible label. Only someone actually looking
at the rendered screen and trying to move forward finds that kind of bug.
This is why a real manual walkthrough was worth doing even after the
automated tests all passed clean.

**Impact:** Both fixes are one-line view changes only — no changes to the
underlying Python logic, since the logic was already correct. Applied to
the database with a module upgrade, and the live server was restarted so
the fix is visible immediately (an already-running server keeps stale
copies of view definitions in memory until it's restarted — a normal
Odoo behaviour, not a bug). Survey → Feasibility now has the same
one-click bridge that BOQ → Quotation already had. Anyone stepping through
the pipeline by hand from here on should no longer hit a dead end at that
stage.

---

## Step 16 — Chased down a pricing mystery, found a stale field, and closed the last dead end

**What:** Continuing the manual walkthrough, two more things looked wrong:
a BOQ line's price came out wrong on the Quotation, and a Project's System
Capacity showed 0 and then "fixed itself" after a few minutes without
anyone doing anything visible. Both were investigated all the way to a
definite, DB-checked cause before touching any code:

1. **The BOQ line price wasn't the bug — the test product was.** One BOQ
   line had its Product set to a generic sample product that ships with
   every Odoo install ("Furniture Delivery (Manual)") for unrelated demo
   purposes. That particular product carries its own built-in pricing
   behaviour that overrides whatever price is handed to it — nothing to do
   with this app's code, which was confirmed (by reading the actual
   database rows) to be calculating and sending the *correct* marked-up
   price every time. Lesson, not a bug: BOQ lines for pure costing
   categories (Civil Work, Manpower, Logistics, Overheads) should be left
   without a Product at all — that field was always meant to be optional
   for exactly this reason — and DEMOVALUES.md (below) spells this out so
   nobody hits it again.
2. **The Project's System Capacity "fixing itself" was two separate real
   findings, not one.** First: confirming a Sales Order actually creates
   *two* projects, not one — this app's own correctly-linked EPC project,
   plus a second, generic project Odoo's own Sales/Project integration
   creates automatically whenever an order line uses a "service" type
   product (the same demo product from finding #1). The second project
   has none of this app's data on it, which is what looked broken — it
   simply wasn't the real project. Second, and this one *was* a genuine
   bug: System Capacity on a Project was a plain number copied once, the
   moment the project was created, from the BOQ — unlike Budgeted Cost and
   Contract Revenue right next to it, which were already built to always
   show the BOQ's current number. If the BOQ's capacity was blank at that
   exact moment (as it was here), the Project was stuck showing 0 forever,
   even after someone filled the real number in afterwards.
3. **Procurement had no "Start" button.** The Project screen could show a
   list of Material Requests already raised, but had no way to raise the
   *first* one — exactly the same class of dead end as Site Survey →
   Feasibility in Step 15, just one stage further down the pipeline.

**Fixes made:**
- System Capacity on a Project is now wired the same way as Budgeted Cost
  and Contract Revenue — it always shows the BOQ's current number, live,
  not a one-time snapshot.
- Added a "New Material Request" button to the Project screen, visible
  until the first Material Request exists (mirroring the Step 15 button),
  so Procurement can always be started from the project itself.
- No code changed for the pricing mystery — it was a test-data choice, not
  a defect. Documented instead.

**Why:** The capacity bug is the same underlying lesson as Step 13's
dashboard bugs and Step 15's missing button: something can look completely
broken on screen while the underlying calculation is perfectly correct —
here, a stale copy sitting right next to two fields that were built the
right way made the difference obvious once compared side by side. Confirmed
with direct database checks before and after the fix (not just "looks
right now") — before the fix, the Project's number matched neither the
BOQ nor updated when the BOQ changed; after the fix, changing the BOQ's
capacity directly changed the Project's number, live, exactly like the two
Monetary fields beside it always did.

**Impact:** Applied with a module upgrade (zero errors) and a live server
restart. Procurement (Stage 8A) can now be started from the Project screen
with one click, the same as every other bridge in the pipeline. A new
`DEMOVALUES.md` was written alongside this fix — a complete, start-to-
finish walkthrough of one demo project through all 18 stages with the
exact value to type into every field, written specifically to steer around
the test-product pitfall from finding #1 so nobody loses time chasing it
again.

---

## Step 17 — BOQ list decluttered, Procurement now pre-fills itself, and warehouse stock is finally tracked by project both ways

**What:** Four more things fixed in one pass, following a closer look at
ibsolar's own Material Requisition screen (`ib_inventory`) for how a
mature version of this same idea works there:

1. **BOQ line list decluttered.** Unit Cost and Subtotal are now hidden
   by default on the BOQ Lines grid (still there — one click on the
   column-picker gear brings them back — just not cluttering the main
   view, which now leads with Category, Product and Quantity).
2. **Material Requests now write themselves.** Clicking "New Material
   Request" (moved next to Share Project, at the top of the Project
   screen — easier to find than a stat button buried in the button row)
   no longer opens a blank form. It creates the request immediately with
   one line per BOQ item that has a Product attached, quantity copied
   straight from the BOQ — mirroring how ibsolar's own requisition screen
   pre-fills itself from a Bill of Materials, rather than making someone
   retype what the BOQ already says. What's actually short of stock still
   shows automatically per line, exactly as before.
3. **Incoming stock is now tagged by project.** Confirming a Purchase
   Order that has a project on it now stamps that same project onto the
   warehouse receipt it creates. Before this, `stock.picking.project_id`
   was a field that existed but nothing ever filled in — Odoo's own
   `project_purchase` app only wires the project onto the *order*, not the
   *receipt* that comes from it. Checked directly in the database, before
   and after: receipt "WH/IN/00007" showed no project until this fix,
   correctly showed the project afterwards.
4. **Outgoing stock now exists as a real, trackable step.** There was
   previously no way to represent "this material left the warehouse and
   went to the project site" as an actual stock movement — Purchase
   Orders only ever cover what's short, never what's already sitting in
   stock. Added an "Issue to Project" button on the Material Request that
   creates a real internal transfer for whatever's on hand, moving it to
   a site location created automatically the first time a project needs
   one. Verified end-to-end with a real product: received 10 units onto
   a Purchase Order, confirmed the receipt carried the project, then
   issued those same 10 units out to the project's site location and
   confirmed that transfer also carried the project.

**Why:** The heavier multi-level HR-approval machinery in ibsolar's own
requisition screen (employee records, department chains, two-tier
sign-off) is a different, much larger system built for a different
purpose than this app's own approval mixin, so it wasn't copied wholesale
— only the one part of its design actually relevant here (pre-fill from
what's already been costed, don't make someone retype it) was brought
over. The incoming/outgoing tracking gap was a real, confirmed hole: a
project's material could be bought and received without ever being
traceable back to that project's own stock movements, which defeats the
point of Stage 8B being "connected" to the rest of the pipeline at all.

**Impact:** Confirmed with direct database and shell checks, not just
"looks right" — the receiving picking and the outgoing transfer both
carry the correct project after this fix, where neither did before.
`DEMOVALUES.md`'s product-setup instructions were also corrected along
the way: the two sample products it originally described need "Track
Inventory" switched on, or Odoo treats them as having no real stock at
all and neither the incoming nor outgoing tracking has anything to work
with — found by hitting exactly that wall during this fix's own testing.
Applied with a module upgrade (zero errors) and a live server restart.

---

## Step 18 — Create PO redone properly, and Quality Checks got an actual bug fix plus real teeth

**What:** Two more rounds of manual testing turned up one genuine bug and
one missing safeguard:

1. **"Create Purchase Orders" used to fail silently if a product had no
   vendor set up.** It tried to guess a vendor automatically and, if it
   couldn't, just skipped that line — with nothing telling the user why
   their new PO had nothing in it. Rebuilt it to always open a brand-new
   Purchase Order screen with every short-of-stock line's Product and
   Quantity already filled in, leaving only Vendor for a person to pick
   (pre-filled too, if every line happens to agree on one already).
2. **Switching a Quality Check's category didn't refresh its checklist.**
   Pick "Incoming Material QC" first, its four checklist items appear —
   correct. Then change the category to "Installation QC", and the same
   four Incoming Material items stayed on screen instead of being
   replaced by Installation's own five items. Root cause: the code that
   fills in the checklist only ran "if the checklist is currently empty",
   so it worked exactly once and then silently stopped doing its job on
   every category change after that. Fixed by having it always replace
   the checklist to match whatever category is currently selected.
3. **Nothing stopped a delivery being received with no quality check at
   all.** The process diagram is explicit that Incoming Material QC sits
   *between* Goods Receipt and Store in Warehouse — but until now,
   validating a receipt and putting stock away worked identically whether
   a quality check existed or not. Added a real guard: validating a
   project's incoming receipt now checks for a logged, *passed* Incoming
   Material Quality Check against that specific receipt, and blocks with
   a clear message if one is missing or hasn't passed yet. Verified this
   actually blocks, using a real receipt with no quality check logged.

**Why:** Both the PO bug and the QC bug are the same shape as Step 15/16's
findings — code that quietly does nothing instead of clearly failing or
clearly succeeding. A blank "Create Purchase Orders" result with no
explanation, and a checklist that's wrong but not obviously wrong, are
both far worse than an honest error message. The QC gate on receiving
closes a real gap: a checklist model with no consequence for skipping it
isn't actually enforcing quality, just recording it after the fact.

**Impact:** Confirmed the PO screen now arrives pre-filled by inspecting
the actual context Odoo hands the form. Confirmed the receiving block
works by deliberately validating a receipt with no quality check logged
against it and getting the expected error, not a silent success. Applied
with a module upgrade (zero errors) and a live server restart.

---

## Step 19 — Incoming Material checklist was generic; now it's the real delivery

**What:** Spotted right after Step 18's fix: Incoming Material QC's
checklist ("Modules", "Inverters", "Mounting Structures", "Cables") was a
fixed, generic list — the same four labels every single time, regardless
of what a delivery actually contained. A delivery of just modules and
inverters still showed a line for "Mounting Structures" and "Cables" that
had nothing to do with what was really delivered. Fixed by dropping the
generic list for this one category and building the checklist instead
from the real products on the delivery/receipt actually linked to it —
picking a receipt now fills the checklist with the exact products on that
receipt, by name. The other three categories (Installation, Electrical,
Final) keep their generic checklists, since those genuinely have no
underlying document to check against — a physical installation step isn't
"delivered", there's nothing to read the real list from.

Also narrowed which receipts show up in the "Related Delivery/Receipt"
picker to just this project's own incoming shipments, so it's not a
scroll through every receipt in the whole database.

**Why:** A checklist that doesn't reflect what was actually delivered
isn't really checking anything — it was accidentally generic instead of
accidentally wrong, but the effect is the same: an inspector ticking
"Pass" on "Mounting Structures" for a delivery that never contained any.

**Impact:** Applied with a module upgrade (zero errors) and a live server
restart. Incoming Material QC's checklist now always matches the real
delivery it's checking.

---

## Step 20 — QC checklists moved out of code and into a configurable list

**What:** Installation, Electrical and Final QC's checklist items
("Structure QC", "Insulation Test", etc.) were hardcoded in Python — the
only way to change what gets checked was to edit the module's source
code. Built a proper configuration screen instead: a new **QC
Checkpoints** model (Solar EPC > Configuration > QC Checkpoints, Project
Manager/Admin access) where each checkpoint is just a name plus which of
the 4 QC categories it belongs to. Add one, rename one, reorder them, or
untick Active to retire one — no code change, no upgrade needed, takes
effect on the very next Quality Check.

Incoming Material QC now draws from two sources at once, both real: any
checkpoints configured under "Incoming Material" (seeded with two
sensible starting ones — "Packaging Condition" and "Delivery Challan
Matches Purchase Order" — things that apply to *any* delivery), plus one
line per actual product on whichever receipt is picked, exactly as fixed
in Step 19. Verified directly: picking a category alone shows just the
two generic checks; picking an actual receipt on top of that adds exactly
that receipt's own products and nothing else.

The old hardcoded list was seeded into this new table as the starting
data (`data/epc_quality_checkpoint_data.xml`, `noupdate="1"` so it's a
one-time starting point, not something reset on every upgrade), so
nothing already using the app sees any change in behaviour until someone
deliberately edits it.

**Why:** A checklist a Project Manager can't adjust without asking for a
code change isn't really "configurable" — it just happens to be editable
by whoever built the app. Every other part of this pipeline that needs
tuning per company (security groups, sequences, the AMC support team) is
already real Odoo configuration data, not Python constants; this brings
QC checklists in line with that same expectation.

**Impact:** Applied with a module upgrade (zero errors) and a live server
restart. Nobody needs a developer involved to change what a Quality Check
inspects going forward.

---

## Step 21 — Passing Final QC now actually consumes the material it verified

**What:** Stage 8B's diagram ends with "Material Consumption (Against
Activity)" — the step after "Material Issue (To Project)" where material
that's actually been used stops counting as stock. Nothing built that
step yet; material issued to a project's site (Step 17) stayed as stock
on hand forever, even once it was clearly installed. Added a "Consume
Site Stock" button on Final QC, enabled only once that check has actually
Passed, which moves everything still sitting at the project's site into a
new "Installed / Consumed Material" location — a real stock move, not a
number edited by hand, so it stays fully auditable. Tested end-to-end: 10
units on hand → issued to site (still 10 on hand, now at the site) →
Final QC passed → Consume Site Stock → 0 on hand, confirmed via direct
query, not just "looks right on screen".

**Why:** Asked for directly — once Final QC (which includes
Pre-Commissioning QC) passes, whatever material went into that project is
physically part of the installation now, not warehouse stock, and the
numbers should say so.

**Impact:** Applied with a module upgrade (zero errors) and a live server
restart. The full Stage 8B chain — Vendor Delivery → GRN → Incoming QC →
Warehouse → Issue to Project → Consumption — now exists end to end, each
step a real, trackable stock move.

---

## Step 22 — Commissioning now prints a real certificate

**What:** The Certificate tab on Commissioning only accepted a file
someone made elsewhere and uploaded — there was no way to actually
produce one from this app's own data. Added a "Print Certificate" button
(visible once a Commissioning record is Approved) that generates a real
PDF: certificate number, project, customer, capacity, commissioning date,
verified generation, the written checklist, the three yes/no
confirmations (System Testing, Customer Walkthrough, Customer Approved),
and signature lines for the engineer and the customer.

**Why:** Asked for directly, and it's a genuine gap — a commissioning
certificate is supposed to be evidence the company generated and issued,
not just a scanned copy of something made outside the system.

**Impact:** Verified the PDF actually renders (309KB, valid PDF content),
not just that the button exists. Applied with a module upgrade (zero
errors) and a live server restart.

---

## Step 23 — Found (not yet fixed): Milestone Billing doesn't actually gate invoicing

**What:** Checked, at the user's request, exactly what happens when a
project reaches Stage 15 (Billing). Confirmed in the database that the 4
milestones auto-created on every project (Stage 7) have no `sale_line_id`
set — Odoo's real milestone-billing mechanism requires that link, so
right now marking a milestone "reached" has zero effect on invoicing.
Separately, the order lines copied from the BOQ are plain "Goods"
products on the default "Ordered quantities" policy, so the *entire*
contract becomes invoiceable the instant the order is confirmed — there
is no staged billing gate of any kind today, despite the diagram calling
for "Milestone-wise Billing".

**Why not fixed yet:** the user asked to defer this — it's a real
structural decision (rebuild order lines around linked milestone service
lines the "native" way, vs. add a simpler custom staged-invoice-by-
percentage action) rather than a quick fix, and needs a deliberate choice
before building either.

**Impact:** `DEMOVALUES.md`'s Stage 15-16 section was corrected to
describe what actually happens today (full-order invoicing, no staging)
instead of the inaccurate "mark a milestone, invoice that portion"
description it had before. No functional code changed. This is an open
item, not a completed one — revisit when ready to decide between the two
approaches.

---

## Step 24 — Menu cleanup, and every report now prints a PDF instead of opening a pivot

**What:** Three requested changes to the app's menus:
1. Removed the top-level "Daily Progress Reports" menu (it sat right
   beside Material Requests). Since that was the *only* way to create the
   very first DPR on a project, removing it without anything else would
   have been a dead end — added a "New Daily Progress Report" button to
   the Project screen instead (same pattern as the Material Request one),
   so starting Stage 11 still works, just from the project itself.
2. Removed "Solar EPC Dashboard" from the Reporting submenu — it was a
   duplicate of the Dashboard link already at the very top of the app.
3. All 7 reports under Reporting (Profitability, Procurement, Inventory,
   DPR, Quality, Billing & Collection, O&M/AMC) used to open an
   interactive pivot table. They now generate a real PDF instead, each
   pulling live data straight from the database at the moment it's
   printed — a proper printed report, not a screen you have to be sat in
   front of Odoo to read.

**Why:** Asked for directly. The pivot views were interactive analysis
tools; a PDF is what you actually hand someone or file away.

**Impact:** Verified every one of the 7 new PDF reports actually renders
(sizes from ~110KB to ~775KB, all valid), not just that the menu item
exists — and verified the new DPR button opens correctly with the project
pre-filled. Applied with a module upgrade (zero errors) and a live server
restart. Old, now-unused pivot/act_window report records were cleaned up
automatically by the upgrade rather than left behind as dead entries.

---

## Step 25 — Dashboard redesigned: mocked up first, approved, then built for real

**What:** Three charts (Procurement Spend by Project, Quality Checks by
Category, Revenue vs. Cost by Project) and the Recent DPR table came off
the live dashboard; three new ones went in their place, all answering a
different question — "what's stuck", not "how much money" — matching the
shift already made across procurement/inventory in Steps 17-21:
- **Pipeline Activity** — how much open work is sitting at each stage
  right now (unapproved Surveys/Feasibility/BOQs/Material Requests,
  pending Quality Checks).
- **AMC Contract Health** — every maintenance contract, by status.
- **Procurement Status** — Purchase Orders by stage in the RFQ-to-PO
  process (a process view, deliberately not a spend figure).

Before touching any code, a static HTML mockup of the new layout was
built and shared for approval first, since a dashboard redesign is worth
seeing before it's built. Only after that was approved did the real
backend (`models/epc_dashboard.py`), frontend (`epc_dashboard.js`/`.xml`)
get changed.

**Why:** Asked for directly. Mocking it up first avoided guessing at a
layout the user might not have wanted, and kept the actual code change
small and confident once the direction was confirmed.

**Impact:** Verified two ways: every new number was cross-checked against
a raw database count and matched exactly (e.g. Pipeline Activity's
"Quality Checks Pending: 1" against a direct `search_count` returning 1),
and the whole thing was re-verified over real HTTP — logged in and called
`get_dashboard_data` exactly the way the browser's own JavaScript does,
confirming the old chart keys (`recent_dprs`, `quality_by_category`) are
gone and the new ones are present and correct. Applied with a module
upgrade (zero errors) and a live server restart.

---

## Step 26 — Dashboard spacing fix (round 2) and a Sales Order smart button on Project

**What:** The first attempt to fix the dashboard's empty space at the
bottom (an invisible flex spacer) turned out not to actually work —
confirmed by the user's own screenshot after the "fix." Replaced it with
real content growth instead of a filler hack: chart canvases 280px →
340px, bigger KPI tile icons/numbers/padding, bigger chart/table card
padding and headings, more breathing room between the KPI row, chart row
and table, and a stronger background gradient extending toward the
bottom. Separately, added a "Sales Order" smart button to the Project
form's button box (`action_view_epc_sale_order`), so the project can be
navigated back to its originating Sales Order in one click, matching the
"EPC Project" smart button that already exists the other way round on
the Sales Order form.

**Why:** The invisible-spacer approach was cosmetically insufficient —
it didn't change how much real content the page showed, just quietly
padded empty space with more empty space. Growing the actual tiles,
charts and cards is what genuinely fills the screen. The Sales Order
button closes a one-way navigation gap the user pointed out.

**Impact:** Applied with a module upgrade (zero errors) and a live
server restart.

---

## Step 27 — QC Category trimmed down to Incoming Material and Final only

**What:** Removed "Installation QC" and "Electrical QC" from the QC
Category dropdown, in both `epc.quality.check` (the actual quality
checks) and `epc.quality.checkpoint` (the configurable checklist-item
master list), per explicit request — only Incoming Material QC and Final
QC remain selectable. Also removed the now-unreachable demo checkpoints
and the demo quality-check record that used the `installation` category,
so a fresh install won't recreate data in a category that no longer
exists.

**Why:** Asked for directly — the process only actually uses two QC
stages in practice, and having two unused categories in the dropdown was
just noise.

**Impact:** Two pre-existing quality checks in the live test database
(QC/2026/00010 and QC/2026/00002) still have `installation` stored as
their category — left untouched as historical records rather than
silently rewritten, so they'll now show a blank Category badge instead
of "Installation QC." Flagged to the user; can be reassigned or deleted
on request. Applied with a module upgrade (zero errors) and a live
server restart.

---

## Step 28 — Hid BOQ Total Cost/Sell Price and Project Budgeted Cost/Contract
## Revenue until the underlying pricing gap is fixed

**What:** These four fields were showing 0 on every BOQ and Project in
the live test data — not a bug, but a direct, correct consequence of BOQ
lines having no Unit Cost entered yet (confirmed by reading the actual
line values straight from the database: both `unit_cost` values were 0,
so `subtotal`, `total_cost` and `total_sell_price` all compute to 0, and
the Project's Budgeted Cost / Contract Revenue are `related` fields that
just mirror those same BOQ totals). Per the user's request, rather than
leaving 0s on screen that read as broken, hid `total_cost` and
`total_sell_price` on the BOQ list and form (`views/epc_boq_views.xml`),
and `boq_total_cost` / `boq_total_sell_price` on the Project form
(`views/project_project_views.xml`) with `invisible="1"` / `optional="hide"`.
The fields and their computation logic are untouched — only hidden from
view.

**Why:** Asked for directly, as a stopgap — showing a 0 that looks like
a broken calculation is worse than not showing the figure at all until
BOQ pricing (Unit Cost entry) is actually part of the day-to-day
workflow.

**Impact:** Purely a view-layer change; no model or computation logic
was touched, so re-showing these fields later (once BOQ pricing is
properly filled in as part of the normal flow) is just reverting the
`invisible`/`optional="hide"` attributes. **Open item — revisit later:**
decide how Unit Cost should actually get entered in practice (manually
on each BOQ line, or defaulted from the product's cost price) so these
figures are meaningful by default instead of needing to be remembered.
Applied with a module upgrade (zero errors) and a live server restart.

---

## Step 29 — Dashboard KPI: "Budgeted Cost" tile replaced with "Completed Projects"

**What:** Replaced the dashboard's "Budgeted Cost" KPI tile with a
"Completed Projects" tile. `models/epc_dashboard.py`'s `_get_kpis()` now
reuses the same handed-over-project-ids set it already computed for
excluding finished projects from "Active Projects", and reports its count
as a new `completed_projects` KPI (dropping the old `budgeted_cost` KPI
entirely, since it was redundant with the BOQ/Project total-cost figures
elsewhere). The tile is clickable, same as Active Projects, opening the
exact list of handed-over projects.

**Why:** Asked for directly — a plain cost figure at the top of the
dashboard wasn't as useful a headline number as knowing how many projects
have actually been finished.

**Impact:** Verified via `get_dashboard_data()` that `completed_projects`
returns the correct count and domain (matches projects with an approved
Handover). Applied with a module upgrade (zero errors) and a live server
restart.

---

## Step 30 — Four fixes: AMC funnel chart, report preview, DPR timesheet detail, QC gate button

**What:** Four separate, unrelated changes made together in one pass:

1. **AMC Contract Health chart** (`static/src/js/epc_dashboard.js`) —
   changed from a doughnut to a funnel-style chart. Chart.js has no native
   funnel type, so this uses a well-known plugin-free technique: a
   horizontal bar chart where each status's bar is a "floating"
   `[-count/2, +count/2]` segment centred on the same vertical axis,
   which reads as a symmetric funnel narrowing down the page (Draft →
   Active → Expired → Terminated) instead of a plain bar list. A custom
   legend was added by hand (one dataset can't drive Chart.js's default
   per-slice legend the way a doughnut's can).
2. **Print preview for all 7 PDF reports** (`views/epc_reports_board.xml`)
   — every report action's `report_type` changed from `qweb-pdf` to
   `qweb-html`. This is Odoo's own native behaviour, not custom code:
   `qweb-html` opens the report in an iframe with a "Print" button,
   instead of `qweb-pdf`'s immediate forced download with no preview
   step. Same templates, same data, just a different render/print path.
3. **DPR Report now shows who worked, on what, and for how many hours**
   (`views/epc_reports_board.xml`, DPR template) — for each Daily
   Progress Report row, a nested sub-table lists that project's real
   Timesheet entries (`account.analytic.line`, Odoo's own `hr_timesheet`
   data — the same data the Project app's own Timesheets tab shows) for
   that exact date: Employee, Task, Work Description, Hours. Not a new
   parallel data-entry table — it reads whatever timesheets are already
   logged against the project. `hr_timesheet` added to `__manifest__.py`
   depends (it was already installed transitively, but the module now
   directly relies on it, so it should be declared).
4. **Quality Check gate now has a working button, not just a message**
   (`models/stock_picking.py`) — the two existing block messages (no
   Incoming QC logged / logged but not passed) are now raised as
   `RedirectWarning` instead of plain `UserError`, with the exact same
   message text as before. `RedirectWarning` is Odoo's built-in mechanism
   for exactly this: the popup keeps blocking the receipt, but also shows
   a "Log Quality Check" button that jumps straight to a pre-filled
   Quality Check form (project + delivery/receipt + category already
   set), instead of only telling the user where to go find it themselves.
   A new dedicated action, `epc_quality_check_action_new_incoming`
   (`views/epc_quality_check_views.xml`, `view_mode="form"` only, so it
   always opens straight to a blank form, never a list), is what the
   button redirects to.

**Why:** All four asked for directly.

**Impact:** Verified all four end to end, not just "installs cleanly":
`get_dashboard_data()` still returns a correct `amc_contract_health`
breakdown; all 7 report actions confirmed as `report_type = qweb-html` in
the database; the DPR report template was rendered
(`_render_qweb_html`) and produced real HTML with no errors; a fresh test
receipt was created and `button_validate()` was called on it to confirm
`RedirectWarning` actually fires with the right message, the right
action id, the right button label, and the right project/picking
context — then rolled back (test data only, nothing left behind).
Applied with a module upgrade (zero errors) and a live server restart.

---

## Step 31 — Corrected Step 30: real funnel sorting, QC button moved out of the popup into a wizard, DPR report proven with real timesheet data

**What:** Direct user testing found Step 30's four changes needed real
fixes, not just polish:

1. **Funnel chart was never actually tapering.** The bug: AMC states were
   always drawn in a fixed order (Draft, Active, Expired, Terminated)
   regardless of their counts, so with real data like 1/3/0/1 the bars went
   up-then-down-then-up — not a funnel shape at all, and the small
   Terminated bar read as "missing" rather than just being small.
   `_renderAmcHealthChart()` now sorts the 4 stages by count, largest
   first, before charting, so it always narrows top-to-bottom like an
   actual funnel — labels, colours and click-domains all reordered
   together so nothing gets mismatched.
2. **"Log Quality Check" moved out of the warning popup entirely.** Per
   explicit correction, the button no longer lives inside the blocking
   message (`button_validate()` is back to a plain `UserError`, same
   wording as originally written). Instead, `stock.picking` gets a new
   computed field `epc_needs_incoming_qc` and a permanent header button —
   `views/stock_picking_views.xml` inserts it between the native
   "Validate" and "Print" buttons, visible only while a passed Incoming
   QC is genuinely still missing.
3. **Opens as a wizard, not a page navigation.** `action_log_quality_check()`
   returns its act_window with `target: 'new'`, so clicking the button
   opens the pre-filled Quality Check form as a dialog directly on top of
   the receipt screen, instead of navigating away and losing the
   picking's breadcrumb.
4. **DPR report's timesheet section proven to actually work.** The report
   looked unchanged in testing because the demo data has zero real
   Timesheet entries logged on any DPR's date — the code was correct but
   had nothing to show, and silently showed nothing. Two fixes: (a) added
   an explicit "No timesheet entries logged against this project for this
   date" line so the section is always visibly present, empty or not,
   instead of looking like nothing happened; (b) actually created a real
   timesheet entry against a test project/task/date and re-rendered the
   report to confirm the employee, task, work description and hours all
   print correctly when data exists (then rolled the test data back).

**Why:** All four were genuine gaps in Step 30, caught by direct
inspection of the running app rather than a second guess — the funnel
was a real sorting bug, the popup-button placement was an explicit
correction, and the DPR report needed proof with real data, not just a
correct-looking template.

**Impact:** Verified via `odoo shell`: `epc_needs_incoming_qc` computes
`True`/`False` correctly, `action_log_quality_check()` returns
`target: 'new'` with the right context, `button_validate()` now raises a
plain `UserError` again (confirmed no `RedirectWarning` button leaks
into the popup), and the DPR report's HTML was rendered twice — once
showing the "no entries" fallback, once showing a real logged timesheet
row with correct employee/task/description/hours — both passing. Applied
with a module upgrade (zero errors) and a live server restart.

---

## Step 32 — Funnel chart drops empty stages; found why the DPR report looked empty for real timesheet data

**What:** Two follow-ups from live testing:

1. **Funnel chart no longer shows empty stages.** With Expired at 0
   contracts, the funnel still listed "Expired (0)" as a zero-width row in
   both the bars and the legend — a stage nothing can be "filled into"
   shouldn't take up a slot at all. `_renderAmcHealthChart()` now filters
   out any status with a count of 0 before sorting/drawing, so the funnel
   only ever shows stages that actually have contracts in them.
2. **Root-caused why the DPR report showed "No timesheet entries" even
   after real timesheet hours were logged** (project "Abigail Peterson -
   Solar EPC (S00047)", task "task to install": John Doe / Anita Oliver,
   15 hours total, all dated 2026-08-31). Not a bug: that project had **no
   Daily Progress Report at all**, and the report only ever prints rows
   for DPRs that exist — a project with real timesheets but no DPR simply
   never appears in it. Created `DPR/2026/00005` for that exact project
   and date so the report now shows this real data end-to-end, live, as
   proof rather than a synthetic example.

**Why:** Both asked for directly after seeing the dashboard/report not
match expectations.

**Impact:** Verified via `get_dashboard_data()` that Expired (0) is still
correctly computed on the backend (nothing removed from the KPI data
itself) but is now filtered out only at chart-render time on the
frontend. Confirmed `DPR/2026/00005` persists and is linked to project 26
with the matching real timesheet lines already on that project/date, so
the printed DPR report will show the real Employee/Task/Description/Hours
breakdown for it. Applied with a live server restart (JS-only change,
no model/view/data changes this round).

---

## Step 33 — Commissioning now gated on Final QC, same pattern as the receiving gate

**What:** Commissioning could be Submitted for Approval regardless of
whether its project's Final Quality Check had actually passed — the
"System Testing Done" field was just a checkbox anyone could tick, with
nothing verifying a real Final QC record backed it up. Added the exact
same gate pattern already built for incoming receipts (Step 31):

- `epc.commissioning` gets a new computed field `epc_needs_final_qc` —
  True while the project has no passed Final QC (`epc.quality.check`,
  `category='final'`, `overall_result='pass'`) logged against it.
- `action_submit()` is overridden to block with a `UserError` if that's
  still true, so the check holds even if Submit is somehow triggered
  another way, not just via the button.
- On the form (`views/epc_commissioning_views.xml`), "Submit for
  Approval" and a new "Log Quality Check" button now show/hide as a pair
  — Submit is only visible once Final QC has actually passed; otherwise
  "Log Quality Check" takes its place.
- `action_log_quality_check()` opens a blank Quality Check form as a
  wizard dialog (`target: 'new'`) with Project and Category ("Final QC")
  already filled in — same UX as the incoming-receipt version, not a
  page navigation away from the commissioning record.

**Why:** Asked for directly — commissioning a system that hasn't actually
passed its final quality check shouldn't be possible just because a
checkbox was ticked.

**Impact:** Verified via `odoo shell`: a commissioning on a project with
no passed Final QC has `epc_needs_final_qc = True` and `action_submit()`
correctly raises; the same wizard action returns `target: 'new'` with the
right project/category context; a commissioning on a project that *has*
passed Final QC has `epc_needs_final_qc = False` and `action_submit()`
succeeds normally. Applied with a module upgrade (zero errors) and a live
server restart.

---

## Step 34 — "Consume Site Stock" button added to Commissioning, beside Submit for Approval

**What:** Added a "Consume Site Stock" button to the Commissioning form's
header, next to "Submit for Approval" — so the final stock-consumption
step (previously only reachable from the Final QC record itself) can be
done directly from Commissioning. New computed field
`epc_can_consume_site_stock` (True once the project has a passed Final QC
and still has material sitting at its site location) controls its
visibility. `action_consume_site_stock()` on `epc.commissioning` finds
that project's passed Final QC record and delegates to its own
`action_consume_site_stock()` — no duplicated stock logic, just a second
entry point to the same action.

**Why:** Asked for directly.

**Impact:** A mistake on my end during this step: I ran the module
upgrade against the database but forgot to restart the already-running
dev server afterward, so the live browser session was still serving the
old view definition and threw an `EvalError` (`epc_can_consume_site_stock`
undefined) the moment the page tried to evaluate the new button's
`invisible` condition. Restarting the server fixed it immediately — not a
code bug, just a missed step in the usual apply/restart routine.
Re-verified afterward with `get_view()` that the form's arch now loads
cleanly and includes the new field. Also verified via `odoo shell`: a
commissioning on a project with a passed Final QC and real stock still at
site shows `epc_can_consume_site_stock = True`, and calling the button's
action actually consumes that stock (site quants confirmed empty
afterward) — while a project with nothing left at site (or no passed
Final QC yet) correctly keeps the button hidden.

---

## Step 35 — Removed the Project Profitability report

**What:** Removed the "Project Profitability" entry from the Reporting
menu entirely — its menu item, `ir.actions.report`, and QWeb template
(`epc_report_profitability_pdf_action` / `epc_report_profitability_template`)
are all deleted from `views/epc_menus.xml` / `views/epc_reports_board.xml`.

**Why:** Asked for directly — not needed.

**Impact:** Confirmed via the upgrade log that Odoo cleanly deleted the
now-orphaned menu, report action and view records on upgrade (no manual
cleanup needed). The other 6 Reporting entries (Procurement, Inventory,
DPR, Quality, Billing & Collection, O&M/AMC) are untouched. Applied with
a module upgrade (zero errors) and a live server restart.

---

## Step 36 — Simplified the DPR report + "New Daily Progress Report" is now an instant download

**What:** Two changes to Daily Progress Report reporting:
1. Reporting > DPR Report no longer prints the 6-column summary row
   (Project/Reference/Date/Weather/Manpower/Reported By) above each
   project's timesheet table. Each block is now just a plain
   "Project — Date" heading followed straight by the Employee/Task/Work
   Description/Hours table (pulled live from real Timesheets, unchanged
   logic from Step 31/32) — the block markup itself was factored into a
   shared sub-template (`epc_report_dpr_project_block`) so it isn't
   duplicated.
2. The "New Daily Progress Report" button on the Project form no longer
   opens a blank `epc.dpr` form to fill in by hand. It's renamed
   "Download Today's Report" and now instantly downloads a report of
   exactly who worked on that project **today**, in the same simplified
   format as (1) — `project.project.action_print_today_dpr()` calls a new
   report action (`epc_report_dpr_today_pdf_action`) directly. Nothing is
   saved to the database; it's a pure print, so it can be run again any
   day.

**Why:** Asked for directly — the summary row wasn't wanted, and the
create-a-DPR-by-hand form (weather/manpower/material/issues fields) was
never what was actually wanted from that button; a same-day "who worked
today" printout was.

**Impact:** The `epc.dpr` model, its own fields and its list/form view
are untouched — they still exist and are still reachable via the
project's "Daily Progress Reports" stat button (once any record exists)
or a list view "New". They're just no longer wired to this particular
project-form button, which is now purely a print action. Verified via
`odoo shell`: the main DPR Report's rendered HTML no longer contains the
old "Reference" summary column; the new per-project "today" report
correctly names the project and, once a real timesheet line was created
for today against it (created and immediately rolled back, not left in
the DB), showed that exact employee/task/description/hours row. Applied
with a module upgrade (zero errors) and a live server restart.

---

## Step 37 — Reporting > DPR Report now shows today's work, not stale old dates

**What:** Following straight on from Step 36: the menu-level Reporting >
DPR Report was still looping over historic `epc.dpr` records (old demo
data from 30/31 Aug), so it kept showing yesterday's dates even when
opened today (1 Sept). Changed `epc_report_dpr_pdf_action`'s model to
`project.project` and rewrote `epc_report_dpr_template` to stop reading
`epc.dpr` at all — it now searches real Timesheets for `date = today`,
finds every distinct project that has one, and renders each through the
same shared `epc_report_dpr_project_block` used by the per-project
"Download Today's Report" button. Shows a plain "No project has any
timesheet entries logged today" message if nothing was logged yet.

**Why:** Asked for directly — "why 31st aug when today is 1 sept...
it should show projects in which work was done today."

**Impact:** Reporting > DPR Report and the project's own "Download
Today's Report" button now share identical logic and always agree with
each other and with the real Timesheets tab. Verified via `odoo shell`:
re-rendered the report with no filters and confirmed it lists exactly
the projects/employees/tasks/hours that already had real timesheet lines
dated 2026-09-01 in the test DB (found live, not synthetic), and none of
the old 2026-08-30/31 dates appear anywhere. Applied with a module
upgrade (zero errors) and a live server restart.

---

## Step 38 — Dashboard scrolls both ways and adapts down to phone-width screens

**What:** `static/src/scss/epc_dashboard.scss` / `static/src/xml/epc_dashboard.xml`:
- The dashboard's root (`.o_epc_dashboard`) now sets `height: 100%` and
  `overflow: auto` (both axes), so it always scrolls itself — vertically
  if its content is taller than the visible area, horizontally if
  anything can't shrink far enough to fit — instead of relying on
  whatever the surrounding Odoo action frame happens to do.
- Added a phone-width breakpoint (`max-width: 420px`) collapsing the KPI
  tile grid to a single column, and a `max-width: 360px` breakpoint
  letting the chart/table cards shrink to fill the row instead of
  holding a fixed 320px minimum that could exceed a very narrow phone's
  actual width.
- The "Upcoming AMC Preventive Services" table (the one part of the
  dashboard with several fixed columns that can't reflow) is now wrapped
  in its own `.o_epc_table_scroll` (`overflow-x: auto`) container, so a
  long project name or a narrow window scrolls just that table sideways
  instead of squashing its columns unreadably or scrolling the whole page.

**Why:** Asked for directly — "add both vertical and horizontal scroller
for dashboard and make it responsive for all screen sized."

**Impact:** The KPI row and chart row already reflowed reasonably via
existing grid/flex-wrap breakpoints (7→4→2 tile columns, chart cards
wrapping to their own row); this step adds the missing phone-width step,
the dashboard's own scroll behaviour, and the one place (the table) that
genuinely needed its own horizontal scroller rather than a reflow.
Nothing here touches the dashboard's data/JS logic — CSS/XML only.
Applied with a module upgrade (zero errors) and a live server restart so
the updated static assets are actually served.

---

## Step 39 — Added real backend data so the dashboard isn't sparse (no code changes)

**What:** No code/view changes — added real records directly to the
`csl_solar_epc_test` database (via `odoo shell`, not `demo/epc_demo.xml`,
so it took effect immediately with no reinstall) to fill in the parts of
the dashboard that were sitting at 0 or showing only one bar:
- 3 new leads (Sunrise Apartments, Green Valley Textiles, Coastal Foods
  Pvt Ltd), each carried to a different pending-approval stage — a
  submitted Site Survey, an approved-survey-with-submitted-Feasibility,
  and an approved-survey-and-feasibility-with-submitted-BOQ — so "Site
  Surveys", "Feasibility Studies" and "BOQs Pending Approval" on the
  Pipeline Activity chart aren't stuck at 0.
- 2 new Material Requests (`to_submit` / `submitted`) on two existing
  active projects — feeds both "Material Requests" on Pipeline Activity
  and the "Pending Material Requests" KPI tile (same domain, both moved
  0 → 2).
- 1 new approved Commissioning on project 19 (Metro Textiles, S00039)
  with no Handover created for it — so the Portfolio by Phase donut
  shows a real "Commissioned" slice (was 0) instead of only Execution/
  Handed Over/Under AMC.
- 4 new Purchase Orders (linked to real projects, real order lines) at
  draft/sent/to approve/done, so the Procurement Status chart shows all
  5 stages instead of one big "Purchase Order" bar and nothing else.

**Why:** Asked for directly — the dashboard looked empty in several
spots even though it was rendering correctly; it needed more real data
behind it, added from the backend rather than the module's demo fixture.

**Impact:** Every new record was created with the same required fields
and approval-mixin conventions as the existing data (proper sequence
numbers, real product/partner/project references) — nothing orphaned or
fabricated to look right only in the dashboard. Verified by re-calling
`epc.dashboard.get_dashboard_data()` both in `odoo shell` and over real
HTTP against the live server: `pending_material_requests` 0→2,
`portfolio_phase` counts `[2,1,5,3]` (Commissioned now populated),
`pipeline_activity` counts `[1,2,1,2,2]` (all five stages now non-zero),
`procurement_status` counts `[1,1,1,9,1]` (all five RFQ→Locked stages
now non-zero). Also read back every new record's `display_name` and ran
`get_views` on the affected models to confirm nothing errors when
opened. No module upgrade or server restart needed — this was pure data,
already live in the same database the running server reads from.

---

## Step 40 — More dashboard data, fixed a black-bar chart bug, "RFQ Sent" colour

**What:** Follow-up round on the dashboard:
1. Found and fixed a real bug while doing the color change: the palette
   in `static/src/js/epc_dashboard.js` (`CHART_COLORS`) never actually
   defined a `warn` key, so both the Procurement Status chart's "RFQ
   Sent" bar and the AMC Contract Health chart's "Expired" bar were
   silently falling back to Chart.js's default black whenever their
   count went above 0 — that's why "RFQ Sent" rendered black. Fixed by
   adding a real `sentLight` (light sky blue, `#7ec8e3`) colour for RFQ
   Sent, and reusing the existing amber `pending` colour for "Expired"
   (same latent bug, same fix, fixed proactively before it ever showed
   up in a screenshot the way RFQ Sent did).
2. Added more real backend data (again via `odoo shell`, not
   `demo/epc_demo.xml`): 9 more Purchase Orders (3 more each at RFQ /
   RFQ Sent / Locked) so those bars are properly visible next to the
   Purchase Order bar, and 3 more complete project chains (lead → survey
   → feasibility → BOQ → project → commissioning → handover → an active
   AMC contract with its own `next_service_date`) — Horizon Retail Park,
   Blue Ridge Dairy, Palm Grove Resorts.

**Why:** Asked for directly — more data for RFQ/RFQ Sent/Locked, more
completed projects, more Upcoming AMC Preventive Services rows, and the
RFQ Sent bar's colour fixed.

**Impact:** `pending_material_requests`/other counts from Step 39
unaffected; new counts confirmed over real HTTP against the live
server: Completed Projects 8→11, Active AMC Contracts 3→6, Procurement
Status `[4,4,1,9,4]` (was `[1,1,1,9,1]`), Portfolio by Phase
`[2,1,5,6]` (the 3 new projects landed in "Under AMC", since they got
both an approved Handover and an active AMC contract), and Upcoming AMC
Preventive Services now lists 6 rows instead of 3, correctly sorted by
next service date. Confirmed the fixed JS bundle is actually being
served (`sentLight` present, no remaining `CHART_COLORS.warn`
reference) and the server is alive. Applied with a module upgrade (zero
errors) and two live server restarts (one per JS edit).

---

## Step 41 — O&M / AMC Report redesigned ("Solar Bold Brand")

**What:** Restyled the O&M / AMC Report's QWeb template
(`epc_report_amc_template` in `views/epc_reports_board.xml`) — a
sunrise-gradient title banner, a 4-tile KPI strip (Total Contracts,
Active, Contract Value, Next Service Due), and the contract table with
colour-coded status badges (Active green / Draft grey / Terminated red
/ Expired amber) and right-aligned, bold monetary values. Everything is
scoped under one `.o_epc_amc_report` wrapper with its own `<style>`
block so it can't affect any other report. The KPI numbers and every
table cell are computed from the exact same `epc.amc.contract` recordset
and fields as before (`project_id`, `name`, `partner_id`, `start_date`,
`end_date`, `state`, `next_service_date`, `contract_value`) — no field,
column, or underlying value changed, only how they're presented.

**Why:** Asked for directly — five design directions were mocked up in
an artifact first (Corporate Ledger, Scandinavian Minimal, Ops
Dashboard, Formal Ledger, Solar Bold Brand) using the report's own real
data, and "Solar Bold Brand" was the one picked.

**Impact:** Verified via `odoo shell` by rendering the actual report
template (`_render_qweb_html`) with no filters: the banner, KPI strip
and badge classes all render, and the KPI numbers match hand-computed
totals exactly (8 contracts, 6 active, $372,950.00 total value) — same
totals as Step 40's verification, confirming no data changed, only
presentation. Applied with a module upgrade (zero errors) and a live
server restart.

---

## Step 42 — O&M / AMC Report now draws its own branded header/footer

**What:** Step 41's redesign left Odoo's own default plain logo/address
header and contact-info footer (from `web.external_layout`) sitting
above and below the new gradient banner, looking disconnected from it.
Switched this one report's `t-call` from `web.external_layout` to
`web.basic_layout` (which draws no header/footer of its own) and built
the company logo, name, address, phone, email and website directly into
the "Solar Bold Brand" design instead: the logo (or a 2-letter fallback
mark if none is set) plus company name/address now sit inside the top
of the gradient banner itself, and a matching light contact-info strip
now sits below the table as the report's own footer. All pulled from
the exact same `res.company` fields (`logo`, `name`, `street`,
`street2`, `city`, `state_id`, `zip`, `country_id`, `phone`, `email`,
`website`) the default layout would have used — nothing invented.

**Why:** Asked for directly — "add header footer also the company
address logo etc" for this report, once the mismatch between the new
banner and the old plain header/footer became visible.

**Impact:** Scoped to this one report only (`epc_report_amc_template`)
— every other report still uses `web.external_layout` and is
unaffected. Verified via `odoo shell` by rendering the actual template:
the real company logo renders as a base64 image inside the banner, the
name/address block matches the company's real address exactly
("My Company (San Francisco)", "250 Executive Park Blvd, Suite 3400",
"San Francisco CA 94134", "United States" — including the state code,
fixed after a first pass that was missing it), and the footer shows the
real phone/email/website. Applied with two module upgrades (zero
errors, the second for the missing-state fix) and a live server
restart.

---

## Step 43 — "Solar Bold Brand" applied to all 7 reports

**What:** Extended the O&M/AMC Report's redesign (Steps 41-42) to every
other report in `views/epc_reports_board.xml` — Procurement, Inventory,
DPR Report, "Download Today's Report", and Quality Report, plus Billing
& Collection Report. To do this without copy-pasting the same large CSS
block and header/footer markup into 6 more templates, pulled the shared
pieces out into three small reusable templates that every report now
`t-call`s:
- `epc_report_style` — the one shared `<style>` block (renamed classes
  from `o_epc_amc_*` to generic `o_epc_report_*`, and added a small
  5-colour badge system — `o_epc_badge_pass/info/warn/fail/neutral` —
  reused by every report's status column instead of a bespoke palette
  per report).
- `epc_report_header` — the gradient banner with company logo/name/
  address plus that report's own `title`/`subtitle` (set via `t-set`
  just before calling it).
- `epc_report_footer` — the phone/email/website contact strip.

Each report also got a small KPI strip relevant to its own data
(Procurement: Total/Confirmed/Pending Approval/Total Amount; Inventory:
Total Transfers/Done/In Progress/Projects Covered; DPR: Projects Active
Today/Timesheet Entries/Total Hours; Quality: Total/Passed/Failed/
Pending; Billing: Total Invoices/Total Billed/Collected/Outstanding;
AMC: unchanged from Step 41) and its status-like column now renders as
a colour-coded badge via a small `badge_map` dict mapping that model's
own state values to one of the 5 shared colours (e.g. Purchase Order
`purchase`/`done` → info/pass, `to approve` → warn, `cancel` → fail).
No field, domain, or underlying value changed on any report — same
`env[...].search(...)` calls as before, same columns, just restyled and
reformatted (e.g. `not_paid` → "Not paid").

**Why:** Asked for directly — "this layout is good and perfect do this
for other reports as well."

**Impact:** Verified via `odoo shell` by rendering all 7 report actions
(the six from the Reporting menu plus the project-level "Download
Today's Report" instant action) with `_render_qweb_html` — all render
with zero errors and every one includes the shared banner and footer.
Spot-checked two reports' numbers against hand-computed totals to
confirm no data changed: Procurement (22 orders, 13 confirmed, 5 pending
approval, $2,459,085.25 total — matches exactly) and Quality (20 checks,
16 pass, 2 fail, 2 pending — matches exactly). Applied with a module
upgrade (zero errors) and a live server restart.

---

## Step 44 — Commissioning Certificate redesigned ("Premium Seal")

**What:** Restyled the Commissioning Certificate PDF
(`epc_commissioning_certificate_template` in
`report/epc_commissioning_report.xml`) — a cream parchment page inside a
double gold rule border, a circular gold seal mark, formal serif
typography, the certification statement, a facts table (Certificate No.,
Project, System Capacity, Commissioning Date, Verified Generation), the
three pass/fail checklist items as ✓/✗ marks, an (only-if-filled-in)
"Checklist Notes" section for `commissioning_checklist`'s free text, and
the same blank signature lines as before. Picked from 5 design options
mocked up in an artifact first ("Classic Diploma", "Modern Minimalist",
"Solar Bold Brand", "Technical/Compliance", "Premium Seal" — this one).
No field or value changed — same `doc.name`, `project_id`, `partner_id`,
`capacity_kw`, `commissioning_date`, `generation_verification_kwh`,
`system_testing_done`/`customer_walkthrough_done`/`customer_approved`,
and `commissioning_checklist` as before.

Two things specific to this report, different from the other 6 (which
are all `qweb-html` previewed in the browser): this one is `qweb-pdf` —
actually rendered server-side by this machine's wkhtmltopdf binary,
confirmed **unpatched** (seen in a prior log warning) — so the CSS was
kept deliberately conservative (solid colours, no gradients, no
flexbox/grid, table-based signature layout) rather than reusing the
gradient-banner approach from the other reports. It also switched from
`web.external_layout` to `web.basic_layout` (no company letterhead) to
match the approved design exactly — real certificates don't carry one
either. That surfaced a real cosmetic bug: the default company
paperformat reserves ~52mm at the top of the page for a logo header,
which left the certificate floating in a large empty gap once that
header was removed — fixed by adding a dedicated
`epc_commissioning_certificate_paperformat` (15mm margins, no header
spacing) and assigning it to this one report action via
`paperformat_id`.

**Why:** Asked for directly — "improve this report also give me the
artifact first... do the premium seal one."

**Impact:** Scoped to this one report only — every other report is
untouched. Verified by actually generating the real PDF (not just the
HTML preview) via `_render_qweb_pdf` against a real approved
commissioning record (`COM/2026/00019`, Aka Foster, S00050) and reading
it back: renders cleanly through the real unpatched wkhtmltopdf binary
with no errors, the seal/border/facts/checklist/signatures all appear
correctly, and after the paperformat fix the certificate sits properly
near the top of the page instead of in a large empty gap. Applied with
a module upgrade (zero errors) and a live server restart.

---

## Step 45 — Two more "proceed to the next stage" chain buttons

**What:** Two new pre-filled shortcut buttons, matching the pattern
already used for "New Material Request" and the incoming-QC/Final-QC
"Log Quality Check" buttons earlier this session:
1. **Project form → "Proceed to Commissioning"**: shows once every task
   on the project is actually finished (`epc_all_tasks_done`, a new
   compute field on `project.project`) and no Commissioning record
   exists for it yet (`commissioning_count == 0`). Opens a blank
   Commissioning form with `default_project_id` already set.
2. **Commissioning form → "Proceed to Handover"**: shows once a
   commissioning is approved and its project has no Handover & Closure
   record yet (`epc_needs_handover`, a new compute field on
   `epc.commissioning`). Opens a blank Handover form with
   `default_project_id` already set (the form's own `partner_id` is
   already a `related='project_id.partner_id'` field, so the customer
   fills in automatically too).

**Why:** Asked for directly — "make everything connected through
chains, no break," continuing the pattern used for procurement and
quality-check earlier.

**Impact:** Caught a real bug while building `epc_all_tasks_done`: the
obvious approach (checking `project.task_ids`) is wrong, because that
field's own domain (`[('is_closed', '=', False)]`, in Odoo's own
`project` module) excludes closed tasks — so it goes *empty* the moment
every task is actually done, making a naive `bool(task_ids) and
all(task_ids.mapped('is_closed'))` check permanently False exactly when
it should be True. Fixed by searching `project.task` directly by
`project_id` instead of using that field. Verified via `odoo shell`
against the real project from the screenshots (Aka Foster, S00050):
with its one task done, `epc_all_tasks_done` is `True`; after adding a
second, still-open task to the same project (then rolled back, not
left in the DB), it correctly flips back to `False`; a project with
zero tasks correctly reads `False` too. Also confirmed
`epc_needs_handover` is `False` for that project's commissioning since
it already has a real Handover record (COM/2026/00019 → HO already
exists), so the button correctly doesn't invite a duplicate. Both forms'
`get_view()` render with no errors. Applied with a module upgrade (zero
errors) and a live server restart.
