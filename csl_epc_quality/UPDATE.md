# UPDATE — csl_epc_quality (Quality Checks, QC Checkpoints and DPR)

> Part of the Solar EPC split. Stages 10 and 12. Own app icon: **Quality Checks**. **This is custom code, not Odoo's built-in Quality app** — it is the same custom QC that existed in the old module.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Quality Checks** (`epc.quality.check` + lines `epc.quality.check.line`): two categories — *Incoming Material QC* (tied to a receipt) and *Final QC* (before handover). Lines are filled from the configurable checkpoints; the overall result is Pending / Pass / Fail. A passed Final QC can **consume the remaining material at the site** (moves stock to the *Installed / Consumed Material* location).
- **QC Checkpoints** (`epc.quality.checkpoint`): the checklist templates per category, editable under *Configuration → QC Checkpoints*, with starter data.
- **Receipt guard** (`stock.picking` extension): a project's incoming receipt cannot be validated until an Incoming Material QC has been logged against it and has passed. A *Log Quality Check* button on the receipt opens a pre-filled QC form.
- **Daily Progress Reports** (`epc.dpr`): per-project daily report (date, reported by, weather, manpower deployed, work progress summary, material received/consumed, equipment deployed, site photo, issues/risks, tomorrow's plan), with a *DPR* smart button on the project. *(DPR is not quality-related; it lives here because it is Stage-10 site-execution data with no better home. It can be split later.)*
- **Project**: *Daily Progress Reports* and *Quality Checks* smart buttons with counts.

## Dependencies
`csl_epc_core` (and through it `stock`, `hr_timesheet`, projects).

## Views, menus and screens
- `views/epc_quality_check_views.xml`, `views/epc_quality_checkpoint_views.xml`, `views/epc_dpr_views.xml`, `views/stock_picking_views.xml`, `views/project_project_views.xml`.

- Top-level app **Quality Checks** → *Quality Checks*.
- *Configuration → QC Checkpoints* (under the Solar Dashboard app, Administrator only).

## Data and security
Sequences `seq_epc_dpr` (`DPR/<year>/`), `seq_epc_quality_check` (`QC/<year>/`); starter QC checkpoints (`noupdate`); the stock location *Installed / Consumed Material* (`epc_location_consumed`).

`security/ir.model.access.csv` — DPR, quality check, lines: Field User read/write/create; Project Manager full. Checkpoints: Field User read only; Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_quality_check.py`, `epc_quality_checkpoint.py`, `epc_dpr.py`, `stock_picking.py`, their views, data files and sequences, plus the DPR / quality part of `project_project.py`.

**Why a separate module:** you asked for QA to stay as it is. The Commissioning module checks whether a Final QC passed, so the QC models must exist before Commissioning installs; keeping them inside the parent would have created a circular dependency.

**Edits while splitting:**
- The `epc_location_consumed` reference is now `csl_epc_quality.epc_location_consumed`.
- The receipt-blocking message now says "Open the Quality Checks app" (QC is no longer a submenu of Solar EPC).
- DPR/quality project counts have their own compute methods.

## Impact
- QC logic and the receipt guard behave exactly as before.
- **Installing this module changes how project receipts validate** (they require a passed Incoming QC) — same as the original module.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.
