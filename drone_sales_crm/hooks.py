import logging

_logger = logging.getLogger(__name__)

PRODUCT_XMLIDS = (
    "drone_sales_crm.product_drone_stringing_km",
    "drone_sales_crm.product_drone_mobilisation",
    "drone_sales_crm.product_drone_demobilisation",
)

# PLACEHOLDER SAC code. The accountant must confirm the correct SAC code for drone-based
# stringing services before the first invoice is issued, and update it on the products.
PLACEHOLDER_SAC_CODE = "998719"

# Variants of the 18% sale tax that must not be the product default.
EXCLUDED_TAX_MARKERS = ("IGST", "RC", "EXP", "SEZ")


def _find_gst_18_sale_tax(env, company):
    """The domestic 18% GST sale tax (CGST + SGST group) of the company, if any."""
    taxes = env["account.tax"].with_context(active_test=True).search([
        ("type_tax_use", "=", "sale"),
        ("amount", "=", 18),
        ("company_id", "=", company.id),
    ])
    if len(taxes) <= 1:
        return taxes
    # l10n_in names it "18% GST S"; also accept "GST 18%".
    named = taxes.filtered(
        lambda t: ("GST 18%" in t.name or "18% GST" in t.name)
        and not any(marker in t.name for marker in EXCLUDED_TAX_MARKERS)
    )
    preferred = named.filtered(lambda t: t.amount_type == "group") or named
    return preferred[:1]


def post_init_hook(env):
    """Set the 18% GST sale tax and the SAC code on the drone stringing products (India only)."""
    if not env["ir.module.module"].search_count(
        [("name", "=", "l10n_in"), ("state", "=", "installed")]
    ):
        _logger.info("drone_sales_crm: l10n_in is not installed; taxes and SAC code not set.")
        return

    company = env.company
    if not company.chart_template:
        _logger.info(
            "drone_sales_crm: company %s has no chart of accounts; taxes and SAC code not set.",
            company.name,
        )
        return

    products = env["product.product"]
    for xmlid in PRODUCT_XMLIDS:
        products |= env.ref(xmlid, raise_if_not_found=False) or env["product.product"]
    if not products:
        return

    tax = _find_gst_18_sale_tax(env, company)
    if tax:
        products.write({"taxes_id": [(6, 0, tax.ids)]})
        _logger.info("drone_sales_crm: sale tax %s set on %s.", tax.name, products.mapped("default_code"))
    else:
        _logger.warning(
            "drone_sales_crm: no active 18%% GST sale tax found for company %s; "
            "set the tax on the drone stringing products by hand.",
            company.name,
        )

    if "l10n_in_hsn_code" in products._fields:
        # Placeholder: the accountant must confirm the SAC code (see PLACEHOLDER_SAC_CODE).
        products.write({"l10n_in_hsn_code": PLACEHOLDER_SAC_CODE})
