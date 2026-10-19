# UPDATE — csl_epc_material_request (Material Request / Procurement)

> Part of the Solar EPC split. Stage 8A. Own app icon: **Material Requests**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Material Request** (`epc.material.request`) with lines (`epc.material.request.line`: product, description, quantity required, UoM, vendor): per-project request for materials, approval workflow, sequence `MR/<year>/00001`. Each line shows the quantity required against stock on hand and the quantity still to purchase.
- **Pre-filled from the BOQ**: the project's *New Material Request* button copies every BOQ line that has a product into a new request.
- **Create Purchase Order**: opens a new Purchase Order pre-filled with every line that is short of stock (product and quantity to purchase). The vendor is pre-filled only if all those lines name the same vendor; otherwise it is left blank. *Purchase Orders* smart button. Purchase Orders carry a *Material Request* reference for traceability.
- **Issue to project**: moves what is already in stock out of the warehouse to the project's own site stock location (created on demand), as a real stock transfer.
- Confirming a Purchase Order tags its receipts with the order's project.

## Dependencies
`csl_epc_boq`, `purchase`, `project_purchase` (these bring in `stock` and projects through core).

## Views, menus and screens
- `views/epc_material_request_views.xml` — list, form, search, window action.
- `views/purchase_order_views.xml` — *Material Request* field on the PO form.
- `views/project_project_views.xml` — *New Material Request* button and *Material Requests* smart button on the project form.

- Top-level app **Material Requests** → submenu *Material Requests*.

## Data and security
Sequence `seq_epc_material_request`.

`security/ir.model.access.csv` — request and lines: Field User read/write/create (lines also delete); Project Manager full.

## What was moved / changed compared to the original single module
Moved from the old module: `epc_material_request.py`, `purchase_order.py`, their views and sequence, and the Material Request part of `project_project.py` and its view.

**Edits while splitting:** the project's `material_request_count` used to be computed in one shared method together with DPR / quality / commissioning counts. It now has its own compute method here; each module counts its own records. Behaviour is unchanged.

## Impact
- No functional change. Depends on BOQ because the project button reads `boq_id`.
- Purchase and Inventory become required only when this module is installed.

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Purchase orders (D16):** *Create Purchase Orders* now creates one draft RFQ per preferred vendor directly and links each to the request; it can be pressed again while shortfall remains. Lines without a preferred vendor still open as a pre-filled new RFQ (a vendor is mandatory on a PO). The button hides when nothing is left to buy.
- **Issue to project (D17):** new line fields *Quantity Ordered*, *Still To Order*, *Quantity Issued*, *Can Issue Now* and request field **Issue Status** (Nothing / Partly / Fully Issued). Issuing moves only what is not yet issued; pressing it twice no longer sends material twice; the button hides when fully issued.
- **Stock figure (D18):** *Quantity On Hand* is now free stock (on hand minus reserved). On submit, a request that goes beyond the project's BOQ gets a warning in the chatter; optional switch **Block Over-BOQ Requests** makes it a hard stop.
- **Visibility (F22):** Field Users see requests they created or requested; managers see all.

### Why / Impact
Removes duplicate issuing and the one-PO limit. The on-hand number can be lower than before where stock is reserved elsewhere (that is the correct free quantity).

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).

### Update 3
- **"Issue Material to Site" button on the Project form** (header, highlighted): shown while an approved material request of the project still has stock that has not been issued to the site. One click issues every such request (one internal transfer per request) and opens the transfer; the button disappears once everything has been issued. This way the step is no longer forgotten on the request itself. New project field: *Material To Issue*.
