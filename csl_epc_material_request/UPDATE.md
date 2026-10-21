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

### Update 5 (2026-10-19) — Material Requests dashboard
**What was added:** a **Dashboard** menu entry (first entry of the app, so the app now opens on it) with live KPI tiles, charts and a table that are specific to this stage and do not repeat what the main Solar Dashboard already shows.

- KPIs: lines short on stock, fulfilment rate (issued / required), request approval time, quantity still to order, quantity issued to site.
- Charts: required vs in stock vs ordered vs issued (top 6 products), issue status, vendors by quantity ordered, requests per month, fulfilment by project.
- Table: items short on stock.
- The quantity columns on request lines are computed fields, so these figures are summed in Python from the live records.

**Files:** `models/epc_stage_dashboard.py` (builds the numbers, method `_dashboard_material`), `views/epc_dashboard_views.xml` (client action + menu), `__manifest__.py` (loads the view). The screen itself (OWL component, template, styles) is shared and lives in `csl_epc_core`.

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

### Update 6 (2026-10-19) — drill-down lists for the dashboard
**Problem:** clicking a dashboard tile or bar for lines short on stock, products, vendors, project fulfilment opened a list showing only the record ID, because `epc.material.request.line` had no list view of its own.
**Fix:** added list, form (read-only) and search views for `epc.material.request.line` in `views/epc_dashboard_views.xml` (no new menu, nothing else changes). The list is read-only (no create/delete), can be grouped, and shows the useful columns.
**Upgrade:** `-u csl_epc_material_request`.

### Update 7 (2026-10-19) — dashboard colour
The dashboard's accent colour in `models/epc_stage_dashboard.py` is now a light pastel to match the new shared look (see `csl_epc_core/UPDATE.md`, Update 7). No functional change.

### Update 10 (2026-10-21) — axis headings on the dashboard charts
Every bar, line and scatter chart on this dashboard now shows a heading on each axis (for example "Number of handovers" / "Document"), set in `models/epc_stage_dashboard.py` through `_axis_titles`. Doughnut charts have no axes. Upgrade: `-u csl_epc_core,csl_epc_<this module>`.

### Update 11 (2026-10-21) — material already sent to site is no longer counted as "short"
**Problem:** *Quantity To Purchase* and *Still To Order* were worked out as required minus the stock on hand **now**. Once material was issued to the project site, the warehouse stock dropped, so the line looked short again and the app wanted to buy it a second time. In the demo data 46 of the 60 "short" lines had already been fully issued (e.g. MR/2026/00028 DC cable: 1,074 required, 1,074 issued, still 83 "to order").
**Fix:** a line's shortfall is now **required − already issued − stock on hand** (never below 0), and *Still To Order* is that shortfall minus what is on purchase orders. This changes the *Lines short on stock* tile, the purchase-order suggestion on the request, and the *Material Request* form figures. A helper `_issued_quantity()` in `models/epc_material_request.py` is shared by the three computed fields. The lines list now shows *Quantity Issued* next to *On Hand* and has **Total** footers on Issued, To Purchase and Still To Order. Files: `models/epc_material_request.py`, `views/epc_dashboard_views.xml`. Upgrade: `-u csl_epc_material_request`.

### Update 12 (2026-10-21) — easier-to-read lines list
The list behind the Material Request tiles (one list serves every tile) now has a **Fulfilled (%)** column — issued ÷ required for each line, so a fully issued line reads 100 and an untouched one 0 — which makes the *Fulfilment rate* tile easy to read line by line. *Quantity On Hand* and *Quantity Ordered* are hidden by default (tick them in the column picker); Required, Issued, Fulfilled %, To Purchase and Still To Order stay visible. New non-stored field `fulfilled_percent` in `models/epc_material_request.py`; list in `views/epc_dashboard_views.xml`. Upgrade: `-u csl_epc_material_request`.

### Update 13 (2026-10-21) — "Request approval time" can be checked in the list
**Problem:** the tile (average days from "Submit for Approval" to "Approve") opened a list of approved requests with no dates, so the average could not be seen or checked.
**Fix:** the Material Requests list now shows **Submitted On**, **Approved On** and **Days to Approve** (with an **Average** at the foot equal to the tile). The tile opens only approved requests that have both dates, the same set the average is taken over. New non-stored field `approval_days` in `models/epc_material_request.py`; list in `views/epc_material_request_views.xml`; tile domain in `models/epc_stage_dashboard.py`. Upgrade: `-u csl_epc_material_request`.

### Update 14 (2026-10-21) — "Items short on stock" shows what is left to buy
The dashboard table showed the shortfall before purchase orders were taken off, so a line needing 720 with 400 already ordered still read "To buy 720". It now has an **On order** column and **To buy** shows what is still left after orders (the *Still To Order* figure of the lines list; a line fully covered by an order shows 0 in green). The table still lists the lines short of stock. File: `models/epc_stage_dashboard.py`. Restart the server (Python change) — no module upgrade needed.

### Update 15 (2026-10-21) — "Still To Order" on the request form
The lines on the Material Request form showed *Quantity To Purchase* (the shortfall before purchase orders) and *Quantity Ordered* but not what is left to order, so a line needing 720 with 400 ordered still looked like 720. The form now also shows **Still To Order** (320 in that example) — the amount the *Create Purchase Orders* button will actually order. File: `views/epc_material_request_views.xml`. Upgrade: `-u csl_epc_material_request`.

### Update 16 (2026-10-21) — goods already received are no longer counted as "on order"
**Problem:** a line needing 720 with a purchase order for 400 that had been **received and validated** showed *To buy 0*: the 400 were counted in stock (they were now in the warehouse) and again as "on order", so the shortfall was hidden.
**Fix:** *Quantity Ordered* now counts only the part of a purchase order that has **not arrived yet** (ordered − received, never below 0). Received goods count only as stock. Example: 720 required, 400 ordered and received, 388 free in the warehouse → on order 0, still to order 332. Open orders not yet received count in full, as before. This changes *Quantity Ordered*, *Still To Order*, the dashboard's *On order* / *To buy* columns, the *Still to order* tile and what *Create Purchase Orders* orders. File: `models/epc_material_request.py`. Upgrade: `-u csl_epc_material_request`.

### Update 17 (2026-10-21) — "Pending requests" tile replaces "Still to order"
The *Still to order* tile (units still not on a purchase order) was removed from the Material Request dashboard and replaced by **Pending requests**: how many material requests are not approved yet (To Submit or Submitted for Approval). It is the same count as *Pending Material Requests* on the main Solar Dashboard, and clicking it opens those requests. The still-to-order quantity is still available per line (*Still To Order* column of the lines list and the request form) and in the *Items short on stock* table. File: `models/epc_stage_dashboard.py`. Restart the server (Python change) — no module upgrade needed.
