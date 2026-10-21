{
    'name': 'Unicel Greens - Recovery Planning',
    'version': '18.0.1.0.0',
    'summary': 'Expected hydromet outputs from the assay of the black mass consumed',
    'category': 'Manufacturing/Manufacturing',
    'author': 'Unicel Greens',
    'license': 'LGPL-3',
    'depends': ['ug_lot_assay'],
    'data': [
        'security/ir.model.access.csv',
        'security/ug_rules.xml',
        'views/product_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/ug_process_queue_views.xml',
    ],
    'demo': [
        'demo/ug_recovery_demo.xml',
    ],
    'installable': True,
}
