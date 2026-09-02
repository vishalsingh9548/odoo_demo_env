{
    # Basic identity of the app, shown in Apps list
    'name': 'CSL Solar EPC',
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
    'depends': [
        'mail',
        'hr_timesheet',
        'crm',
        'sale_management',
        'sale_project',
        'purchase',
        'project_purchase',
        'stock',
        'project_stock',
        'project_enterprise',
        'industry_fsm',
        'industry_fsm_sale',
        'industry_fsm_stock',
        'planning',
        'helpdesk',
        'helpdesk_fsm',
        'account',
    ],

    # Data files loaded on install, in dependency order: security first,
    # then sequences/config data, then views, then menus last (menus point
    # at actions/views that must already exist)
    'data': [
        'security/epc_security.xml',
        'security/ir.model.access.csv',
        'data/epc_sequence_data.xml',
        'data/epc_helpdesk_data.xml',
        'data/epc_quality_checkpoint_data.xml',
        'data/epc_inventory_data.xml',
        'views/epc_site_survey_views.xml',
        'views/epc_feasibility_views.xml',
        'views/epc_boq_views.xml',
        'views/epc_material_request_views.xml',
        'views/epc_dpr_views.xml',
        'views/epc_quality_checkpoint_views.xml',
        'views/epc_quality_check_views.xml',
        'report/epc_commissioning_report.xml',
        'views/epc_commissioning_views.xml',
        'views/epc_handover_views.xml',
        'views/epc_amc_contract_views.xml',
        'views/crm_lead_views.xml',
        'views/sale_order_views.xml',
        'views/project_project_views.xml',
        'views/project_task_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/helpdesk_ticket_views.xml',
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
