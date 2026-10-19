{
    'name': 'CSL Solar EPC - BOQ & Costing',
    'version': '18.0.1.0.0',
    'category': 'Industries',
    'summary': 'Bill of Quantities and costing, raised from a Feasibility study; creates the Quotation.',
    'author': 'Cloud Science Labs',
    'website': 'https://cloudsciencelabs.com',
    'license': 'LGPL-3',
    'depends': [
        'csl_epc_feasibility',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/epc_rules.xml',
        'data/boq_sequence_data.xml',
        'views/epc_boq_views.xml',
        'views/epc_feasibility_views.xml',
        'views/sale_order_views.xml',
        'views/project_project_views.xml',
        'views/epc_menus.xml',
    ],
    'application': True,
    'installable': True,
}
