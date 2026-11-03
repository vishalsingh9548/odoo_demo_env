# home_kouzina_uat

## Access control: one group, "Home Kouzina Access"

All Home Kouzina custom functionality is switched on by **one** group:

| | |
|---|---|
| Group | `hk_access.group_hk_access` — **Home Kouzina Access** |
| Category | Home Kouzina |
| Defined in | new module `hk_access` (`hk_access/security/hk_security.xml`) |
| Enable per user | Settings > Users > (user) > Access Rights > **Home Kouzina** section |
| Default members | `base.user_root`, `base.user_admin` |

Install `hk_access` first. Every gated module lists `hk_access` in its `depends`.
Users outside the group see standard Odoo only.

The group implies **Inventory Variation Manager** (`hk_inventory_variation/security/security.xml`), so one checkbox
is enough for that module. It does **not** grant standard Odoo rights (Stock, Sales, Purchase, MRP, Accounting):
the user still needs those for the standard screens and for the ACLs of the report models.

### Where the group is applied

**Menus** (replaces the earlier standard-group restriction where there was one)
- `amazon_orders_menu`: Amazon Orders, Shopify Orders
- `hk_inventory_report`: HK Inventory Report
- `hk_inventory_variation`: Inventory Variation (root and Variation Sessions)
- `hk_purchase_report`: Purchase Consolidate Report
- `home_kouzina_mr`: Material Requisition (root and Requisitions)
- `home_kouzina_sales`: Packages, Marketplace Master
- `inventory_soh_report`: Inventory SOH Report
- `margin_report`: Margin Report and the two COGS wizards
- `mo_cost_report`: Production Report
- `mo_raw_material_consumption`: MO-wise Raw Material Consumption
- `sale_amazon_return`: Amazon Returns
- `sale_marketplace_report`: Marketplace Report
- `weekly_inventory_upload`: Weekly Inventory Upload

**Fields, tabs, buttons, filters and list columns added to standard screens**
(inside inheriting views: `<t groups=...>` for form blocks, `groups=` on each field, button, filter or page
where `<t>` is not allowed, i.e. list, search, pivot and tabs)
- `hk_partner_documents`: Purchase Order, Sale Order, Invoice, Partner forms
- `hk_logistics`, `hk_sale_footer_totals`, `hk_warehouse_invoice_sequence`
- `hk_product_uom_change_wizard`: "Change UoM" buttons (Product and Variant form)
- `hk_inventory_variation_upload`: upload button, group and tab on the Variation form
- `home_kouzina_sales`: Product, Sale Order, Purchase Order, Invoice, Payment and Picking views
- `home_kouzina_mr`: Stock Location form
- `marketplace`: Sale Order form, list and Marketplace Info tab, Sales Analysis filters
- `marketplace_type_update`: "Set Marketplace Type" list button
- `mrp_auto_component_lots`, `mrp_component_lot_fetch`, `mrp_retail_skip_approval`, `mrp_backdated_component_lot`:
  Manufacturing Order, Product, User, Picking and Quant views
  (the standard MO status bar is kept for users without the group and replaced by the custom one for members)
- `no_negative_stock`: Product and Category, Location forms
- `purchase_cost_price`, `purchase_cost_price_filter`, `sale_purchase_previous_product_cost`
- `sale_amazon_payment_gateway`, `sale_amazon_return`: Amazon account and Sale Order views

**Bound actions and reports**
- "Inventory Wizard" (`hk_stock_update`), "Change UoM" server action (`hk_product_uom_change_wizard`)
- Reports: HK Inventory report, Inventory Variation report, Material Requisition report

**Web client (JS)**
- `home_kouzina_sales`: "Download Template" and "Import Marketplace Orders" buttons on the Sale Order list
- `hk_stock_update`: "Inventory Stock Update" entry in the cog menu

### Not gated (cannot be limited by group in Odoo)
- **Attribute-only changes** to standard views apply to everyone: label renames (SKU, EAN, Order Date, Delivery Date,
  Production Date), the Purchase Order picking type domain, hidden Invoice Address field, `duplicate="true"` on
  Product Variant (`hk_product_variant_duplicate`), and the Retail MO approval-button visibility.
- **Python behaviour** (negative-stock block, auto component lots, auto invoicing crons, Amazon and Shopify sync) is
  not UI and is unchanged.
- **Third-party connectors** were left alone on purpose: `shopify_ept`, `common_connector_library`,
  `odoo_multi_channel_sale`, `flipkart_odoo_bridge`, `wk_wizard_messages`.
- Own models keep their existing access rights (`ir.model.access.csv`); their screens are reachable only through the
  gated menus, buttons and actions.

### Known install-order gaps (already present, not from this change)
A fresh database needs these installed first: `purchase`, `wk_wizard_messages`, and `home_kouzina_sales` before
`mo_raw_material_consumption` (they use models or fields they do not declare in `depends`).

## Demo copy notes

This folder is a copy of the Home Kouzina modules (source repo: `home-kouzina/home_kouzina`), made without the
inner `.git` so it can be tracked in the demo environment repo.

Two root-level files from the source repo are intentionally **not** included here:
- `jan.py`: a one-off `odoo shell` script that backfills cancelled Shopify orders (Jul 2025 to Jun 2026) on the live
  system. It is a data-fix job, not a module.
- `shopify_ept.zip`: a 40 MB zip duplicating the `shopify_ept/` folder that is already in this directory.
