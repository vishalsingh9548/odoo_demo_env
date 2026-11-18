# UPDATE — csl_epc_dealer (DISCOM & Dealer)

> New module, added 2026-11-18. Gap #1 from the competitor comparison (Entrivis Solar EPC). Own home-screen tile **Dealers & DISCOM**.

## Why this change was made
The lead captured sanctioned load and site, but not the electricity board (DISCOM), the consumer number or which dealer brought the lead. Government forms (subsidy, net metering) need these, and dealers need to be tracked for commission. They are now typed once on the lead and reused everywhere.

## What this module does (functionality)
- **DISCOM master** (`epc.discom`): name, state, portal link.
- **Dealer master** (`epc.dealer`): name, parent dealer (a sub-dealer is a dealer with a parent), phone, email, commission %, *Leads* smart button.
- **CRM lead** (extra fields in the *Solar Details* tab): DISCOM, Consumer Number, Connection Type, Dealer, Sub-dealer (sub-dealer list follows the chosen dealer).
- **Sale Order** (Solar EPC Terms tab) and **Project** (Solar EPC group): the same four details shown read-only/related from the lead.

## Dependencies
`csl_epc_core` only.

## Why a new module instead of editing csl_epc_core
Adding fields to `csl_epc_core` would force an upgrade of the foundation module that every other module depends on. A separate module keeps core untouched, so nothing existing can break; uninstalling this module removes only these fields.

## Files
`models/` epc_discom, epc_dealer, crm_lead, sale_order, project_project · `views/` discom, dealer, lead, order, project, menus · `security/ir.model.access.csv`.

## Data and security
No sequences or demo data. Field User: read masters; Project Manager: full. No record rules (masters are shared).

## Impact
- Existing leads, orders and projects: new fields are empty; nothing else changes.
- Two new menus under Configuration: *DISCOMs*, *Dealers*.
- No existing view was replaced; the new fields are added by inheritance next to the existing ones.

## Install / upgrade notes
Install after `csl_epc_core`. Needs the DISCOM list filled in (Configuration → DISCOMs) before it is useful. No data migration.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **Dealers & DISCOM** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Starter data for production (added 2026-11-18)
**55 DISCOMs** (electricity boards of Maharashtra, Delhi, Gujarat, Karnataka, Tamil Nadu, Kerala, Telangana, Andhra Pradesh, Uttar Pradesh, Rajasthan, Madhya Pradesh, Chhattisgarh, Punjab, Haryana, Uttarakhand, Himachal, Jharkhand, Bihar, West Bengal, Odisha, Assam, Goa, Puducherry, J&K), each linked to its state — `data/discom_data.xml`. Dealers are NOT pre-loaded because they are specific to your business.

- **Why:** so a new installation is usable straight after installing the module, with no typing of master data.
- **How it loads:** from the module's `data/` folder when the module is installed. The records are `noupdate`, so anything edited later in the screens is never overwritten by an upgrade.
- **Impact:** only adds master records. No existing record or behaviour is changed. If a record with the same name was typed by hand before installing, delete or rename it first, because names must be unique for DISCOMs.
- **Status:** files checked for correct XML only; not yet installed anywhere (install is done by the owner).

## Note on loading the starter data (2026-11-18)
Odoo reads a module's file list only when the server starts. The DISCOM data file was added to the manifest while the server was already running, so the first install did not load it. Fix applied at the owner's request: server restarted, module upgraded once (55 DISCOMs, all linked to a state). Rule for the future: after changing a manifest, restart the server before installing or upgrading.

## Six starter dealers (added 2026-11-18)
At the owner's request the module now ships 4 placeholder dealers (North / West / South / East region) and 2 sub-dealers. They are in `data/discom_data.xml` (not a new file) because that file is already in the manifest, so an Upgrade loads them without a server restart. They are `noupdate`: rename or edit them freely and upgrades will not overwrite. **Replace the placeholder names, phones and commission rates with your real ones before go-live.** (The CSV import template that was briefly offered was deleted by the owner; to bulk-load dealers later, use the standard Import records feature on the Dealers list.)
