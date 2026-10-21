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
