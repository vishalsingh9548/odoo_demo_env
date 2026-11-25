# Drone - CRM & Sales (`drone_sales_crm`)

Odoo 18 Enterprise module for drone stringing of transmission lines for EPC contractors.

## What it adds

| Feature | Where |
|---|---|
| Job details: line name, voltage (kV), site / route, spans, total km | Opportunity and quotation, "Stringing Job" tab |
| Survey spans (span no., towers, length, crossing type) | Opportunity, "Stringing Job" tab |
| Span tasks created on the job when the order is confirmed (no duplicates) | Project created from the order |
| Client certifications that set the delivered km on the order | Sales > Orders > Certifications, and smart button on the order |
| Delivered km on per-km lines can't be edited by hand | Sales order lines |
| Certifications marked "Invoiced" when the invoice is posted | Automatic |
| "Stringing job" block on the quotation / order PDF | Sales order report |

## Created on install

| Record | Details |
|---|---|
| Product category **Drone Stringing Services** | Under *All* |
| **Drone stringing (per km)** `DS-KM` | Service, unit **km**, invoiced on delivered quantity (manual), billed per certified km, creates a project from the template on confirmation. Price 0. |
| **Mobilisation charge** `DS-MOB` | Service, unit Units, invoiced on ordered quantity (billed on confirmation) |
| **Demobilisation charge** `DS-DEMOB` | Same as mobilisation; optional product on the quotation template |
| Project **[Template] Stringing job template** | Stages Planned / In progress / Strung / Certified (folded), billable, visible to followers. Copied for every confirmed order: do not log work on it, and keep it active. |
| Quotation template **Drone stringing job** | Valid 30 days. Lines: DS-KM ×1 and DS-MOB ×1, optional DS-DEMOB, plus the billing terms |

All of these are `noupdate`: changes you make in the UI are kept on module upgrade.

The project generated on confirmation is named `<order> - <customer> - <line name>`, belongs to
the customer, and gets one task per survey span.

### Where to set the rate

The per-km product has a list price of 0 on purpose. Set the **rate per km in the Unit Price
of the DS-KM line on each quotation**, and replace the quantity 1 with the contracted km.
Set the mobilisation amount on the DS-MOB line the same way.

### Tax and SAC code: to be checked by the accountant

When `l10n_in` is installed and the company has a chart of accounts, installing the module:

* sets the domestic **18% GST** sale tax (`18% GST S`, CGST + SGST) on the three products;
  inter-state invoices switch to IGST through the standard fiscal positions;
* sets the SAC code to **998719, a placeholder**.

**The accountant must confirm both the tax and the SAC code** on the three products before the
first invoice. Without `l10n_in`, nothing is set and the taxes must be set by hand.
This only runs on a fresh install, not on module upgrade.

## Daily use

1. Fill the "Stringing Job" tab on the opportunity, including the survey spans.
2. Create the quotation from the opportunity and pick the **Drone stringing job** template:
   line name, voltage and site carry over. Enter the km and the rate per km.
3. Confirm the order: the project is created and gets one task per survey span.
4. When the client certifies km, create a certification from the order's smart button,
   attach the signed sheet and confirm it. The delivered km on the order updates.
5. Create and post the invoice. The certification moves to "Invoiced".

## Notes

* Certified km can't exceed the ordered km. Increase the order quantity first if the scope grows.
* An invoiced certification can't be reset. Cancelling an invoice does not reopen it; handle
  that case with a credit note and a new certification.

## Tests

```bash
odoo-bin -d <test_db> -i drone_sales_crm --no-http --test-enable --test-tags /drone_sales_crm --stop-after-init
```
