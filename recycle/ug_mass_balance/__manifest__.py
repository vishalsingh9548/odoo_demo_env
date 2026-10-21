{
    'name': 'Unicel Greens - Mass Balance Reporting',
    'version': '18.0.1.0.0',
    'summary': 'Recycling overview dashboard, mass balance, element recovery, material output & cost, stock by stage',
    'category': 'Manufacturing/Manufacturing',
    'author': 'Unicel Greens',
    'license': 'LGPL-3',
    'depends': ['ug_recovery_planning', 'ug_epr', 'mrp_account'],
    'data': [
        'security/ir.model.access.csv',
        'security/ug_rules.xml',
        'data/ug_recycling_overview_data.xml',
        'views/ug_report_views.xml',
        'views/ug_recycling_overview_views.xml',
        'views/ug_menus.xml',
    ],
    'installable': True,
    'auto_install': False,
}
