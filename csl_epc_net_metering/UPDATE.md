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
