{
    'name': 'Grando Solar Management',
    'version': '1.0',
    'category': 'Solar',
    'summary': 'Solar EPC Management',
    'author': 'Your Company',
    'depends': [
        'crm',
        'sale_management',
        'project',
        'contacts',
        'mail',
    ],
   
   'data': [
    'security/solar_security.xml',
    'security/ir.model.access.csv',
     'data/sequence.xml',
    'views/crm_lead_views.xml',
    'views/solar_site_survey_views.xml',
    'views/solar_design_views.xml',
    'views/sale_order_views.xml',
    'views/solar_registration_views.xml',
    'views/solar_installation_views.xml',
    'views/solar_discom_views.xml',
    'views/menu_views.xml',
    'views/crm_lead_survey_views.xml',
],
    'demo': [
    'demo/solar_demo.xml',
],
    'installable': True,
    'application': True,
}
