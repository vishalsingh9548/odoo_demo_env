# ug_recycling_base – Unicel Greens recycling base

Foundation for the Unicel Greens lithium-ion battery recycling flow
(Dismantle → Shred → Recover) on Odoo 20 Enterprise.

## Features

* **Battery chemistry** — `ug.battery.chemistry` master (LFP, NMC, LCO, NCA, LMO, Mixed). Chemistry on product, BoM, MO (related to BoM, stored), lot and quant (related to product, stored).
* **Material type** — `ug_material_type` on products: scrap battery, intermediate, recovered material, scrap by-product, chemical. Filters and group-by on products, quants and lots.
* **Recycling BoM** — `ug_is_recycling`, `ug_stage` (dismantle / shred / recover), `ug_max_loss_pct`; `ug_is_primary_input` on BoM lines.
* **Input-weight planning** — `ug_input_qty` (kg) on the MO. In draft it drives `product_qty` from the BoM ratio (components and by-products follow via standard Odoo); editing `product_qty` updates it back. On confirmed MOs the standard *Change Quantity To Produce* wizard gets an *Input Weight (kg)* field.
* **Mass balance** — Stored on done MOs: input (primary input consumed), output (finished + by-products), loss kg / %, loss-exceeded flag. "Mass Balance" tab on the MO.
* **Loss alert** — When a done MO exceeds the BoM's max loss: chatter message + To-Do activity for every Recycling Manager.
* **By-product lots** — On recycling MOs, lot-tracked by-products without a lot get one automatically at *Produce* (`<MO>-<internal ref>`).
* **Security** — Category *Recycling*: Recycling User, Lab Technician, EPR Officer, Recycling Manager.
* **Menu** — Top-level **Recycling** menu (Operations / Reporting / Configuration), extended by the other `ug_*` modules.

Weights are always converted with the product UoM to `uom.product_uom_kgm`.
Odoo 20 has no UoM categories any more: a unit counts as a weight when it shares
a reference unit with kg (`uom.uom._has_common_reference`). Other units are
ignored and a warning is logged.

### Constraints

* A recycling BoM has exactly one primary input line.
* Dismantle and shred BoMs have at least one by-product.
* Total by-product `cost_share` < 100.
* Max loss between 0 and 100 %.

## Actual weights (yield different from the BoM)

Recycling yields vary: 1,000 kg of packs may give 300 kg of cells instead of the
standard 350, or 380. Recycling orders therefore record what was really weighed:

* **Input stays fixed**: changing the quantity produced no longer rescales the
  components or by-products (standard Odoo would consume 857 kg for 300 kg of cells).
  Quantities the operator already entered are kept.
* **Record Weights** button (confirmed orders): one screen for the weighing station
  with the input per lot, the main product and every by-product, and a live mass
  balance (loss % against the BoM maximum, yield % against the BoM range).
  *Confirm & Finish Order* posts the weights and closes the order.
* **No backorder / consumption pop-ups** on recycling orders.
* **Yield range per BoM**: *Yield Tolerance (%)* (default 10 %, relative to the
  standard yield from the BoM quantities). Dismantle / shred orders outside the
  range are flagged *Yield Out of Range*, with a chatter note and an activity for
  Recycling Managers (same as loss alerts). Recover orders are judged on assay
  efficiency instead.
* **Output above input is blocked** on dismantle / shred orders (a weighing error);
  a Recycling Manager can confirm it from Record Weights. Recover orders are not
  blocked (chemicals add weight).

Manual test (BoM 1,000 kg → 650 kg cells, range 58.5–71.5 %): confirm an order, click
*Record Weights*, enter 550 kg cells → orange warning, finish → yield 55 %, flagged,
activity for the manager; enter 800 kg cells + by-products > 1,000 kg → red, cannot finish.

## Configuration (standard features, no code)

1. **Settings › Manufacturing**: enable *Work Orders*, *By-Products* and
   *Quality*. **Settings › Inventory**: enable *Lots & Serial Numbers*.
   (Users in *Recycling User* get these groups automatically.)
2. **Work centers** (Manufacturing › Configuration › Work Centers), each with its
   *Cost per hour*: Discharge station, Dismantling line, Weighing station,
   Shredder, Leach reactor, Filter press, Purification tanks, SX circuit,
   Crystallizer, Precipitation reactor, Dryer and packing.
3. **Operation dependencies** on the dismantle BoM: open the BoM ›
   *Miscellaneous* › tick *Operation Dependencies*, then on the *Dismantle*
   operation set *Blocked By* = *Discharge*.
4. **Quality control point** on discharge: Quality › Configuration › Control
   Points › New: Operation = manufacturing, *Work Order Operation* = Discharge
   (of the dismantle BoM), Type = *Measure*, Norm = the client's residual-voltage
   threshold with tolerance, *Failure* behaviour as required. The Discharge work
   order then can't be finished without a passing check (needs
   `quality_mrp_workorder`, which installs with Quality + Work Orders).
5. **Lot tracking**: set *Track Inventory › By Lots* and unit **kg** on all
   battery, intermediate and recovered-material products. Chemicals stay
   untracked.
6. On each recycling BoM: tick *Recycling BoM*, choose the stage, set the max
   loss, and toggle *Primary Input* on the line being broken down.

## Demo data

* 19 lot-tracked products in kg + 5 untracked chemicals, with material type and chemistry.
* 11 work centers with hourly cost.
* BoMs: *Dismantle LFP* (650 kg cells from 1,000 kg packs + 4 by-products,
  Dismantle blocked by Discharge), *Shred NMC* (750 kg black mass + Cu/Al foil;
  max loss raised to 12 % because the illustrative yields lose 10 % by design),
  *Recover NMC* (nickel sulphate + 5 by-products, 7 operations).
* Stock: 2,000 kg LFP packs (lot BP-LFP-DEMO-001), 1,000 kg NMC cells
  (CM-NMC-DEMO-001).
* Done MOs: one dismantle (1,000 kg → 3 % loss) and one shred (1,000 kg → 10 % loss);
  one draft dismantle MO planned at 500 kg input.

## Tests

```
odoo-bin -c debian/recycle.conf -d <db> -i ug_recycling_base --test-enable --test-tags /ug_recycling_base --stop-after-init
```

Manual test:

1. Recycling › Configuration › Recycling BoMs: open *Cells/modules – LFP*;
   untick *Primary Input* on the pack line and save → error.
2. Recycling › Operations › Manufacturing Orders › New, BoM *Dismantle LFP*:
   set *Input Weight* 2,000 kg → Quantity becomes 1,300 kg; components 2,000 kg; casing 400 kg.
3. Confirm, then click *Change input weight* → wizard with input weight; set 1,500 → quantity 975.
4. Produce with a by-product quantity lowered (e.g. casing 100 kg) → *Mass Balance*
   tab shows the loss, the MO is flagged *Loss Exceeded*, and an activity is
   scheduled for managers.
