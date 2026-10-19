{
    'name': 'CSL Solar EPC - Feasibility',
    'version': '18.0.1.0.0',
    'category': 'Industries',
    'summary': 'Technical Feasibility studies raised from a Site Survey.',
    'author': 'Cloud Science Labs',
    'website': 'https://cloudsciencelabs.com',
    'license': 'LGPL-3',
    'depends': [
        'csl_epc_site_survey',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/epc_rules.xml',
        'data/feasibility_sequence_data.xml',
        'views/epc_feasibility_views.xml',
        'views/epc_site_survey_views.xml',
        'views/epc_menus.xml',
    ],
    'application': True,
    'installable': True,
}
