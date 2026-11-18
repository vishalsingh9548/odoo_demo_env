# UPDATE — csl_epc_documents (Government Document Pack)

> New module, added 2026-11-18. Gap #3. Own home-screen tile: *Project Documents*; templates under *Configuration → Document Templates*.

## Why this change was made
There was no checklist of the government/compliance papers a solar project needs (ID proof, subsidy forms, net-metering forms, certificates). The competitor creates this pack on order confirmation.

## What this module does (functionality)
- **Document Template** master (`epc.document.template`): name, category (KYC, Subsidy, Net Metering, Structure, Commissioning, Other), mandatory, applies to (all / residential / commercial / industrial), create-automatically flag.
- **Project Document** (`epc.project.document`): status Pending → Ready → Submitted → Accepted / Rejected, due date, signed scan, submitted date, remarks, overdue flag, chatter.
  - *Mark Submitted* needs a signed scan; *Rejected* needs a reason.
- **Created automatically when a Sales Order is confirmed** (after the core module has created the project) from the matching templates. Already existing documents are never duplicated.
- **Project**: *Documents* smart button with a progress pie, counts of done and mandatory-pending papers.
- **Auto-filled print form** (QWeb PDF): applicant, contact, site address, DISCOM, consumer number, connection type, sanctioned load, capacity, date, signature lines.
- **Settings switch** *Documents Block Commissioning* (OFF by default): commissioning cannot be submitted while mandatory papers are pending.
- Starter list of 8 templates (noupdate) — editable or switchable off.

## Dependencies
`csl_epc_dealer` (DISCOM/consumer data for the form), `csl_epc_commissioning`.

## Safety
Document creation on order confirmation runs inside a savepoint with logging: if it ever fails, the order still confirms.

## Files
`models/` template, project_document, project_project, sale_order (confirm hook), epc_commissioning (optional check), epc_config · `report/` print form · `views/` · `data/document_template_data.xml` · `security/`.

## Impact
- Every NEW confirmed EPC order now also gets its document pack. Old projects get nothing automatically.
- `sale.order.action_confirm` and `epc.commissioning.action_submit` are extended (original called first / the check is switch-controlled).
- Project form: one smart button added.

## Install / upgrade notes
Install after `csl_epc_dealer` and `csl_epc_commissioning`. Review the 8 starter templates and the mandatory flags before go-live. Existing projects can be given documents via a Python call to `project._epc_create_documents()` if needed.

## Tested note
The *Overdue* filter compares the due date directly. Verified: 8 documents created on confirm, scan required to submit, printable form renders.

## Home-screen tile and icon (updated 2026-11-18)
- Own top-level menu **Project Documents** with `static/description/icon.png` (140x140, navy background like the other Solar EPC icons), so it shows as its own tile on the home screen, like Site Surveys or BOQ & Costing. This replaces the first version, where the menus sat under *Solar Dashboard* and no tile appeared. Setup screens that belong to Configuration (templates, schemes, payment plans) stay under *Solar Dashboard → Configuration*.
- The module icon in Apps was blank because Odoo saves the icon path when a module is installed or upgraded, and the file did not exist yet at install time. Fixed by upgrading the module (`-u`).
- **Impact:** menus and icons only; no data or behaviour change. Upgrade needed to see them.

## Starter data for production (added 2026-11-18)
**4 more document templates** (passport photo, geo-tagged photos of the installed system, DCR / test certificates, company registration / GST certificate for commercial customers), on top of the original 8 — in `data/document_template_data.xml`.

- **Why:** so a new installation is usable straight after installing the module, with no typing of master data.
- **How it loads:** from the module's `data/` folder when the module is installed. The records are `noupdate`, so anything edited later in the screens is never overwritten by an upgrade.
- **Impact:** only adds master records. No existing record or behaviour is changed. If a record with the same name was typed by hand before installing, delete or rename it first, because names must be unique for DISCOMs.
- **Status:** files checked for correct XML only; not yet installed anywhere (install is done by the owner).
