# UPDATE — csl_epc_core (Solar EPC – Core)

> Part of the Solar EPC split. Foundation module. Every other EPC module depends on it (directly or indirectly). Not an app on its own, but it owns the **Solar EPC / Solar Dashboard root menu**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Access groups** (category *Solar EPC*): *Field User* → *Project Manager* → *Administrator* (each implies the previous). The installing admin user is automatically given Administrator.
- **Approval workflow mixin** (`epc.approval.mixin`, abstract): shared by Site Survey, Feasibility, BOQ, Material Request, Commissioning and Handover. Provides the `approval_state` statusbar (To Submit → Submitted for Approval → Approved / Rejected), submit / approve / reject / reset-to-draft actions, and who submitted/approved and when.
- **CRM lead qualification** (`crm.lead` extension): Customer Segment, Proposed Capacity (kW), Monthly Electricity Bill, Roof/Land Type, Site Address, Site Latitude/Longitude, Sanctioned Load, Existing Transformer, Grid Access, Expected Closure Date — shown on the lead/opportunity form in a **Solar Details** tab. Standard CRM is otherwise unchanged.
- **Sale Order extension**: Solar EPC Terms tab (warranty, delivery, freight, payment structure, cancellation policy, certifications, wattage tolerance), an *EPC Project* smart button, and the bridge that **creates a Project automatically when the order is confirmed** (`_epc_create_project`, values come from the new `_epc_project_vals()` hook).
- **Project extension (base part)**: Source Lead, EPC Sales Order link and smart button, Site Address, Scope of Work, project site stock location (`site_location_id` + `_epc_ensure_site_location()`), and seeding of the four default milestones.
- **Project Task extension**: *Solar Site Checklist* tab (civil, structure, module installation, DC/AC cabling, LT panel, earthing, testing & pre-commissioning, each with a done flag and date).

## Dependencies
`mail`, `hr_timesheet`, `crm`, `sale_management`, `sale_project`, `stock`, `project_stock`, `project_enterprise`, `planning`, `account`.

## Views, menus and screens
- `views/crm_lead_views.xml` — Solar Details tab on the CRM lead form.
- `views/sale_order_views.xml` — EPC Project smart button + Solar EPC Terms tab.
- `views/project_project_views.xml` — Sales Order smart button, *Solar EPC* group (Source Lead, EPC Sales Order), Site & Scope group.
- `views/project_task_views.xml` — Solar Site Checklist tab.

- Root menu **Solar Dashboard** (`menu_epc_root`, sequence 45, visible to Field User and above) with the icon `static/description/icon.png`.
- **Configuration** parent menu (`menu_epc_configuration`, Administrator only). Other modules add their configuration screens under it.

## Data and security
No sequences or demo data here.

`security/epc_security.xml` — module category, the three groups, and the grant of Administrator to the admin user. (Per-model access rules live in each module's own `ir.model.access.csv`.)

## What was moved / changed compared to the original single module
Moved here unchanged from the old module: `epc_approval_mixin.py`, `project_task.py`, `views/project_task_views.xml`, `security/epc_security.xml`, the lead qualification fields, the Sale Order terms/project creation, and the base part of `project_project.py`.

**Edits made while splitting (no behaviour change):**
- `crm_lead.py` was split: qualification fields stay here; the Site Survey / Feasibility / BOQ links and buttons moved to their own modules.
- `sale_order.py`: the `boq_id` field moved to `csl_epc_boq`. Project creation now builds its values through a new hook `_epc_project_vals()`, so the BOQ module can add `boq_id` without core knowing about BOQs.
- `project_project.py` and its view were split by stage; this module keeps only the stage-independent parts.
- Group references in all views now read `csl_epc_core.group_epc_*`.

## Impact
- Anything that previously used `csl_solar_epc.group_epc_user/manager/admin` now uses `csl_epc_core.group_epc_*`. Users keep their permissions only if the groups are assigned again on a fresh database.
- Users without the Field User group do not see any Solar EPC app icon.
- The home-screen label of the root menu is now **Solar Dashboard** (was *Solar EPC*).

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- **Settings screen** (new): *Configuration → Settings* shows a **Solar EPC** section with every switch below. Helper model `epc.config` reads them. Switches: Block Self-Approval, Lock Approved Documents, Turn Off Notifications, Stop Work on "Not Feasible", Strict BOQ Check, Failed Items Need a Remark, Lock Finished Quality Checks, Block Over-BOQ Requests, the Commissioning requirements, One Commissioning per Project, the Handover requirements, Create AMC Service Visits Automatically.
- **Approval workflow (`epc.approval.mixin`)** — used by survey, feasibility, BOQ, material request, commissioning, handover:
  - *B6* Approve / Reject now check in Python that the user is a Project Manager or Administrator (not just hidden buttons) and that the document is in the right state (submit from To Submit/Rejected, approve/reject from Submitted). Re-opening an approved document is manager-only.
  - *B6* optional switch **Block Self-Approval**.
  - *B7* optional switch **Lock Approved Documents** (writes to an approved document are refused; approval fields, chatter and a per-model whitelist stay editable; superuser scripts are not affected).
  - *B8* **Notifications**: submitting creates a to-do for the approvers; approving/rejecting messages the submitter (rejection includes the reason and a to-do). Can be switched off.
  - New **Reopen (Reset to Draft)** button (managers) on approved documents.
- **Sale Order**: new **Solar EPC Order** tick (*C11*). Confirming an order creates an EPC Project only for EPC orders (ticked, or created from a BOQ). Ordinary sales orders are left alone. The project values come from `_epc_project_vals()`, the decision from `_epc_should_create_project()`.
- **Menu**: *Configuration → Settings*.

### Why
Close the gaps B6, B7, B8, C11 (and the Reopen path) from the plan, without changing behaviour for anyone who does not switch the new options on.

### Impact
- Approving/rejecting now requires the Project Manager group (intended, B6).
- Sale orders that are neither ticked nor created from a BOQ no longer create a project on confirmation (intended, C11).

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button on every approval form now opens a small dialog (`epc.reject.wizard`) asking for the rejection reason, then rejects with it. `action_reject` itself still requires a reason, so scripts/API behave as before.

### Update 3 — no delivery for solar EPC orders
- `sale_order_line.py` (new): for an EPC order (BOQ order or ticked *Solar EPC Order*) confirming the order creates the **EPC Project but no customer delivery** (`_action_launch_stock_rule` is skipped for its lines). Material reaches the customer through Material Request → issue to site → consumed at site, so a separate warehouse delivery used to take the same stock out twice (Forecasted showed 12 lower than On Hand).
- Ordinary sales orders are untouched: they still create their normal delivery.
- `sale_stock` added to the dependencies (it was already installed automatically).
- Existing EPC orders confirmed earlier keep the delivery they already have; cancel it by hand if it is not needed. Products invoiced on *Delivered quantities* will show nothing delivered on EPC orders; use *Ordered quantities* for solar items.

### Update 4
- **Approval to-dos no longer pile up:** the *Approval requested* (and *Rejected - please fix and resubmit*) to-dos of a document are removed when it is approved, rejected, reset to draft or submitted again, so each document has at most one current set. Old leftovers disappear the next time that document is approved, rejected or reset.

---

## Update 5 (2026-10-19) — shared stage dashboard screen
**What was added:** the one generic screen used by every stage dashboard, so no stage module ships its own JavaScript.
- `models/epc_stage_dashboard.py`: abstract model `epc.stage.dashboard`. `get_data(stage)` checks the caller is an EPC user, then calls `_dashboard_<stage>()` defined by the stage module. Helpers shared by all stages: `_kpi`, `_card`, `_tbl`, month/week buckets, grouped counts (with the matching click-through domain), money/energy/power formatting, approval turnaround.
- `static/src/js/epc_stage_dashboard.js`, `static/src/xml/epc_stage_dashboard.xml`, `static/src/scss/epc_stage_dashboard.scss`: client action `epc_stage_dashboard` (OWL + Chart.js from Odoo's own bundle). Renders KPI tiles, bar / horizontal bar / line / doughnut / scatter charts, a checklist matrix and a table from the JSON the backend returns.
- Each stage module adds a `Dashboard` menu that opens this screen with its stage name (`params = {'stage': ...}`).

### How it behaves
- **Live**: every number is read from the database each time the screen opens, on **Refresh**, and automatically every 2 minutes. Nothing is stored or cached.
- **Click-through**: each tile, chart bar/slice and table row opens the exact records that were counted (the list uses the same domain that produced the number). Scatter dots and table rows open the single record.
- **Access**: numbers are read with the logged-in user's own rights (no sudo), so a Field User only sees counts and lists of their own records (rule F22), and the count always matches the list that opens. A section the user cannot read is left out instead of breaking the page.
- **Screen sizes**: sizes are in `em` and the base font scales with the screen (13px phone to 22px projector); layout follows the width of the dashboard itself (container queries): 5-6 columns on a wide screen, 2 on a tablet, 1 on a phone; tables scroll sideways inside their own card.
- **Install / upgrade**: `-u csl_epc_core,<this module>` (new files only; no data migration, no new database fields).

**Adding a dashboard for a new stage:** inherit `epc.stage.dashboard`, add `_dashboard_<name>()` returning `title`, `accent`, `intro`, `kpis`, `cards`, `table`; add a client action with `tag = epc_stage_dashboard` and `params = {'stage': '<name>'}`; add a menu. No JavaScript needed.

### Update 7 (2026-10-19) — new look for the stage dashboards
- **Look:** white page with faint pastel glows, frosted-glass cards and tab area, tinted KPI tiles with rounded icons, softer tables and pills. One cool pastel palette (sky blue, periwinkle, lavender); no green/red/amber. Status is carried by shade and by the text label (Overdue, Failed, ...).
- **Files:** `static/src/scss/epc_stage_dashboard.scss` (rewritten), `static/src/js/epc_stage_dashboard.js` (chart colour palette only). Each stage module's `accent` colour in `models/epc_stage_dashboard.py` was changed to a pastel.
- **Unchanged:** all numbers, click-through, refresh, access rules and the responsive layout (phone to projector). The page is light-only on purpose.
- **Upgrade:** `-u csl_epc_core` then hard-refresh the browser (Ctrl+Shift+R).

### Update 8 (2026-10-19) — stronger glass effect
The frosted-glass look was too faint on a white page (nothing behind the cards to blur). Added soft colour blobs behind the content (they scroll with it) and made cards, KPI tiles and the Refresh button more translucent with stronger blur (`backdrop-filter: blur(20-22px) saturate(1.7)`), a bright inner edge and a soft shadow. Only `static/src/scss/epc_stage_dashboard.scss` changed. Upgrade: `-u csl_epc_core`, hard-refresh.

### Update 9 (2026-10-19) — no empty gaps in the card grid
**Problem:** when the last row of charts was not full (for example Quality ended with one small chart), the space beside it stayed empty and the table sat far below.
**Fix:** the screen now packs the cards into rows of 6 columns. A short row has its last card stretched; the free space in the final row (3 or more columns) goes to the table, which now sits inside the grid beside the last chart. A table too wide for its space scrolls sideways inside its own card. Files: `static/src/js/epc_stage_dashboard.js` (`applyLayout`), `static/src/xml/epc_stage_dashboard.xml`, `static/src/scss/epc_stage_dashboard.scss`. Upgrade: `-u csl_epc_core`, hard-refresh.

### Update 10 (2026-10-19) — dark mode
The stage dashboards now follow Odoo's own light/dark switch (user menu → *Dark mode*, stored in the `color_scheme` cookie). In dark mode the same pastel colours are used on dark frosted glass: navy page with soft blue/lavender glows, translucent dark cards, off-white text, and brighter chart colours. Light mode is unchanged. Implementation: colours became CSS variables in `static/src/scss/epc_stage_dashboard.scss` with a `.o_epc_sd_dark` override; `static/src/js/epc_stage_dashboard.js` reads the cookie, picks the dark chart palette and brightens the stage colour; the template adds the `o_epc_sd_dark` class. Upgrade: `-u csl_epc_core`, hard-refresh. To switch, use Odoo's user menu (the page reloads in the other mode).

### Update 11 (2026-10-21) — Refresh button and "Updated" time removed
The **Refresh** button and the "Updated hh:mm" label were removed from the top-right of every stage dashboard. The numbers still reload on their own every 2 minutes and every time the dashboard is opened. File: `static/src/xml/epc_stage_dashboard.xml`. Upgrade: `-u csl_epc_core`, hard-refresh.

### Update 12 (2026-10-21) — axis headings
Charts can carry axis headings: a stage module passes `xlabel` (bottom axis) and `ylabel` (left axis) for a card, either directly or through the helper `_axis_titles(cards, {key: (xlabel, ylabel)})`. For horizontal bar charts the bottom axis is the value axis. The screen draws them in the theme's text colour (`static/src/js/epc_stage_dashboard.js`). Upgrade: `-u csl_epc_core`.

### Update 13 (2026-10-21) — charts fill their card
**Problem:** when a chart card sat beside a taller card (for example "Most often missing" next to the document checklist), the card stretched but the chart kept its fixed height, leaving an empty band below the axis.
**Fix:** the chart area now grows to fill the card (it never gets shorter than before: 16em, 14em on a phone, 19em on a projector). The canvas is positioned inside its box so it cannot make the card grow by itself. File: `static/src/scss/epc_stage_dashboard.scss`. Upgrade: `-u csl_epc_core`, hard-refresh.

### Update 14 (2026-10-21) — fade-in and count-up
- **Fade-in:** tiles, charts and the table fade up one after another (0.4 s each, 60 ms apart) when a dashboard opens. The starting look is only applied during the delay, so the hover lift on tiles still works.
- **Count-up:** the tile numbers count up from 0 to their value (about 0.8 s, eased out) the first time the page loads. Automatic refreshes every 2 minutes update the numbers directly, without replaying either animation.
- Both are switched off for users who have "reduce motion" turned on in their system. Files: `static/src/scss/epc_stage_dashboard.scss`, `static/src/js/epc_stage_dashboard.js`, `static/src/xml/epc_stage_dashboard.xml`. Upgrade: `-u csl_epc_core`, hard-refresh.
