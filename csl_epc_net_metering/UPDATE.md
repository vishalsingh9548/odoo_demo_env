# UPDATE — csl_epc_net_metering (Net Metering)

> New module, added 2026-11-18. Gap #5. Own home-screen tile: *Net Metering*.

## Why this change was made
Net metering with the electricity board (application, approval, inspection, meter, grid sync) was not tracked, although a project is not really finished until the meter is synced.

## What this module does (functionality)
- **Net Metering Application** (`epc.net.meter`, `NM/<year>/00001`): Draft → Applied → DISCOM Approved → Inspection Done → Meter Installed → Synced (or Rejected). DISCOM and consumer number come from the project; application number, meter number and all dates are recorded.
  - *Meter Installed* needs the meter number; *Rejected* needs a reason.
- **Stuck reminder**: a daily scheduled job creates a to-do for the project manager when an open application has not changed status for N days (setting, default 15). Respects *Turn Off Notifications*.
- **Handover check** — switch *Handover Needs Net-Meter Sync* (OFF by default): a handover cannot be approved while the project has an open (not synced / not rejected) application. A project with no application is not blocked.
- Project: *Net Metering* smart button.
- No automatic submission to the DISCOM portal (staff enter the data by hand).

## Dependencies
`csl_epc_documents`, `csl_epc_commissioning`, `csl_epc_handover`.

## Files
`models/` net_meter, project_project, epc_handover (optional check), epc_config · `data/` sequence and cron · `views/` · `security/`.

## Impact
- `epc.handover.action_approve` is extended; with the switch off it behaves exactly as before.
- One new scheduled job (daily).
- Settings → Solar EPC: new *Net Metering* block.

## Install / upgrade notes
Install after `csl_epc_documents`. No data migration.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **Net Metering** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Dashboard (added 2026-11-19)
- **What:** a live **Dashboard** screen for this module, the first entry of its menu, in the same look as the Commissioning and Handover dashboards (design was approved from a preview first). It uses the shared screen in `csl_epc_core`, so this module ships no JavaScript: only `models/epc_stage_dashboard.py` (method `_dashboard_net_metering`), `views/epc_dashboard_views.xml` (screen entry and menu) and one line in `models/__init__.py` and in the manifest.
- **Shows:** Open applications, stuck over N days (N is the existing *Net-Metering Stuck After* setting, default 15; shows how many already got a reminder to-do), average days to sync, meter fitted but not synced, synced this month (vs last month), rejected. Charts: pipeline, average days in current status, open applications by DISCOM, synced per month, days-to-sync trend. Table: applications not moving.
- **Clicking** a tile or a chart bar opens the list of exactly the records that were counted. Numbers are read with the logged-in user's own access rights.
- **Reads from:** epc.net.meter. No new fields, no data changes.
- **Impact:** adds one menu entry ("Dashboard") and one client action. Nothing existing is changed; uninstalling the module removes it.
- **Tested:** on a throw-away copy of the database (never on the live one): each dashboard was built empty and with a full scenario, and its result checked to be sendable to the browser. Not yet viewed in a browser.
- **Install / upgrade notes:** the manifest changed, so **restart the Odoo server first**, then *Upgrade* this module (the server keeps each module's file list in memory until it restarts).
