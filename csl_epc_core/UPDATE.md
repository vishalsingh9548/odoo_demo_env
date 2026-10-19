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
