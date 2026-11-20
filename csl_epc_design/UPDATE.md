# UPDATE — csl_epc_design (System Design)

> New module, added 2026-11-18. Gap #2. Own home-screen tile: *System Design*.

## Why this change was made
Panel/inverter selection, strings and the single-line diagram had no home (only tilt, orientation and a layout file in Feasibility). The competitor has a separate design stage with approval.

## What this module does (functionality)
- **System Design** (`epc.design`, sequence `DSG/<year>/00001`) raised from an approved Feasibility Study with the *Create Design* button.
- Inputs: panel make/Wp/count/Vmp/Voc, inverter make/kW/count/MPPT range, strings and panels per string, mounting type, layout drawing, single-line diagram (SLD), yield, tariff, optional estimated cost.
- Calculated: DC capacity, AC capacity, DC/AC ratio, expected yearly generation, yearly savings, payback years.
- **Warnings** (on screen, not blocking): strings × panels ≠ panel count; string Voc above inverter max voltage; string Vmp below MPPT minimum; unusual DC/AC ratio.
- **Approval** reuses the existing `epc.approval.mixin` (To Submit → Submitted → Approved / Rejected), so Submit/Approve/Reject buttons, reject wizard, self-approval and lock switches behave exactly like the other documents.
- **Create BOQ** from an approved design: pre-fills BOQ lines (modules, inverters, mounting structure) and stores `design_id` on the BOQ.
- **Settings switch** *Require Approved Design Before BOQ* (OFF by default).

## Dependencies
`csl_epc_boq` (which brings Feasibility and Core).

## Existing behaviour kept
The existing *Create BOQ* button on Feasibility is unchanged and still works without a design. A design is optional unless the new switch is turned on.

## Files
`models/` epc_design, epc_feasibility (design link/button), epc_boq (`design_id`), epc_config (switch) · `views/` design, feasibility, boq, settings, menus · `security/` access + rules (Field User sees own, Manager all) · `data/design_sequence_data.xml`.

## Impact
- Feasibility form: *Create Design* button and *Designs* smart button added (inherited view).
- BOQ form: *System Design* field shown only when the BOQ came from a design.
- Settings → Solar EPC: new *System Design* block.
- One override: `epc.feasibility._epc_check_ready_for_next_stage` calls the original first, then adds the optional switch check.

## Install / upgrade notes
Install after `csl_epc_boq`. No data migration. Estimated payback needs *Estimated System Cost* filled in; the default yield (1400 kWh/kWp) and tariff (8 per kWh) are only starting values and can be changed per design.

## Tested note
With the existing *Strict BOQ Check* switch on, lines created from a design have no product yet; pick the products (and unit costs) before *Create Quotation*.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **System Design** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Update (2026-11-19) — Mounting-structure line quantity from a design
- `models/epc_design.py` (`action_create_boq`): the *Mounting structure* BOQ line made from an approved design now gets **quantity = the design's DC capacity in kWp** (it was 1; falls back to 1 when the capacity is 0).
- **Why:** the BOQ now fills the unit cost automatically from a per-kWp mounting product (see `csl_epc_boq/UPDATE.md`), so the quantity has to be the kWp for the line total to be right (e.g. 451 kWp x 55 = 24,805, not 55).
- **Impact:** only the quantity of that one generated line; panels and inverter lines are unchanged. Existing BOQs are not touched. Upgrade `csl_epc_design` (and `csl_epc_boq`) to apply.
- **Tested:** a BOQ built from design DSG/2026/00001 (451 kWp) gave mounting quantity 451 and the correct subtotal (rolled back, nothing saved).

## Update (2026-11-19) — Panel and Inverter are now product dropdowns
- New fields `panel_product_id` and `inverter_product_id` (many2one to products) shown as **Panel Make / Model** and **Inverter Make / Model** on the design form. The dropdowns list only products in the categories *Solar EPC / Solar Modules* and *Solar EPC / Inverters* (new categories created by `csl_epc_boq`; put a product in one of them to make it appear).
- Choosing a product fills the old text fields (`panel_make`, `inverter_make`, now hidden but kept so old designs and descriptions still work) and, when the name contains the rating ("550 Wp", "100 kW"), also Panel Rating (Wp) / Inverter Rating (kW). The rating can still be typed over.
- *Create BOQ* now puts the chosen products on the panel and inverter BOQ lines, so the unit cost comes from those products' Cost.
- **Impact:** existing designs keep their typed text (dropdown empty until a product is picked). No data migration. Upgrade `csl_epc_boq` and `csl_epc_design`.
- **Tested:** dropdown lists 1 module and 3 inverters; picking them filled name and rating correctly (rolled back).

## Dashboard (added 2026-11-19)
- **What:** a live **Dashboard** screen for this module, the first entry of its menu, in the same look as the Commissioning and Handover dashboards (design was approved from a preview first). It uses the shared screen in `csl_epc_core`, so this module ships no JavaScript: only `models/epc_stage_dashboard.py` (method `_dashboard_design`), `views/epc_dashboard_views.xml` (screen entry and menu) and one line in `models/__init__.py` and in the manifest.
- **Shows:** Awaiting approval, designs with warnings, designed capacity (approved, DC), average DC/AC ratio, average payback, approved designs that already have a BOQ. Charts: approval pipeline, designs per month, capacity by mounting type, DC/AC spread, payback bands. Table: designs needing attention (warning, rejected, or waiting 5+ days).
- **Clicking** a tile or a chart bar opens the list of exactly the records that were counted. Numbers are read with the logged-in user's own access rights.
- **Reads from:** epc.design. No new fields, no data changes.
- **Impact:** adds one menu entry ("Dashboard") and one client action. Nothing existing is changed; uninstalling the module removes it.
- **Tested:** on a throw-away copy of the database (never on the live one): each dashboard was built empty and with a full scenario, and its result checked to be sendable to the browser. Not yet viewed in a browser.
- **Install / upgrade notes:** the manifest changed, so **restart the Odoo server first**, then *Upgrade* this module (the server keeps each module's file list in memory until it restarts).
