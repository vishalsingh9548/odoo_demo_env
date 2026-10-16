{
    'name': 'Unicel Greens - EPR Certificates',
    'version': '18.0.1.0.0',
    'summary': 'EPR certificate register (Battery Waste Management Rules 2022), sales and waste manifests',
    'category': 'Manufacturing/Manufacturing',
    'author': 'Unicel Greens',
    'license': 'LGPL-3',
    'depends': ['ug_recycling_base', 'sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'security/ug_rules.xml',
        'data/ug_epr_data.xml',
        'views/ug_epr_certificate_views.xml',
        'views/ug_waste_manifest_views.xml',
        'views/ug_epr_category_views.xml',
        'views/mrp_production_views.xml',
        'views/res_config_settings_views.xml',
        'views/ug_menus.xml',
    ],
    'demo': [
        'demo/ug_epr_demo.xml',
    ],
    'installable': True,
}
