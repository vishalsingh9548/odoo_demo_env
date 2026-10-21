{
    # Basic identity of the app, shown in Apps list
    'name': 'Solar Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Industries',
    'summary': 'End-to-end Solar EPC project management: Lead to O&M',
    'description': """
CSL Solar EPC
=============
Covers the complete Solar EPC (Engineering, Procurement, Construction) journey
for a solar company: Lead/CRM, Site Survey, Technical Feasibility, BOQ & Costing,
Quotation, Sales Order, Project Creation, Procurement, Inventory & Logistics,
Project Planning, Site Execution, Daily Progress Reports, Quality Checks,
Commissioning, Handover, Billing & Payments, O&M/AMC Management and Analytics.
""",
    'author': 'Cloud Science Labs',
    'website': 'https://cloudsciencelabs.com',
    'license': 'LGPL-3',

    # Other Odoo apps this module builds on top of, instead of reinventing them
    # The EPC pipeline is split into one module per stage; installing this
    # parent pulls in all of them. The parent itself only keeps what spans
    # every stage: the Dashboard, the Reporting menu/PDF reports and demo data.
    'depends': [
        'csl_epc_core',
        'csl_epc_site_survey',
        'csl_epc_feasibility',
        'csl_epc_boq',
        'csl_epc_material_request',
        'csl_epc_quality',
        'csl_epc_handover',
        'csl_epc_commissioning',
        'csl_epc_amc',
    ],

    'data': [
        'views/project_project_views.xml',
        'views/epc_reports_board.xml',
        'views/epc_menus.xml',
    ],

    # Sample data walking one lead all the way through the pipeline, so the
    # app can be explored/tested without having to create everything by hand
    'demo': [
        'demo/epc_demo.xml',
    ],

    # The Solar EPC Dashboard's frontend (Stage 18: Analytics & Reports) — a
    # live, click-through KPI screen, not a static picture
    'assets': {
        'web.assets_backend': [
            'csl_solar_epc/static/src/js/epc_dashboard.js',
            'csl_solar_epc/static/src/xml/epc_dashboard.xml',
            'csl_solar_epc/static/src/scss/epc_dashboard.scss',
        ],
    },

    'application': True,
    'installable': True,
}
