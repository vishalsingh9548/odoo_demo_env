# ug_lot_assay – Lot assays

Black mass is a mixed powder whose composition is only known from a lab assay.
This module records assays per lot and uses them for composition, value
estimates, Certificates of Analysis and a quality gate.

## Features

* **Masters**: assay elements (Li, Ni, Co, Mn, Fe, P, Al, Cu, C and Na),
  assay templates (*NMC black mass*, *LFP black mass*). On products: *Requires
  Assay* and *Assay Template* (Recycling tab).
* **Lot assay** (`ug.lot.assay`, ASSAY/YYYY/0001): lot, sample date/ref,
  in-house or external lab (partner required; certificate attachment required
  before approval), basis weight (lot kg when created), results per element
  (% with 4 decimals, contained kg on basis and on current quantity), *Others %*.
  Workflow Draft → Submitted (Lab Technician) → Approved / Rejected (Recycling Manager).
  Approving makes the assay *current* for the lot; the previous one is un-set
  and a note is posted on the lot. Approved assays are locked.
* **Constraints**: each % between 0 and 100, total ≤ 100.5 %, no duplicate element.
* **Lot**: *Assays* smart button, *Composition* tab (current assay lines,
  estimated metal value), assay status (*Not required / Pending / Approved*,
  stored, with an *Assay pending* filter), *Print CoA* button.
* **Auto draft assay**: when an MO is done and produces a lot (finished or
  by-product) of a product requiring an assay, a draft assay is created from the
  product's template and a To-Do activity is scheduled for every Lab Technician.
* **Quality gate** (Settings › Inventory › Traceability › *Block Unassayed
  Lots*, per company): a lot with a pending assay cannot be consumed in a
  recover-stage MO nor delivered to a customer (checked in
  `stock.move.line._action_done`).
* **Metal prices** (`ug.metal.price`): latest price by date per element and
  company. `ug_estimated_metal_value` on lots = Σ contained kg (current) × latest
  price, converted to company currency. **Estimate only – not accounting valuation.**
* **Certificate of Analysis**: QWeb PDF on lots; *Print CoA* on the lot, on the
  delivery order header and on each delivery line with an assayed lot.

## Configuration

1. Recycling › Configuration › Assay Elements / Assay Templates.
2. On each black mass (and recovered material, see `ug_recovery_planning`)
   product: tick *Requires Assay* and pick the template.
3. Add users to *Lab Technician* (submit) and *Recycling Manager* (approve).
4. Settings › Inventory › *Block Unassayed Lots* to enforce the gate.
5. Recycling › Configuration › Metal Prices.

## Demo data

* *Black mass – NMC/LFP* require an assay (NMC/LFP templates).
* Lot **BM-NMC-DEMO-001**, 1,000 kg, approved assay: Ni 20, Co 7, Mn 6, Li 3.5, C 35, Al 1, Cu 1 %.
* The black-mass lot produced by the demo shred MO gets a draft assay (pending).
* Metal prices for Ni (two dates), Co, Mn, Li, C, Cu, Al.

## Tests

`--test-tags /ug_lot_assay`

Manual test:

1. Inventory › Lots: filter *Assay pending* → the shredded black-mass lot.
2. Open its assay, enter results, *Submit* (as lab) → *Approve* (as manager).
   The lot status becomes Approved, *Composition* shows contained kg and the value estimate.
3. Create a second assay for the same lot and approve it → the first one is no longer current; note on the lot.
4. Enable *Block Unassayed Lots*; sell a lot that is still pending → validating the delivery fails naming the lot.
5. *Print CoA* from the lot.
