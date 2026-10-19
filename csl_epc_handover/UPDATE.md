# UPDATE — csl_epc_handover (Handover & Closure)

> Part of the Solar EPC split. Stage 14. Own app icon: **Handover & Closure**.

## Why this change was made
The original `csl_solar_epc` was one large module holding every stage of the solar EPC flow. We wanted each stage to be its own installable module (visible separately in Apps and as its own icon on the home screen) **without changing any behaviour**. Installing `csl_solar_epc` (shown as "Solar Dashboard") installs every sub-module automatically.

## What this module does (functionality)
- **Handover** records (`epc.handover`, chatter + activities + approval workflow): project, customer, closure date, uploads for as-built drawing, test reports, O&M manual and warranty certificate, customer training done/date, and a project closure report, used to formally close an installation. Sequence `HO/<year>/00001`.
- Opened from an approved Commissioning record with *Proceed to Handover* (that button lives in `csl_epc_commissioning`).

## Dependencies
`csl_epc_core`.

## Views, menus and screens
- `views/epc_handover_views.xml` — list, form, search, window action.

- Top-level app **Handover & Closure** → submenu *Handover & Closure*.

## Data and security
Sequence `seq_epc_handover`.

`security/ir.model.access.csv` — Field User read/write/create; Project Manager full.

## What was moved / changed compared to the original single module
Moved unchanged from the old module: `epc_handover.py`, its view and sequence.

No code edits other than the group references (`csl_epc_core.group_epc_*`).

## Impact
- No functional change. It only depends on core, which is why Commissioning can depend on it (and not the other way round).

## Install / upgrade notes
- Odoo only scans one folder level below each `addons_path` entry, so all modules sit side by side in `odoo_demo_env/` (not nested inside `csl_solar_epc/`).
- Moving records between modules changes their external IDs (`<module>.<xml_id>`). **Do not upgrade a database that already had the old single `csl_solar_epc` installed** — install on a fresh database.
- Fields, model names (`epc.*`) and database tables are unchanged from the original module, so data layout is the same.

---

## Update 2 (2026-10-19) — gap fixes
Follow-up round from `SOLAR_EPC_GAPS_AND_FIX_PLAN.md`. Existing behaviour is unchanged unless stated; every stricter rule is behind a switch in *Solar Dashboard → Configuration → Settings* (all OFF by default) except the two decided as ON: server-side approval permission (B6) and Field User own-records visibility (F22).

### What changed
- Optional switch **Handover Needs Documents**: the four documents and *Customer Training Done* must be present before a handover can be approved (OFF by default).
- Approval now goes through the shared approval checks (Project Manager only, correct state).
- **Visibility (F22):** Field Users see handovers they created; managers see all.
- **Not changed (decision):** approving a handover simply means *Completed* — no archiving, no project closure or stage change, and the Handover screen is unchanged.

### Impact
No behaviour change unless the switch is turned on.

### Upgrade note
Upgrade the module (`-u <module>`); new fields have safe defaults, no data migration is needed. Users who approve documents must be in the *Project Manager* group.

- **Reject pop-up:** the *Reject* button now opens a dialog that asks for the reason (provided by `csl_epc_core`).
