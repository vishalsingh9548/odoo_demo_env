{
    'name': 'CSL Solar EPC - Handover',
    'version': '18.0.1.0.0',
    'category': 'Industries',
    'summary': 'Handover & Closure records.',
    'author': 'Cloud Science Labs',
    'website': 'https://cloudsciencelabs.com',
    'license': 'LGPL-3',
    'depends': [
        'csl_epc_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/handover_sequence_data.xml',
        'views/epc_handover_views.xml',
        'views/epc_menus.xml',
    ],
    'application': True,
    'installable': True,
}
