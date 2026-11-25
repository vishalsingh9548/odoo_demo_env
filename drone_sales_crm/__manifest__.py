{
    "name": "Drone - CRM & Sales",
    "summary": "Stringing job details, survey spans, certified-km billing and quotation layout for drone stringing jobs",
    "description": """
Strings pilot rope across transmission line spans by drone for EPC contractors.

This module adds, on top of standard CRM and Sales:

* Job details on the opportunity and quotation (line name, voltage, site, spans, total km)
* Survey spans on the opportunity, turned into span tasks on the job when the order is confirmed
* Client certifications that drive the delivered (invoiceable) km on the order
* A "Stringing job" block on the quotation / order PDF
* On install: the drone stringing products, the job project template and the
  "Drone stringing job" quotation template
""",
    "version": "18.0.1.7.0",
    "category": "Drone",
    "author": "Abas",
    "license": "LGPL-3",
    "depends": [
        "crm",
        "sale_crm",
        "sale_management",
        "sale_project",
        "project",
        "account",
        "mail",
    ],
    "data": [
        "security/drone_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/uom_precision_data.xml",
        "data/project_data.xml",
        "data/product_data.xml",
        "data/sale_order_template_data.xml",
        "views/crm_lead_views.xml",
        "views/sale_order_views.xml",
        "views/product_template_views.xml",
        "views/project_task_views.xml",
        "views/certification_views.xml",
        "views/project_project_views.xml",
        "views/res_config_settings_views.xml",
        "report/sale_report_templates.xml",
        "report/certification_report.xml",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
