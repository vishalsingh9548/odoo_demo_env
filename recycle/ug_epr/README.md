# ug_epr – EPR certificates

Under India's Battery Waste Management Rules 2022 registered recyclers generate
EPR certificates on the CPCB portal and sell them to battery producers.

> **To confirm with the client**: the certificate basis (battery weight processed
> vs material recovered) and the battery categories. Both are configurable.

## Features

* **Settings** (Manufacturing › EPR): *EPR Basis* — `input_battery_weight`
  (primary input consumed in dismantle MOs) or `recovered_material_weight`
  (recovered-material output of recover MOs); *EPR Service Product*
  (default *EPR Certificate (per kg)*, service in kg, invoiced on order).
* **Categories**: Portable, Automotive, Industrial, Electric Vehicle.
* **MO fields** (done recycling MOs, *EPR* tab): eligible kg (stored, by basis and
  stage), claimed kg (non-cancelled certificates), available kg.
* **EPR certificate** (EPR/YYYY/0001): CPCB number (required from *Generated*),
  Indian financial year (computed from generation date, April–March, editable),
  category, chemistry, quantity, linked MOs, buyer, price, amount, quotation,
  invoices, transfer ref/date.
  Workflow Draft → Generated → Listed → Sold → Transferred (+ Cancelled), restricted to EPR Officers.
* **No double claiming**: a certificate's quantity is allocated over its MOs in
  date order (`ug.epr.allocation`); it must fit in the kg not claimed by other
  non-cancelled certificates.
* **Create Quotation** (listed, buyer and price set) → sale order with the EPR
  service product, quantity in kg, price per kg. Posting its customer invoice
  moves the certificate to *Sold*. *Mark Transferred* requires the transfer reference.
* **Hazardous waste manifest** register (HWM/YYYY/0001): Draft → Dispatched → Acknowledged.
* **Reports**: EPR Register (pivot/graph by FY, category, chemistry, state, buyer);
  EPR Eligible vs Claimed (pivot on MOs).

## Demo data

Producer, transporter and TSDF partners; a dispatched waste manifest; the demo
dismantle MO (1,000 kg eligible) backs a *listed* certificate of 600 kg with a
quotation and a draft certificate of 400 kg (fully claimed).

## Tests

`--test-tags /ug_epr`

Manual test:

1. Recycling › EPR Certificates › new: link the done dismantle MO, quantity
   larger than available → error.
2. Fill the CPCB number › *Mark Generated* › *List for Sale* › set buyer/price ›
   *Create Quotation* › confirm › create invoice › post → certificate *Sold*.
3. Enter the transfer reference › *Mark Transferred*.
4. Recycling › Reporting › EPR Register / EPR Eligible vs Claimed.
