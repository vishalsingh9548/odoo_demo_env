"""Demo data for the "Manufacturing Expo" company only.

How to run (from the odoo folder):
    myenv_18/bin/python3 odoo/odoo-bin shell -c solar_epc_split.conf -d solar_epc_v2 --no-http \
        < demo_modules/odoo_demo_env/advance_manufacturing/scripts/seed_expo_demo_data.py

What it does, in plain words:
  * Reads the panel products, their variants and their Bills of Materials from the
    reference database (crm_complete) - read only, nothing is changed there.
  * Creates the same kind of products, variants and BOMs for the company
    "Manufacturing Expo" ONLY (every record is stamped with that company).
  * Removes the old brand name from product names.
  * Puts starting stock of every component into the Expo warehouse.
  * Adds a few sample Process Stages.
It is safe to run twice: things that already exist are skipped.
"""
import re
import psycopg2

SOURCE_DB = 'crm_complete'
COMPANY_NAME = 'Manufacturing Expo'
# Which panel models to copy (watts as written in the reference product names).
PANEL_WATTS = ['450W', '500W', '540W']
# Starting stock for each component.
START_STOCK = 5000

# Units of measure in the reference database -> the nearest unit that exists here.
UOM_MAP = {'NOS': 'Units', 'Pcs': 'Units', 'Units': 'Units', 'Set': 'Units',
           'Sqm': 'm²', 'Kgs': 'kg', 'Litres': 'L'}

company = env['res.company'].search([('name', '=', COMPANY_NAME)], limit=1)
assert company, 'Company %s not found' % COMPANY_NAME
Env = env['product.template'].with_company(company)
src = psycopg2.connect(dbname=SOURCE_DB)
sc = src.cursor()


def clean(name):
    """Take the old brand name out of a product name."""
    name = re.sub(r'\bIB\s*solar\b\s*', '', name or '', flags=re.I)
    name = re.sub(r'\bIB\s+Logo\b', 'Logo', name, flags=re.I)
    return re.sub(r'\s+', ' ', name).strip()


def uom(name):
    """Find our unit of measure for a reference unit name."""
    return env['uom.uom'].search([('name', '=', UOM_MAP.get(name, 'Units'))], limit=1)


def first_value(jsonb):
    """Cost is stored per company as {company_id: value}; take the first one."""
    if isinstance(jsonb, dict) and jsonb:
        return float(next(iter(jsonb.values())))
    return 0.0


# ---- categories (global labels, no brand name) --------------------------------------------
Cat = env['product.category']
cat_panel = Cat.search([('name', '=', 'Solar Panels')], limit=1) or Cat.create({'name': 'Solar Panels'})
cat_comp = Cat.search([('name', '=', 'Solar Components')], limit=1) or Cat.create({'name': 'Solar Components'})

# ---- attribute shared by all panels --------------------------------------------------------
attr = env['product.attribute'].search([('name', '=', 'Cell Type')], limit=1) or env['product.attribute'].create(
    {'name': 'Cell Type', 'create_variant': 'always', 'display_type': 'radio'})
attr_values = {}
for v in ('Bifacial-NDCR', 'Bifacial-DCR', 'Mono-Perc-NDCR', 'Mono-Perc-DCR'):
    attr_values[v] = env['product.attribute.value'].search(
        [('attribute_id', '=', attr.id), ('name', '=', v)], limit=1) or env['product.attribute.value'].create(
        {'attribute_id': attr.id, 'name': v})

manufacture_route = env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
# A confirmed sale order only creates a manufacturing order when the product has the 'Replenish on Order (MTO)' route too.
mto_route = env['stock.route'].with_context(active_test=False).search([('name', 'ilike', 'Replenish on Order')], limit=1)
if mto_route and not mto_route.active:
    mto_route.active = True
routes = (manufacture_route | mto_route) if mto_route else manufacture_route
components = {}  # source product id -> our product.product


def get_component(src_pid):
    """Create (once) the component product that matches a reference component."""
    if src_pid in components:
        return components[src_pid]
    sc.execute("""select t.name->>'en_US', t.list_price, u.name->>'en_US', p.standard_price
                  from product_product p join product_template t on t.id = p.product_tmpl_id
                  join uom_uom u on u.id = t.uom_id where p.id = %s""", (src_pid,))
    name, list_price, uom_name, cost = sc.fetchone()
    name = clean(name)
    existing = env['product.product'].with_company(company).search(
        [('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not existing:
        existing = env['product.product'].with_company(company).create({
            'name': name, 'type': 'consu', 'is_storable': True, 'categ_id': cat_comp.id,
            'uom_id': uom(uom_name).id, 'uom_po_id': uom(uom_name).id,
            'list_price': list_price or 0.0, 'standard_price': first_value(cost),
            'sale_ok': False, 'purchase_ok': True, 'company_id': company.id,
            # Components are tracked by lots (like the real flow); finished panels stay by quantity.
            'tracking': 'lot',
        })
    components[src_pid] = existing
    return existing


created_panels = []
for watt in PANEL_WATTS:
    sc.execute("select id, name->>'en_US', list_price from product_template where name->>'en_US' ~ %s and "
               "exists (select 1 from mrp_bom b where b.product_tmpl_id = product_template.id and b.active) "
               "order by id limit 1", (r'SOLAR PANEL - %s' % watt,))
    row = sc.fetchone()
    if not row:
        print('skip: no reference product for', watt)
        continue
    src_tmpl, src_name, list_price = row
    name = 'Solar Panel %s' % watt
    # Which cell types does the reference model come in?
    sc.execute("""select p.id, v.name->>'en_US' from product_product p
                  join product_variant_combination c on c.product_product_id = p.id
                  join product_template_attribute_value tv on tv.id = c.product_template_attribute_value_id
                  join product_attribute_value v on v.id = tv.product_attribute_value_id
                  where p.product_tmpl_id = %s and p.active""", (src_tmpl,))
    # The reference data spells some values with stray spaces (e.g. 'Bifacial -DCR'); tidy them.
    src_variants = {pid: re.sub(r'\s*-\s*', '-', vname.strip()) for pid, vname in sc.fetchall()}
    values = [attr_values[v] for v in sorted(set(src_variants.values()), key=list(attr_values).index) if v in attr_values]
    tmpl = Env.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not tmpl:
        tmpl = Env.create({
            'name': name, 'type': 'consu', 'is_storable': True, 'categ_id': cat_panel.id,
            'is_finished_good': True, 'keep_mo_in_draft': True,
            'list_price': list_price or 0.0, 'company_id': company.id, 'sale_ok': True, 'purchase_ok': False,
            'route_ids': [(6, 0, routes.ids)] if routes else [],
            'attribute_line_ids': [(0, 0, {'attribute_id': attr.id, 'value_ids': [(6, 0, [v.id for v in values])]})],
        })
    if routes:
        tmpl.route_ids = [(6, 0, routes.ids)]
    tmpl.is_finished_good = True  # only finished goods can be manufactured in Advance Manufacturing mode
    # one BOM per variant, copied from the reference BOM of that variant
    for src_pid, vname in src_variants.items():
        variant = tmpl.product_variant_ids.filtered(
            lambda p: p.product_template_variant_value_ids.product_attribute_value_id.name == vname)[:1]
        if not variant:
            continue
        if env['mrp.bom'].search_count([('product_id', '=', variant.id), ('company_id', '=', company.id)]):
            continue
        sc.execute("select id, product_qty from mrp_bom where product_id = %s and active and type = 'normal' "
                   "order by id limit 1", (src_pid,))
        bom_row = sc.fetchone()
        if not bom_row:
            continue
        sc.execute("select product_id, product_qty from mrp_bom_line where bom_id = %s order by id", (bom_row[0],))
        lines = sc.fetchall()
        if not lines:
            continue
        bom_lines = []
        for comp_src, qty in lines:
            comp = get_component(comp_src)
            bom_lines.append((0, 0, {'product_id': comp.id, 'product_qty': qty, 'product_uom_id': comp.uom_id.id}))
        env['mrp.bom'].with_company(company).create({
            'product_tmpl_id': tmpl.id, 'product_id': variant.id, 'product_qty': bom_row[1] or 1.0,
            'type': 'normal', 'company_id': company.id, 'bom_line_ids': bom_lines,
        })
    created_panels.append(tmpl)

# ---- starting stock for components ---------------------------------------------------------
wh = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
Quant = env['stock.quant'].with_company(company)
Lot = env['stock.lot']
all_components = env['product.product'].with_company(company).search(
    [('company_id', '=', company.id), ('categ_id', '=', cat_comp.id)])
for comp in all_components:
    if comp.tracking != 'lot':
        comp.tracking = 'lot'  # existing components are switched to lot tracking
    # Stock on hand with no lot number is moved into one lot per product (idempotent).
    for quant in Quant.search([('product_id', '=', comp.id), ('location_id.usage', '=', 'internal'),
                               ('lot_id', '=', False), ('quantity', '>', 0)]):
        lot = Lot.search([('product_id', '=', comp.id), ('company_id', '=', company.id)], limit=1) or Lot.create({
            'name': 'LOT-%s-001' % comp.id, 'product_id': comp.id, 'company_id': company.id})
        qty, loc = quant.quantity, quant.location_id
        Quant._update_available_quantity(comp, loc, -qty)
        Quant._update_available_quantity(comp, loc, qty, lot_id=lot)
    have = sum(Quant.search([('product_id', '=', comp.id), ('location_id', '=', wh.lot_stock_id.id)]).mapped('quantity'))
    if have < START_STOCK:
        lot = Lot.search([('product_id', '=', comp.id), ('company_id', '=', company.id)], limit=1) or Lot.create({
            'name': 'LOT-%s-001' % comp.id, 'product_id': comp.id, 'company_id': company.id})
        Quant._update_available_quantity(comp, wh.lot_stock_id, START_STOCK - have, lot_id=lot)

# ---- sample process stages -----------------------------------------------------------------
Stage = env['advmfg.stage']
for seq, (nm, qc, att) in enumerate([
        ('Cell Stringing', False, False), ('Lamination', False, True), ('EL Testing', True, False),
        ('Framing', False, False), ('Final Flash Test', True, False)], start=1):
    if not Stage.search_count([('name', '=', nm), ('company_id', '=', company.id)]):
        Stage.create({'name': nm, 'sequence': seq * 10, 'qc_required': qc, 'attachment_required': att,
                      'company_id': company.id})

# ---- master data the new features need (all for Manufacturing Expo) --------------------------
Prefix = env['advmfg.serial.prefix']
if not Prefix.search_count([('company_id', '=', company.id)]):
    Prefix.create({'company_id': company.id, 'prefix': 'EXPO'})
Bank = env['advmfg.bank.account']
if not Bank.search_count([('company_id', '=', company.id)]):
    Bank.create({'bank_name': 'Demo Bank', 'account_name': 'Manufacturing Expo', 'account_number': '000123456789',
                 'branch_name': 'Main Branch', 'ifsc_code': 'DEMO0000001', 'company_id': company.id})
Loc = env['stock.location']
parent = wh.view_location_id
for name, flags in (('Store', {'is_mr_source_location': True}), ('Packaging', {'is_mo_stock': True}),
                    ('Rejection', {'for_scrap_order': True})):
    if not Loc.search_count([('name', '=', name), ('company_id', '=', company.id)]):
        Loc.create(dict({'name': name, 'usage': 'internal', 'location_id': parent.id, 'company_id': company.id}, **flags))
admin = env.ref('base.user_admin')
admin.write({'groups_id': [(4, env.ref('advance_manufacturing.group_advmfg_manager').id),
                           (4, env.ref('advance_manufacturing.group_sale_admin_approval').id),
                           (4, env.ref('advance_manufacturing.group_sale_second_approval').id)],
             'company_ids': [(4, company.id)]})
if not env['hr.employee'].search_count([('user_id', '=', admin.id), ('company_id', '=', company.id)]):
    env['hr.employee'].with_company(company).create({'name': admin.name, 'user_id': admin.id, 'company_id': company.id})
Master = env['material.request.approver.master']
for kind in ('admin_manager', 'standard_multi_level'):
    if not Master.search_count([('material_type', '=', kind), ('company_id', '=', company.id)]):
        Master.create({'material_type': kind, 'no_of_approvals': 2 if kind == 'standard_multi_level' else 1,
                       'company_id': company.id,
                       'approver_line_ids': [(0, 0, {'sequence': i, 'approver_id': [(6, 0, [admin.id])]})
                                             for i in range(1, (2 if kind == 'standard_multi_level' else 1) + 1)]})
# Machine maintenance: a source store, a workshop, a team, and the admin as manager.
for name, flag in (('Maintenance Store', 'is_maintenance_source_location'), ('Maintenance Shop', 'is_maintenance_location')):
    if not Loc.search_count([('name', '=', name), ('company_id', '=', company.id)]):
        Loc.create({'name': name, 'usage': 'internal', 'location_id': parent.id, 'company_id': company.id, flag: True})
if not env['maintenance.team'].search_count([('company_id', '=', company.id)]):
    env['maintenance.team'].create({'name': 'Expo Maintenance', 'company_id': company.id})
admin.write({'is_maintenance_manager': True, 'is_maintenance_store_person': True,
             'groups_id': [(4, env.ref('advance_manufacturing.group_purchase_approver').id),
                           (4, env.ref('advance_manufacturing.group_it_approver').id)]})
Partner = env['res.partner']
for pname, rank in (('Expo Customer', 'customer_rank'), ('Expo Vendor', 'supplier_rank')):
    if not Partner.search_count([('name', '=', pname)]):
        Partner.create({'name': pname, rank: 1})

env.cr.commit()
src.close()
print('PANELS:', [(t.name, len(t.product_variant_ids)) for t in created_panels])
print('BOMs for Expo:', env['mrp.bom'].search_count([('company_id', '=', company.id)]))
print('Components:', len(components))
print('Stages:', Stage.search([('company_id', '=', company.id)]).mapped('name'))
