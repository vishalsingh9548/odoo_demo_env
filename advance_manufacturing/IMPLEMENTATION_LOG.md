# Advance Manufacturing: implementation log

Plain-language record of what was built, why, and what it changes. Keep this file updated with every change to the module.

Database: `solar_epc_v2` (port 8669, config `solar_epc_split.conf`). The module lives in `demo_modules/odoo_demo_env/advance_manufacturing`, next to the Solar EPC modules, so the production demo has one database with both code sets.

---

## 1. What this module is

Standard Odoo manufacturing counts a **batch** ("make 100 panels"). This module adds **unit-by-unit** manufacturing: every panel gets its own serial number, passes through stages with quality checks, is graded A/B/C, goes onto pallets, and only then is the order closed.

It is a **switch**, not a replacement. Nothing changes for anyone unless **both** are true:

1. The **company** has *Advance Manufacturing* ticked (Settings > Users & Companies > Companies > "Advance Manufacturing" tab), and
2. The **user** is in the group **Advance Manufacturing** (Settings > Users > Access Rights > Manufacturing).

Otherwise standard Odoo manufacturing runs, exactly as before.

No "IB Solar" name or branding appears anywhere in this module. It was written fresh using the old `extra_addons/ibsolar` code only as a reference. Nothing in `ibsolar` was changed.

---

## 2. What was done to the database (and why)

| Step | What | Impact |
|---|---|---|
| Backup | `pg_dump` plus filestore copy saved in `/home/csl/Downloads` (`solar_epc_v2_backup_20261022_092725.dump`, `solar_epc_v2_filestore_20261022_092725.tar.gz`) | Safety net. Restore with `pg_restore`. |
| Company | Created company **Manufacturing Expo** (id 3) and added the admin user to it | New company that holds this functionality. The two existing companies are untouched. |
| Warehouse | Created warehouse "Expo Warehouse" (code EXP) for that company | Odoo does not create a warehouse automatically for a new company. Without one there are no manufacturing operation types ("floors"). |
| Dependencies | Installing the module also installs the standard **Manufacturing (mrp)** and **Sale-Manufacturing (sale_mrp)** apps | Adds the Manufacturing app and menus to the whole database. Standard behaviour for the other companies is unchanged. |
| Switch on | Ticked *Advance Manufacturing* on Manufacturing Expo and set serial prefix `EXPO` | Only that company uses the special rules. |
| Group | The admin user was added to the *Advance Manufacturing* group | Only the admin flow exists in the demo, so only the admin sees the extra screens. |

A throwaway copy of the database (`solar_epc_v2_test`, restored from the backup) was used to test everything first. It was deleted afterwards.

---

## 3. What each file does

### Control (the switch)
- `models/switch.py`: one question used everywhere: "is the company switched on AND is the user in the group?"
- `models/res_company.py`: company fields: on/off switch, serial prefix, max units per pallet (default 28), optional "Packed Stock Location".
- `security/security.xml`: the group, adds the admin to it, company walls (each company sees only its own records).
- `security/ir.model.access.csv`: group members get full access to the module's models.
- `views/company_views.xml`: the "Advance Manufacturing" tab on the company form.

### Core manufacturing
- `models/stage.py`: **Process Stages** (your own list of stations). Options per stage: quality check required, attachment required, ask for grade, parent stage (sub-tests that count as passed with the parent).
- `models/unit.py`: **Unit** (one row per panel): serial, current stage, status (Yet To Start, In Progress, Completed, Cancelled), quality check, attachments, comment, pallet. Buttons: Start, Next Stage, Update Status.
- `models/qc.py`: **Quality Check** per unit per stage (Pass/Fail). Failing asks for a reason. A list action "Bulk Pass" passes many at once.
- `models/serial.py`: **Serial Pool**: serials booked for an order and waiting to be allocated.
- `models/mrp_production.py`: additions to the standard Manufacturing Order: Floor, Book Serial Number, Allocate Serials, New Pallet, Confirm Packs, Plan and Mark Done rules, and the replacement order for scrapped units.
- `models/stock_rule.py`: makes the manufacturing order stay in **Draft** after a sale order is confirmed (for switched-on users only).
- `wizard/status_wizard.py`: the **Update Status** pop-up (Grade A / B / C).
- `wizard/qc_fail_wizard.py`: asks why a check failed.

### Packing
- `models/pallet.py`: **Pallet** (named PALLET0001...), QR code text, Draft/Confirmed, lock after confirm, size limit.
- `wizard/pallet_add_wizard.py`: the scan box that runs five checks on each serial before adding it.

### Screens, menus and reports
- `views/*.xml`, `wizard/*_views.xml`: all screens. Manufacturing Order form gets a Floor field, four buttons, and Units / Serial Pool / Pallets tabs, all hidden unless the special mode is on.
- `views/menus.xml`: Unit Tracker (Reporting), Quality Checks, Process Stages (Configuration). Group members only.
- `report/report.xml`: Pallet Sheet (with QR code) and Serial Labels (barcodes).
- `data/sequence.xml`: number series for pallets and serials.

---

## 4. How it behaves (when switched on)

1. **Sale order confirmed** (by a group member): the manufacturing order is created but left in **Draft**.
2. **Floor** must be chosen before **Plan**: "Floor is required before planning the manufacturing order."
3. **Book Serial Number**: one serial per unit to make (prefix + 5-digit number, e.g. `EXPO00001`). Needs the company prefix.
4. **Allocate Serials**: creates one Unit row per serial, starting at the first stage. Needs at least one Process Stage.
5. **Per unit**: Start, then pass the quality check (if the stage needs one), attach a document (if the stage needs one), Next Stage. After the last stage the unit is **Completed**.
6. **Update Status** grades a unit:
   - **A**: moves to the next stage.
   - **B**: scraps the chosen components and sends the unit back to an earlier stage (new quality check there).
   - **C**: scraps the chosen components, cancels the unit, shrinks the order by 1 and creates a **1-unit replacement order** (linked by a "Replacement Orders" button) carrying the same serial from the first stage again. If the order has only one unit, no replacement order is made.
   - Grade must match the quality result: passed means only A; failed means only B or C; not done yet means do the check first.
7. **Pallets**: New Pallet, then Add Serial (scan box). Each serial must: be entered, exist and be completed, belong to this order, not already be on this pallet, not be on another pallet. Max 28 per pallet (company setting). **Confirm Packs** locks the pallets.
8. **Mark Done / Produce**: blocked unless every live unit is completed, pallets exist and none is empty, every completed unit is on a pallet, and all pallets are confirmed. The produced quantity is set to the number of finished units. If a Packed Stock Location is configured, finished goods go there.

---

## 5. Deliberate differences from the old IB Solar behaviour

- **No quant hacking for stock.** The old code cancelled the "produce adds stock" effect and added stock one unit at a time. Here the produced quantity simply equals the finished units, and the finished goods can be routed to a Packed Stock Location. End result is the same without editing stock records directly.
- **Own quality checks.** Quality checks are this module's own lightweight records, so no Enterprise Quality app is needed.
- **Stricter grading.** The old code allowed any grade while the check was still "To Do". Here the check must be passed or failed first.
- **Mark Done is stricter**: all pallets must be confirmed, and every completed unit must be on a pallet.
- **Scrap with not enough stock**: the scrap still goes through (stock may go negative) and a note is left on the order.
- **Parent/child stages** are simplified: only top-level stages are steps; sub-stages are labels that count as passed with the parent.
- **Left out on purpose** (not in scope): emails and WhatsApp, approvals, material requisition, scan station, vehicle lines on deliveries, BOM change requests, "use stock vs make" popup on sale orders, Excel serial import/export.

---

## 6. Things to know

- **Automatic jobs have no user.** If a sale order is confirmed by an automatic process (not a person in the group), the special mode is off for that action and standard Odoo applies.
- A user in the group working in a **different company** (switch off) gets standard behaviour.
- Users must pick **Manufacturing Expo** in the company switcher (top right) to work in that company.
- **Setup still needed in the UI** before a demo: create Process Stages (Manufacturing > Configuration > Process Stages), a product with a Bill of Materials and component stock in the Expo warehouse.

---

## 7. Test results (on the throwaway copy)

All of these passed: switch on for Expo and off for the other companies; a user outside the group gets no special behaviour; Plan blocked without a floor; serial booking and allocation; quality gate on Next Stage; attachment rule; Grade A to completion; QC fail with reason; grade gate; Grade B (scrap, back to stage 1, new check); Grade C (scrap, cancel, replacement order with resized components); Mark Done blocked without pallets; duplicate scan blocked; pallet lock after confirm; Mark Done after packing; draft manufacturing order only for the switched-on company; all views load.

---

## 8. Demo data for Manufacturing Expo (added 2026-10-22)

Script: `scripts/seed_expo_demo_data.py` (safe to run twice; it skips anything that already exists).

**What it did to `solar_epc_v2`** (every record stamped with the company Manufacturing Expo only):
- Read-only copy of structure from the reference database `crm_complete` (that database was not changed).
- **3 panel products with 4 variants each**: Solar Panel 450W, 500W, 540W. Variants come from a shared attribute **Cell Type**: Bifacial-NDCR, Bifacial-DCR, Mono-Perc-NDCR, Mono-Perc-DCR. Panels use the Manufacture route and have the original list prices.
- **11 Bills of Materials**, one per variant, copied from the reference BOMs (e.g. the 450W has 22 component lines: cells, glass, EVA, backsheet, ribbon, frames, junction box, sealant, labels...). The 500W has 3 BOMs because one variant had no usable BOM in the reference data.
- **28 component products** (category *Solar Components*), with the reference cost and a unit of measure mapped to the nearest one here (NOS/Pcs/Set to Units, Sqm to m², Kgs to kg, Litres to L).
- **Starting stock of 5000 of each component** in the Expo warehouse stock location.
- **5 sample Process Stages**: Cell Stringing, Lamination (attachment required), EL Testing (quality check), Framing, Final Flash Test (quality check). Edit or delete freely.
- **Brand name removed** from product names (e.g. "IB solar Backlabel" became "Backlabel"). New categories: *Solar Panels*, *Solar Components*.

**Choices to know about:**
- The request said "450 kW / 540 kW"; the reference data has **450 W and 540 W** panels, so those were copied.
- Components are **not lot-tracked** (in the reference they were) so a demo can run without picking lots on every component. Grade B/C scrap also works with tracked components (see below).
- The attribute and categories are database-wide labels, but the products, BOMs, stock and stages belong to Manufacturing Expo only, so other companies cannot see them.
- No sale-order "make to order" route was added to the panels. Add it on the product if you want a sale order to trigger a manufacturing order automatically.

**Code change made at the same time:** the *Update Status* pop-up now has a **Lot** column on each scrap component line. If a component is lot/serial tracked and no lot is picked, the system picks a lot that has stock at the order's source location (or asks you to choose one). Before this, scrapping a tracked component would have failed.

**Checked after seeding** (rolled back, no test records left): a 450W order with 22 components; Grade C on one unit scrapped all 22 components, shrank the order from 2 to 1, and created a replacement order.


## 10. Second build round (2026-10-22): sections 1-6 of GAP_LIST.md

Scope agreed with the user: emails, WhatsApp and cron jobs are excluded; dead/broken reference code is excluded; build stopped after six sections so the user can test in the UI. Everything below is still behind the company switch + group switch.

**Section 1: Sale / manufacturing-order core**
- `models/stage.py`, `unit.py`, `qc.py`, `validation_mixin.py`, `mrp_production.py`, `wizard/status_wizard.py`, `wizard/attachment_wizards.py`: sub-stages that count as passed with their parent, running line numbers, "stages passed" count, QC attachments window, bulk attachments window, sale information on the order, total quantity, scrap smart button, backorder handling, delivery-quantity helper, finished-good rule, Quality-only users cannot Plan.
- `models/product.py`, `stock_rule.py`: per-product "Keep Manufacturing Orders in Draft" (default on) and route default.
- `models/sale_terms.py`: bank accounts, GST number, Terms and Conditions tab, billing/shipping addresses, 7-day validity, who may send quotations, wattage on products.
- `models/sale_flow.py`, `wizard/sale_confirm_wizard.py`: the **Confirm Sale Order** window (take finished units from stock, make the rest; the manufacturing order is resized or removed), **Split** with a reason, **Reference PI** copy with locked lines, and the three-level **sales approval** (First, Second, Admin; in-app notes instead of emails). A finished unit taken from stock is reserved on the unit (`stock_sale_order_id`).
- Deliberate differences: the sale status "Sales Order" keeps its normal label (others are not affected); manual mode now really reserves the units (the old code only reduced the number).
- Not built in this round (still TO-BUILD): sale-order-level serial generation and reuse, pallets on sale orders, delivery packs, vehicle lines, pack stock moves.

**Section 2: BOM change request and revision**
- `models/bom_approval.py`, `wizard/bom_change_wizard.py`: non-administrators cannot edit a BOM; they send a change request (window with reason). Approver sees a before/after table and approves or rejects. Direct edits are turned into a request quietly (the old behaviour raised an error that rolled the request back).
- `models/bom_revision.py`, `wizard/bom_update_wizard.py`: lightweight "Revise BOM / Update BOM" from an order, replacing the Enterprise Engineering Change Order (no Enterprise PLM needed).

**Section 3: Serial prefix, scan station**
- `models/serial_prefix.py`, `wizard/prefix_wizard.py`: one prefix per company; "Update Serial Number Prefix" on unallocated serials.
- `wizard/scan_station.py`, `static/src/js/serial_lookup_input.js`: Serial Scan app (scan box with a small custom field widget, details window, Pass/Fail, grade A / B / C, related sale order and manufacturing order, Serial Journey report). Pack scan validation is done by the pallet scan box (same five checks) rather than a custom tag widget.

**Section 4: Material requisition**
- `models/requisition.py`, `mrp_requisition.py`, `mr_report_wizard.py`, `views/requisition_views.xml`: requisitions with multi-level approvers (approver masters), approval by role, in-app notes and To-Do activities, internal transfer on final approval, purchase order link (receipt goes to the floor), lot picker window, shortage check on manufacturing orders (Plan, work-order Start and Book Serials are blocked), PDF and Excel reports, purchase-block flag on users, default requisition source and MO Stock / Rejection location flags.

**Section 5: Scrap**
- `models/scrap_transfer.py`, `views/scrap_views.xml`: transfers into a Rejection location create scrap records; deliveries leave from MO Stock; scrap reason tags menu; Scrap Serial Excel report.

**Section 6: Incoming quality check**
- `models/receipt_qc.py`, `views/receipt_qc_views.xml`: a check per product on each receipt (sample count from the product), receipt cannot be validated until every check is passed; finished goods cannot be purchased. No Enterprise Quality app needed.

**Applied to `solar_epc_v2`:** module upgraded, seed re-run (adds serial prefix, a bank account, Store / Packaging / Rejection locations, an employee for the admin, approver masters, a customer and a vendor, the Replenish-on-Order route on the panels). Backups: `/home/csl/Downloads/solar_epc_v2_backup2_*` and `solar_epc_v2_before_upgrade_*`.

## 9. Change history

| Date | Change |
|---|---|
| 2026-10-22 | Second build round: sections 1-6 of GAP_LIST.md built, tested on a copy, applied to solar_epc_v2. |
| 2026-10-22 | Demo data added for Manufacturing Expo (panels, variants, BOMs, components, stock, stages). Lot column added to the Update Status pop-up. |
| 2026-10-22 | Backup taken. Company "Manufacturing Expo" created. Module `advance_manufacturing` written and tested on a copy, then installed on `solar_epc_v2`. |

## 11. Third build round (sections 7 to 9) and a fix

- **Fix (MO looked like standard Odoo on a new order):** the "is the mode on" flag on the manufacturing order, sale order and BOM was computed before the company was filled in, so it was False on a NEW record. Added `@api.depends('company_id')` + context dependency in `mrp_production.py`, `sale_terms.py`, `bom_approval.py`. Saved orders were never affected.
- **7 Sale-order serials:** `models/sale_serial.py` - `advmfg.so.serial`, Generate Serials on the sale order (reuses numbers freed by cancelled orders), release on cancel, Link-to-Sale-Order wizard, Excel import/export of the serial pool, "Additional Notes from SO" tab on the MO.
- **8 Delivery:** `models/delivery.py` - vehicle/driver tracking tab, dispatch-details check, Generated Packs (pallets into packs, confirm/lock, one pallet one pack, must belong to the sale order), pack status, pack list report, serials marked delivered after validation.
- **9 Purchase and access:** `models/purchase_misc.py` - category flag "Purchase Needs Approval" (PO goes to 'to approve' for non-managers, to-do for managers), PO label, Customers/Vendors partner filters, Product Creation group, combo HSN column.
- Tested on the throwaway copy (T7.x, T8.x, T9.x all pass), backup `solar_epc_v2_before_sec789_*.dump` in Downloads, then applied to `solar_epc_v2`.
- Not built: PO/SO/quotation custom reports, invoice customisations, machine maintenance, the remaining access-rule rows, delivery email/WhatsApp (excluded).

## 12. Fourth build round (sections 10 and 11)

- **10 Sale payments, purchase approval, reports, invoice:** `sale_payment.py` (advance, outstanding, LC interest %, pending amount, "total cannot be negative"; gate number on bills; product.product creation gate), `purchase_approval.py` (Restricted Purchase User / Purchase Approver / IT Approver groups and record rules, category "allowed" flags, Send Approval, Reject, confirm only by the matching approver, lock after approval), `custom_reports.py` + `report/custom_reports.xml` (Custom Purchase Order, Custom Sale Order, Custom Quotation / Proforma with combo grouping; PO and SO refuse to print before confirmation).
- **11 Machine maintenance (needs the community `maintenance` module, now a dependency):** `maintenance.py` - machine product flag and due date, maintenance location/source flags (one each), user flags, component and reason pop-ups, Send for Approval / Approve (creates the internal transfer) / Start Progress / Mark to Done (consumes parts) / Repairing State / Repairing Done / Scrap, stages renamed and ordered, Machine Maintenance Schedule menu.
- Seed adds: maintenance store + shop locations, an Expo maintenance team, admin flagged as maintenance manager and approver.
- Tested on the copy (T10.x, T11.x pass), backup `solar_epc_v2_before_sec1011_*.dump`, applied to `solar_epc_v2`.
- Deviations: the pending amount = total - advance + outstanding (the LC interest is already inside the total, the reference added it twice); customer/vendor dropdown is not hard-limited by rank (only filters), so new partners stay selectable; "Send Maintenance Mail", invoice confirmation email wizard and all other email/WhatsApp rows stay excluded.
- GAP_LIST.md statuses were NOT re-audited after sections 7 to 12; the counts there are out of date.

## 13. One access setting

- The many roles were folded into ONE dropdown on the user form: **Advance Manufacturing > Administrator**. Everything in the module (menus, buttons, tabs, ACLs, the master switch) now keys on that single group (`group_advmfg_manager`). Empty = standard Odoo.
- Old roles stay defined but hidden (no category) so data keeps working; Administrator implies the approval roles, BOM approver and product creation. Removing Administrator also strips the hidden legacy roles (`models/switch.py`).
- Fixed: the sales-approval record rules hid draft orders from anyone holding the approval roles; Administrator is now exempt.
- Purchase approval screens no longer need the switch, so restricted buyers/approvers (hidden roles) can still use them.
- Section 13 addendum: Serial Scan and Material Requisition apps now have their own icons (static/description/icon_scan.png, icon_requisition.png).
- Fix: Purchase Approver / IT Approver record rules no longer restrict Administrator (admin got 'no read access' on ordinary purchase orders, e.g. from the requisition's Purchase Orders button).
- Removed the 'attach the document for stage X and serial Y' check: units can move on without an attachment (the stage flag stays but is no longer enforced).
- Fix: QWeb does not allow t-field directly on <td>. Wrapped in <span> in the Pallet Sheet, Material Requisition PDF and Serial Journey reports (pallet sheet now prints the serial numbers). All four PDF reports render.

## 14. Live Serial Journey screen + delivery receipt fields

- `wizard/serial_journey.py`, `report/journey.xml`, view in `views/scan_views.xml`: scanning any serial in the Serial Scan box now opens the Serial Journey screen (live, read fresh on open/Refresh): where it is now, status, quality result, grade, stage strip with QC state, origin (sale order, MO, booked/allocated), packing (pallet, pack, delivery order), delivery details (vehicle, number, driver, contact, delivered to, dispatched, expected, delivered on, received by) and a full history timeline. Buttons: Refresh, Update Status (only while the unit is being made), Print Report (PDF), Close. Serials booked but not yet allocated show a message.
- `models/delivery.py`: new delivery-order fields Delivered On (auto-filled at validation), Received By, and Delivered To (customer name and address, read-only); shown on the Delivery Tracking tab.
- Timeline times come from record dates (QC checks, pallet, pack, delivery); pallet/pack times are the record's create/confirm dates.

## 15. Components tracked by lots
- The 28 Manufacturing Expo components are now tracked **By Lots**; the 12 finished panels (and variants) stay **By Quantity**. Existing stock was moved into one lot per component (LOT-<id>-001), nothing deleted. The seed script (scripts/seed_expo_demo_data.py) now creates components with lot tracking and stocks them with a lot, and converts any lot-less stock when re-run.
