{
    'name': 'CSL Solar EPC - Site Survey',
    'version': '18.0.1.0.0',
    'category': 'Industries',
    'summary': 'Site Survey records, linked from the CRM opportunity.',
    'author': 'Cloud Science Labs',
    'website': 'https://cloudsciencelabs.com',
    'license': 'LGPL-3',
    'depends': [
        'csl_epc_core',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/epc_rules.xml',
        'data/site_survey_sequence_data.xml',
        'views/epc_site_survey_views.xml',
        'views/crm_lead_views.xml',
        'views/epc_menus.xml',
    ],
    'application': True,
    'installable': True,
}
