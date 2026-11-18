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
