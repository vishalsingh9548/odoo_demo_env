# UPDATE — csl_solar_epc (Solar Dashboard — the parent module)

> Part of the Solar EPC split. The module you install. Its displayed name is **Solar Dashboard** (technical name still `csl_solar_epc`). Installing it installs all nine sub-modules.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
The parent now keeps only what spans every stage:
- **Dashboard** (`epc.dashboard` + the OWL screen in `static/`): live KPIs, portfolio phase, pipeline activity, AMC health, procurement status, upcoming services — each click-through.
- **Reporting**: Procurement, Inventory, DPR, Quality, Billing & Collection and O&M/AMC PDF reports, and *Download Today's Report* button on the project (daily progress PDF from timesheets).
- **Demo data** (`demo/epc_demo.xml`): one lead taken all the way from survey to AMC, so the app can be explored without entering data.

## Dependencies
`csl_epc_core`, `csl_epc_site_survey`, `csl_epc_feasibility`, `csl_epc_boq`, `csl_epc_material_request`, `csl_epc_quality`, `csl_epc_handover`, `csl_epc_commissioning`, `csl_epc_amc`.

## Views, menus and screens
- `views/project_project_views.xml` — the *Download Today's Report* button.
- `views/epc_reports_board.xml` — report actions/templates and the dashboard client action.

- Root menu **Solar Dashboard** (defined in core) with: *Dashboard*, *Reporting* (6 reports), and *Configuration*.
- Each stage's own app icon comes from its sub-module.

## Data and security
No data other than demo.

No access rules of its own (each module protects its models).

## What was moved / changed compared to the original single module
Remains here: `models/epc_dashboard.py`, a small `project_project.py` (print today's DPR), dashboard assets, reports board, menus, demo data, README/LOG/DEMOVALUES docs. Everything else was moved out into the sub-modules (see their UPDATE.md files).

**Edits made to what stayed here:**
- `__manifest__.py`: name changed to **Solar Dashboard**; `depends` is now the nine sub-modules only; `data` shrank to three view files; demo and assets kept.
- `epc_menus.xml`: only Dashboard and Reporting remain, now parented to `csl_epc_core.menu_epc_root`.
- `epc_dashboard.py`: group check now uses `csl_epc_core.group_epc_user`.
- `epc_demo.xml`: external IDs now carry the module prefix for records that moved (`csl_epc_amc.epc_helpdesk_team`, `csl_epc_quality...`).

## Impact
- Home screen now shows **one icon per stage** (Site Surveys, Feasibility, BOQ & Costing, Material Requests, Quality Checks, Commissioning, Handover & Closure, AMC Contracts) plus **Solar Dashboard**.
- Installing the parent installs the whole stack; individual stages can be installed alone only if their dependencies allow it (see each module's dependencies).

## Overall module map

```
csl_epc_core ─┬─ csl_epc_site_survey ─ csl_epc_feasibility ─ csl_epc_boq ─ csl_epc_material_request
              ├─ csl_epc_quality ───────┐
              ├─ csl_epc_handover ──────┴─ csl_epc_commissioning
              └─ csl_epc_amc
csl_solar_epc (Solar Dashboard) depends on all of the above
```

## Testing that was done
- Fresh database install of `csl_solar_epc` with demo data: all ten modules installed, no errors.
- Every list/form view of the EPC models and of the extended standard models (CRM lead, project, sale order, purchase order, stock picking, helpdesk ticket, task) loaded.
- Flow checked on demo data: lead → survey → feasibility → BOQ → project (BOQ attached on creation) → material request → commissioning action; dashboard returns data for the admin user.
- After the home-screen icon change the modules were upgraded on a database with no errors.

## Known environment note (not caused by this change)
If a database's admin time zone is saved as `Asia/Calcutta`, PostgreSQL here does not recognise that old name and the CRM pipeline fails. Set the time zone to `Asia/Kolkata` right after first login, before installing apps.

## Git note
The repo root is `odoo_demo_env/`. Stage the whole set with:
`git add -A csl_solar_epc csl_epc_*` from that folder; running `git add .` inside `csl_solar_epc/` misses the sibling modules.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Automated tests (F23):** `tests/test_epc_flow.py` — 23 tests walking the pipeline and every fix above (full lead→project flow, approval guards, switches, quotation checks, revisions, per-vendor POs, double-issue guard, commissioning switches, AMC job, Field User visibility, Consume Site Stock cases). They live in the parent because it depends on every stage. Run with `--test-enable --test-tags=/csl_solar_epc`.
- No functional change to the dashboard or reports.

### Settings
All switches are in *Solar Dashboard → Configuration → Settings* (core module). Defaults: everything stricter is OFF; notifications are ON; approval permission checks and Field User own-records visibility are always ON.

### Not done in this round (still in the plan)
A2 phase 2 (accepted/rejected quantity and return-to-vendor on incoming QC), C14 (auto-marking milestones, billing link), C15 (site checklist linked to tasks), F24 (DPR approval/reminder/multi-photo), E21 SLA link and default warranty date, a lot/serial pre-check on *Issue to Project*, multi-company, AMC invoicing.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

### Update 3
Tests now total 27 (added: failed check logged with reason, EPC order has no delivery while a plain order keeps its delivery, failed check saved by a real user). All pass.

---

## Update 5 (2026-10-19) — stage dashboards and tests
- Each stage app now has its own **Dashboard** (Site Survey, Feasibility, BOQ, Material Request, Quality, Commissioning, Handover, AMC). See the `UPDATE.md` of each module for what it shows; the shared screen is described in `csl_epc_core/UPDATE.md`.
- The main **Solar Dashboard** of this module is unchanged. The stage dashboards were designed to show different numbers from it (it keeps portfolio phase, pipeline counts, AMC status, procurement status, upcoming AMC visits).
- New tests in `tests/test_epc_dashboards.py`: every stage returns a complete JSON-safe payload for a manager and a field user; every count tile and count chart equals the size of the list it opens; the dashboard follows live data (creating a survey raises the count); users without EPC access are refused; an unknown stage is refused.
- Run: `odoo-bin -d <db> -u csl_solar_epc --test-enable --test-tags=/csl_solar_epc --stop-after-init`

---

## Update 6 (2026-10-19) — main Solar Dashboard: new look and dark mode
The main **Solar Dashboard** (tiles, Portfolio by Phase, Pipeline Activity, AMC Contract Health, Procurement Status, upcoming AMC visits) now matches the stage dashboards.
- **Look:** white page with soft colour blobs behind frosted-glass tiles and cards; one cool pastel palette (sky blue, periwinkle, lavender) instead of green/red/amber. Meaning is carried by shade and by the label.
- **Dark mode:** follows Odoo's own light/dark switch (user menu). Dark glass on a navy page, brighter chart colours; tables are transparent so the dark theme no longer shows white/black stripes.
- **Files:** `static/src/scss/epc_dashboard.scss` (colours became variables, `.o_epc_dark` override), `static/src/js/epc_dashboard.js` (light/dark chart palettes, reads the `color_scheme` cookie), `static/src/xml/epc_dashboard.xml` (adds the dark class). No change to the numbers, click-through or layout.
- **Upgrade:** `-u csl_solar_epc`, then hard-refresh (Ctrl+Shift+R).

### Update 7 (2026-10-19) — legend text colour
The AMC Contract Health legend (and the Portfolio legend) showed black text on the dark background because the legend colour was not set. It now uses the theme's text colour in both light and dark mode. File: `static/src/js/epc_dashboard.js`. Upgrade: `-u csl_solar_epc`, hard-refresh.

### Update 8 (2026-10-21) — axis headings on the charts
The bar charts now have headings on their axes (Pipeline Activity: "Open items" / "Pipeline stage"; Procurement Status: "Purchase order stage" / "Purchase orders"). The doughnut and funnel charts have no axes. File: `static/src/js/epc_dashboard.js`. Upgrade: `-u csl_solar_epc`, hard-refresh.

### Update 9 (2026-10-21) — "Contract Value" tile is now clickable
**Problem:** the *Contract Value* tile on the Solar Dashboard did nothing when clicked, unlike the other tiles.
**Fix:** it now opens the list of projects it adds up (every project that has a BOQ, 15 at the moment), and that list has **BOQ**, **System Capacity** and **Contract Value** columns with a **Total** at the foot equal to the tile. The figure itself is unchanged: the sell price of the BOQ linked to each project. Files: `models/epc_dashboard.py`, `static/src/xml/epc_dashboard.xml`; the list columns are in `csl_epc_boq` (see its Update 16). Upgrade: `-u csl_epc_boq,csl_solar_epc`.

### Update 10 (2026-10-29) — CRM access error fixed (changes are in the sub-modules)
**Problem:** a user without any Solar EPC group got an *Access Error* on `epc.site.survey` when opening CRM, caused by the survey, feasibility and BOQ counts added to the CRM lead.
**Fix:** those fields are now restricted to `csl_epc_core.group_epc_user` (see Update 13 in `csl_epc_site_survey`, Update 14 in `csl_epc_feasibility` and Update 17 in `csl_epc_boq`). No change in this module itself.

**Also (database clean-up on `solar_epc_v2`):** the stale module `csl_ai_assistant` (not in the addons path) was uninstalled, because its leftover Settings view referenced the missing field `csl_ai_sqft_per_kw` and crashed the Settings page.

Upgrade: `-u csl_epc_site_survey,csl_epc_feasibility,csl_epc_boq`, then restart the server.


---

# UPDATE — csl_solar_epc (Solar Dashboard) — gap modules added

> 2026-11-18. Summary of the whole "gap closing" round (competitor comparison with Entrivis Solar EPC). Details are in each new module's own `UPDATE.md`.

## What was changed in THIS folder
- ~~`__manifest__.py`: six modules added to `depends`~~ **REVERTED (see Uninstall below)**: six modules had been added to `depends` (`csl_epc_dealer`, `csl_epc_design`, `csl_epc_documents`, `csl_epc_subsidy`, `csl_epc_net_metering`, `csl_epc_billing`).
  - **Why:** so a fresh install of "Solar Dashboard" installs the whole set.
  - **Impact:** none on a running database until `csl_solar_epc` is upgraded; then Odoo installs any of the six still missing. On `solar_epc_v2` they are already installed.
- Nothing else in this module (views, dashboard, reports, demo data) was touched.

## New modules (all additive, no existing file edited)
| Module | Closes gap | Existing behaviour touched |
|---|---|---|
| csl_epc_dealer | DISCOM, consumer number, dealer / sub-dealer | none (new fields by view inheritance) |
| csl_epc_design | System Design stage | none unless switch *Require Approved Design Before BOQ* is turned on |
| csl_epc_documents | Government document pack | extends order confirmation (adds documents) and, only with its switch on, commissioning submit |
| csl_epc_subsidy | Subsidy schemes and applications | extends order confirmation (adds a Draft application when a scheme fits) |
| csl_epc_net_metering | Net-metering tracking | handover approval check only with its switch on; one daily reminder job |
| csl_epc_billing | Stage-wise payment plan and draft invoices | only orders that have a Payment Plan |

No file in `csl_epc_core`, `csl_epc_boq`, `csl_epc_feasibility`, `csl_epc_commissioning`, `csl_epc_handover` etc. was edited. New code hooks into them by Odoo inheritance and always calls the original method first.

## How it was verified
1. Full database backup before starting: `/home/csl/Desktop/odoo_18/backups/solar_epc_v2_before_gap_modules.sql.gz`.
2. Installed on a throw-away copy of `solar_epc_v2` first, then ran a full scenario there: lead with DISCOM/dealer → survey → feasibility → design (with warnings) → BOQ → quotation → confirm → project, 8 documents, subsidy application, advance draft invoice → documents flow and printable form → subsidy flow → net metering flow → installation / commissioning / handover triggering invoices → retention scheduled 90 days and raised by the daily job → delivery trigger on a stock order → a plain order with no plan stays untouched.
3. Installed on `solar_epc_v2` with no errors; the running server reloaded and the login page answers 200. The test copy was deleted.

## Things found while testing and what was done
- The *Overdue* filter on Project Documents used an unsearchable field → fixed (uses the due date directly).
- Dealer full-name field now declared recursive (removes a framework warning).
- *Customer pays after subsidy* is now never below zero.
- Your existing **Strict BOQ Check** (on in `solar_epc_v2`) needs a product on every BOQ line. A BOQ created from a design has the lines but no products, so the engineer must pick them before *Create Quotation* — expected, not a bug.
- Your existing commissioning / handover requirement switches still apply (customer approval, certificate, handover documents); the new modules do not bypass them.
- Not covered by an automatic test: screens were not clicked through in a browser (only models, flows and view validation on install).

## Rollback
Uninstall the six modules from Apps (newest first: billing, net metering, subsidy, documents, design, dealer), or restore the backup above. Removing them deletes only their own data and fields.

## Icons and home-screen tiles for the six new modules (2026-11-18)
Each new module has `static/description/icon.png` and its own top-level menu (tiles: Dealers & DISCOM, System Design, Project Documents, Subsidy, Net Metering, Milestone Billing), matching the existing stage modules. Menus and icons only, no behaviour change. The six modules were upgraded on `solar_epc_v2` so Apps and the home screen show the icons.


## Uninstall of the six new modules (2026-11-18) — manual install later
The owner asked to uninstall all six and install them one by one by hand.
- The `depends` edit above was **reverted**, so Solar Dashboard no longer pulls the new modules in and they are fully optional.
- **Incident:** uninstalling the six also uninstalled `csl_solar_epc` itself, because the database had already recorded the edited dependency list. It was reinstalled straight away. Verified against the pre-install backup: record counts of leads, orders, projects, tasks, milestones, surveys, feasibility, BOQs, material requests, DPRs, quality checks, commissioning, handovers, AMC contracts, partners, invoices, pickings, views, menus and actions are identical. Only internal reference-table counts of base/mail modules differ slightly (Odoo reload metadata, harmless).
- All tables and columns of the six modules are gone (`epc_design`, `epc_dealer`, `epc_discom`, `epc_subsidy_*`, `epc_net_meter`, `epc_order_milestone`, `epc_project_document`, `epc_payment_plan*`, and the new fields on the lead). Nothing had been entered in them (only rolled-back tests).
- The module folders, code and `UPDATE.md` files are kept for installing later.
- Lesson: do not add optional modules to a parent's `depends` on a running database.

## Install order (one by one, from Apps; remove the "Apps" filter and search "CSL Solar EPC")
1. CSL Solar EPC - DISCOM & Dealer (`csl_epc_dealer`)
2. CSL Solar EPC - System Design (`csl_epc_design`) — independent, can go anywhere
3. CSL Solar EPC - Government Document Pack (`csl_epc_documents`) — needs 1
4. CSL Solar EPC - Subsidy (`csl_epc_subsidy`) — needs 3
5. CSL Solar EPC - Net Metering (`csl_epc_net_metering`) — needs 3
6. CSL Solar EPC - Milestone Billing (`csl_epc_billing`) — independent, can go anywhere

## Starter data added inside the optional modules (2026-11-18)
DISCOM list (`csl_epc_dealer`), PM Surya Ghar scheme (`csl_epc_subsidy`), two payment plans (`csl_epc_billing`) and 4 extra document templates (`csl_epc_documents`) now ship in each module's `data/` folder and load on install. See each module's UPDATE.md. Rule from the owner: modules are installed by the owner on their own instance; nothing is installed or upgraded on it by the assistant.
