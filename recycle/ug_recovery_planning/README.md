# ug_recovery_planning – Recovery planning from assay

In the hydromet (recover) stage the expected outputs come from the actual assay
of the black mass being consumed, not from fixed BoM quantities.

## Features

* **Product metal content** (recovered materials): metal element and metal
  content %, e.g. NiSO4·6H2O 22.3 % Ni, CoSO4·7H2O 21.0 % Co, Li2CO3 18.8 % Li,
  MnSO4·H2O 32.5 % Mn, graphite 95 % C.
* **Recovery rates on recover BoMs** (*Recovery Rates* tab): element → output
  product (finished product or a by-product of the BoM) → recovery %. The output
  product must carry that element.
* **Recover MO, Recovery tab** (draft): input lots (approved assay only) with kg.
  Button **Compute expected outputs from assay**:

  1. contained kg = Σ lot kg × element % (current assay of each lot);
  2. expected metal = contained × recovery %;
  3. expected product kg = expected metal ÷ metal content %;
  4. primary input demand = Σ lot kg (chemicals scale with the same ratio);
  5. main product quantity set first (standard rescale), then each by-product demand
     is set to its expected quantity.
* A snapshot (`ug.production.recovery.line`) keeps contained, recovery %, metal
  content, expected and — once done — actual output, actual metal and efficiency
  (actual metal ÷ contained metal).
* Several input lots per MO are supported (one MO per shift/day).
* On confirmation the primary input move is reserved on the selected lots.

### Odoo 20 implementation note

In draft, Odoo 20 rebuilds raw and finished moves whenever `product_qty`,
`date_finished`, etc. change (`_compute_move_raw_ids` / `_compute_move_finished_ids`).
Writing by-product demands once would be lost on the next rebuild, so the expected
quantities are injected in `_get_moves_raw_values` / `_get_moves_finished_values`
whenever a snapshot exists. Changing the input lots clears the snapshot; compute again.

## Output purity gate (configuration)

Recovered material lots must pass a purity check before sale:

1. Create purity templates (demo: *Nickel sulphate purity* Ni/Co/Fe/Cu/Na,
   *Cobalt sulphate purity*, *Lithium carbonate purity*).
2. On the recovered material product tick *Requires Assay* and select the purity template.
3. Enable *Block Unassayed Lots* (Inventory settings).

Each recover MO then creates a draft purity assay for every output lot, and the
delivery is blocked until the assay is approved.

## Demo data

* Metal element / content on Nickel sulphate, Cobalt sulphate, Lithium carbonate,
  Manganese sulphate, Graphite.
* Recovery rates on *Recover NMC*: Ni 95, Co 95, Mn 95, Li 88, C 90 %.
* Purity templates on NiSO4, CoSO4, Li2CO3.
* A draft recover MO consuming lot BM-NMC-DEMO-001 (1,000 kg) with expected outputs
  computed: NiSO4 852.02, CoSO4 316.67, MnSO4 175.38, Li2CO3 163.83, graphite 331.58 kg.

## Tests

`--test-tags /ug_recovery_planning` (includes the spec check of the expected outputs within ±1 kg).

Manual test:

1. Open the draft recover MO › *Recovery* tab: input lot and expected outputs.
2. Change the quantity of the input lot → the snapshot is cleared; click the button again.
3. Confirm → the black-mass move is reserved on BM-NMC-DEMO-001.
4. Produce → actual output, actual metal and efficiency fill in; purity assays are created
   for the recovered lots.
