# ug_mass_balance – Recycling reporting

Reporting only, on SQL views (`_auto = False`).

* **Mass Balance (`ug.mass.balance.report`)** — done recycling MOs; main measures: input kg, output kg, loss kg, loss %
* **Element Recovery (`ug.element.balance.report`)** — recovery lines of done recover MOs; main measures: contained kg, actual metal kg, efficiency %
* **Material Output & Cost (`ug.material.output.report`)** — done finished / by-product moves of recycling MOs; main measures: qty kg, value, cost per kg
* **Stock by Stage** — `stock.quant` (internal locations); main measures: quantity by material type × chemistry

* Quantities in kg: in SQL only units sharing the kg reference unit are converted
  (`uom.factor`); other units count 0.
* Value: Odoo 20 has no `stock.valuation.layer`; the value comes from
  `stock.move.value` (stock_account), split between finished product and
  by-products by their cost share.
* Loss %, efficiency % and cost per kg are averaged in pivots; use the kg measures
  for weighted totals.

## Menu

**Recycling**
* Operations: Manufacturing Orders (recycling only), Lot Assays, EPR Certificates, Waste Manifests
* Reporting: Mass Balance, Element Recovery, Material Output & Cost, Stock by Stage, EPR Register, EPR Eligible vs Claimed
* Configuration: Recycling BoMs, Chemistries, Assay Elements, Assay Templates, Metal Prices, EPR Categories

## Tests

`--test-tags /ug_mass_balance`

Manual test: Recycling › Reporting › Mass Balance (pivot by stage and chemistry);
Element Recovery after producing the demo recover MO; Material Output & Cost;
Stock by Stage.
