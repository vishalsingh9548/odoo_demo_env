# Manifest = the module's "ID card": its name, what it needs installed first, and which files to load.
{
    'name': 'Advance Manufacturing',
    'version': '18.0.1.0.0',
    'summary': 'Panel-by-panel manufacturing (serials, stages, quality, grades, pallets) switched on per company and per user group',
    'description': """
Advance Manufacturing
=====================
Adds unit-by-unit tracking on top of standard Odoo manufacturing.

Nothing here changes standard Odoo unless BOTH are true:
  1. The company has "Advance Manufacturing" switched on, and
  2. The user belongs to the "Advance Manufacturing" group.
Everyone else keeps using standard Odoo manufacturing.
    """,
    'author': 'Cloud Science Labs',
    'category': 'Manufacturing',
    'license': 'LGPL-3',
    # mrp = manufacturing, sale_mrp = sale order -> manufacturing order link.
    'depends': ['mrp', 'sale_mrp', 'stock', 'sale_management', 'hr', 'purchase', 'portal', 'account', 'maintenance'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/maintenance_stages.xml',
        'views/company_views.xml',
        'views/stage_views.xml',
        'views/unit_views.xml',
        'views/pallet_views.xml',
        'wizard/status_wizard_views.xml',
        'wizard/qc_fail_wizard_views.xml',
        'wizard/pallet_add_wizard_views.xml',
        'views/mrp_production_views.xml',
        'views/core_extra_views.xml',
        'views/bom_views.xml',
        'views/scan_views.xml',
        'views/sale_views.xml',
        'views/requisition_views.xml',
        'views/receipt_qc_views.xml',
        'views/scrap_views.xml',
        'views/more_views.xml',
        'views/purchase_sale_views.xml',
        'views/maintenance_views.xml',
        'report/custom_reports.xml',
        'report/report.xml',
        'report/journey.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'advance_manufacturing/static/src/js/serial_lookup_input.js',
            'advance_manufacturing/static/src/xml/serial_lookup_input.xml',
        ],
    },
    'installable': True,
    'application': False,
}
