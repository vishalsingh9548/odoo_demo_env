{
    "name": "Drone - Flight Log & Equipment",
    "summary": "Flight log per span, drones and batteries tracked by serial number, battery cycles and drone servicing",
    "description": """
Flight operations for drone stringing jobs, on top of Drone - CRM & Sales:

* Flight log on each span task: drone, pilot, batteries (by serial number), take-off and
  landing time, result, weather and wind
* Drones and batteries are Maintenance equipment with a unique serial number
* Battery charge cycles, flight time, last use and health (OK / near limit / retire)
* Drone flight hours, with a preventive service request when the service interval is reached
* A successful flight moves the span task to "Strung"
* Checks: no retired battery on a flight, no drone or battery on two flights at once
* Breakdowns: "Report Breakdown" on a flight takes the equipment out of service, opens a
  high-priority repair request and a replacement request (requested > approved > dispatched >
  received) to send a working unit to site; a completed repair puts the equipment back in service
""",
    "version": "18.0.1.8.1",
    "category": "Drone",
    "author": "Abas",
    "license": "LGPL-3",
    "depends": [
        "drone_sales_crm",
        "project",
        "maintenance",
        "hr",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/equipment_category_data.xml",
        "views/flight_log_views.xml",
        "views/equipment_request_views.xml",
        "views/breakdown_wizard_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/project_task_views.xml",
        "views/project_project_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
