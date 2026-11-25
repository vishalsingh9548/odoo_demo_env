from datetime import datetime, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDroneFlightLog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.stage_planned = ref("drone_sales_crm.task_type_planned")
        cls.stage_strung = ref("drone_sales_crm.task_type_strung")
        cls.stage_certified = ref("drone_sales_crm.task_type_certified")
        cls.project = cls.env["project.project"].create({
            "name": "Test stringing job",
            "type_ids": [(6, 0, (
                cls.stage_planned | ref("drone_sales_crm.task_type_in_progress")
                | cls.stage_strung | cls.stage_certified).ids)],
        })
        cls.span = cls.env["project.task"].create({
            "name": "Span 1: T1 - T2", "project_id": cls.project.id, "is_span": True,
            "tower_from": "T1", "tower_to": "T2", "span_length_m": 600, "stage_id": cls.stage_planned.id,
        })
        cls.pilot = cls.env["hr.employee"].create({"name": "Test Pilot"})
        Equipment = cls.env["maintenance.equipment"]
        cls.drone = Equipment.create({
            "name": "Test drone", "serial_no": "TDRN-01",
            "category_id": ref("drone_flight_log.equipment_category_drone").id,
            "service_interval_hours": 1.0,
        })
        battery_category = ref("drone_flight_log.equipment_category_battery").id
        cls.bat1, cls.bat2 = Equipment.create([
            {"name": "Test battery 1", "serial_no": "TBAT-01", "category_id": battery_category,
             "battery_cycle_limit": 5},
            {"name": "Test battery 2", "serial_no": "TBAT-02", "category_id": battery_category,
             "battery_cycle_limit": 5},
        ])
        cls.start = datetime(2026, 1, 5, 9, 0)

    def _flight(self, offset_min=0, minutes=10, batteries=None, result="success", **extra):
        takeoff = self.start + timedelta(minutes=offset_min)
        return self.env["drone.flight.log"].create(dict({
            "task_id": self.span.id,
            "drone_id": self.drone.id,
            "pilot_id": self.pilot.id,
            "battery_ids": [(6, 0, (batteries or self.bat1).ids)],
            "takeoff_time": takeoff,
            "landing_time": takeoff + timedelta(minutes=minutes),
            "result": result,
        }, **extra))

    def test_01_duration_and_times(self):
        flight = self._flight(minutes=9)
        self.assertAlmostEqual(flight.duration_min, 9.0)
        self.assertTrue(flight.name.startswith("FL/"))
        with self.assertRaises(ValidationError):
            flight.landing_time = flight.takeoff_time - timedelta(minutes=1)

    def test_02_done_flight_counts_cycles_and_hours(self):
        flight = self._flight(minutes=12, batteries=self.bat1 | self.bat2)
        self.assertEqual(self.bat1.drone_flight_count, 0, "Draft flights do not count.")
        flight.action_done()
        for battery in self.bat1 | self.bat2:
            self.assertEqual(battery.drone_flight_count, 1)
            self.assertAlmostEqual(battery.drone_flight_minutes, 12.0)
        self.assertAlmostEqual(self.drone.drone_flight_minutes, 12.0)
        self.assertEqual(self.drone.drone_last_flight_date, flight.takeoff_time)
        flight.action_cancel()
        self.assertEqual(self.bat1.drone_flight_count, 0, "Cancelled flights do not count.")

    def test_03_battery_health_and_retirement(self):
        for i in range(4):
            self._flight(offset_min=i * 20).action_done()
        self.assertEqual(self.bat1.battery_health, "warning")  # 4 of 5 = 80%
        self._flight(offset_min=100).action_done()
        self.assertEqual(self.bat1.battery_health, "retire")
        request = self.env["maintenance.request"].search([
            ("equipment_id", "=", self.bat1.id), ("maintenance_type", "=", "corrective")])
        self.assertEqual(len(request), 1, "Reaching the cycle limit opens one retirement request.")
        with self.assertRaises(UserError):
            self._flight(offset_min=200).action_done()

    def test_04_no_double_booking(self):
        self._flight(offset_min=0, minutes=15)
        with self.assertRaises(ValidationError, msg="Same battery in an overlapping flight"):
            self._flight(offset_min=10, minutes=15, batteries=self.bat1)
        # Back-to-back flights are fine.
        self._flight(offset_min=15, minutes=10, batteries=self.bat2)

    def test_05_success_moves_span_to_strung(self):
        failed = self._flight(result="aborted", abort_reason="Wind above limit")
        failed.action_done()
        self.assertEqual(self.span.stage_id, self.stage_planned)
        self._flight(offset_min=30).action_done()
        self.assertEqual(self.span.stage_id, self.stage_strung)
        self.span.stage_id = self.stage_certified
        self._flight(offset_min=60).action_done()
        self.assertEqual(self.span.stage_id, self.stage_certified, "Never moves a span backwards.")

    def test_06_failed_flight_needs_reason(self):
        with self.assertRaises(UserError):
            self._flight(result="retry").action_done()

    def test_07_drone_service_request(self):
        self._flight(minutes=40).action_done()
        Request = self.env["maintenance.request"]
        domain = [("equipment_id", "=", self.drone.id), ("maintenance_type", "=", "preventive")]
        self.assertFalse(Request.search(domain))
        self._flight(offset_min=60, minutes=30).action_done()  # 70 min > 1 h interval
        request = Request.search(domain)
        self.assertEqual(len(request), 1)
        self._flight(offset_min=120, minutes=10).action_done()
        self.assertEqual(len(Request.search(domain)), 1, "Only one open service request per drone.")
        done_stage = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        request.stage_id = done_stage
        self.assertTrue(self.drone.last_service_date)
        self.assertAlmostEqual(self.drone.hours_since_service, 0.0)

    def test_08_serial_number_required_and_unique(self):
        battery_category = self.env.ref("drone_flight_log.equipment_category_battery").id
        with self.assertRaises(ValidationError):
            self.env["maintenance.equipment"].create({"name": "No serial", "category_id": battery_category})
        # Uniqueness comes from the standard Maintenance app (SQL constraint on serial_no).
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["maintenance.equipment"].create({
                "name": "Duplicate", "serial_no": "TBAT-01", "category_id": battery_category})

    def test_09_task_and_project_counts(self):
        self._flight(minutes=8).action_done()
        self._flight(offset_min=30, minutes=7)
        self.assertEqual(self.span.drone_flight_count, 2)
        self.assertAlmostEqual(self.span.drone_flight_minutes, 8.0, msg="Only completed flights add time.")
        self.assertEqual(self.project.drone_flight_count, 2)
        with self.assertRaises(UserError):
            self.span.drone_flight_ids.filtered(lambda f: f.state == "done").unlink()

    # --- Breakdowns and replacement requests --------------------------------------------------

    def _report_breakdown(self, flight, equipment, **extra):
        wizard = self.env["drone.breakdown.wizard"].with_context(active_id=flight.id).create(dict({
            "flight_id": flight.id,
            "equipment_ids": [(6, 0, equipment.ids)],
            "breakdown_type": "malfunction",
            "description": "Battery swelling noticed after landing",
            "site_location": "Site: Test",
        }, **extra))
        wizard.action_confirm()
        return wizard

    def test_10_breakdown_takes_equipment_out_and_opens_requests(self):
        flight = self._flight(batteries=self.bat1 | self.bat2)
        self._report_breakdown(flight, self.bat1)
        self.assertEqual(self.bat1.drone_operational_state, "broken")
        self.assertEqual(self.bat2.drone_operational_state, "ok")
        repair = flight.repair_request_ids
        self.assertEqual(len(repair), 1)
        self.assertEqual((repair.equipment_id, repair.maintenance_type, repair.priority),
                         (self.bat1, "corrective", "3"))
        request = flight.equipment_request_ids
        self.assertEqual(len(request), 1)
        self.assertEqual((request.broken_equipment_id, request.equipment_type, request.state),
                         (self.bat1, "battery", "requested"))
        self.assertTrue(request.activity_ids, "Someone is asked to send the replacement.")
        self.assertEqual(flight.result, "aborted")
        self.assertIn(self.bat1.name, flight.abort_reason)
        flight.action_done()  # the flight it broke on can still be closed (as aborted)

    def test_11_broken_equipment_cannot_fly_until_repaired(self):
        flight = self._flight(batteries=self.bat1)
        self._report_breakdown(flight, self.bat1, request_replacement=False)
        flight.action_done()
        self.assertFalse(flight.equipment_request_ids)
        next_flight = self._flight(offset_min=60, batteries=self.bat1)
        with self.assertRaises(UserError):
            next_flight.action_done()
        done_stage = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        flight.repair_request_ids.stage_id = done_stage
        self.assertEqual(self.bat1.drone_operational_state, "ok", "A completed repair puts it back in service.")
        self.assertEqual(self.bat1.drone_availability, "free", "Repaired equipment is back in the store, free.")
        self.assertFalse(self.bat1.drone_project_id)
        self.assertEqual(self.bat1.location, "Store")
        next_flight.action_done()

    def test_12_replacement_workflow_and_new_flight(self):
        spare = self.env["maintenance.equipment"].create({
            "name": "Spare battery", "serial_no": "TBAT-09",
            "category_id": self.env.ref("drone_flight_log.equipment_category_battery").id,
        })
        flight = self._flight(batteries=self.bat1 | self.bat2)
        self._report_breakdown(flight, self.bat1)
        request = flight.equipment_request_ids
        with self.assertRaises(UserError, msg="A replacement must be chosen before dispatch"):
            request.action_dispatch()
        with self.assertRaises(ValidationError, msg="Must be the same type"):
            request.replacement_equipment_id = self.drone
        request.action_approve()
        request.replacement_equipment_id = spare
        request.action_dispatch()
        self.assertEqual(request.state, "dispatched")
        self.assertEqual(spare.location, "Site: Test")
        request.action_receive()
        self.assertEqual(request.state, "received")
        action = request.action_new_flight()
        new_flight = self.env["drone.flight.log"].browse(action["res_id"])
        self.assertEqual(new_flight.task_id, flight.task_id)
        self.assertEqual(new_flight.battery_ids, spare | self.bat2, "The broken battery is swapped for the spare.")
        self.assertEqual(new_flight.state, "draft")

    def test_13_broken_drone_replaced(self):
        spare_drone = self.env["maintenance.equipment"].create({
            "name": "Spare drone", "serial_no": "TDRN-09",
            "category_id": self.env.ref("drone_flight_log.equipment_category_drone").id,
        })
        flight = self._flight()
        self._report_breakdown(flight, self.drone, breakdown_type="crash")
        request = flight.equipment_request_ids
        self.assertEqual(request.equipment_type, "drone")
        request.replacement_equipment_id = spare_drone
        request.action_dispatch()
        request.action_receive()
        new_flight = self.env["drone.flight.log"].browse(request.action_new_flight()["res_id"])
        self.assertEqual(new_flight.drone_id, spare_drone)

    # --- Availability and assigned job -----------------------------------------------------------

    def test_14_availability_follows_use(self):
        self.assertEqual(self.drone.drone_availability, "free")
        self._flight().action_done()
        self.assertEqual(self.drone.drone_project_id, self.project)
        self.assertEqual(self.bat1.drone_project_id, self.project)
        self.assertEqual(self.drone.drone_availability, "busy")
        self.drone.action_drone_release()
        self.assertEqual(self.drone.drone_availability, "free")
        self.assertEqual(self.drone.location, "Store")
        self._report_breakdown(self._flight(offset_min=60), self.bat1, request_replacement=False)
        self.assertEqual(self.bat1.drone_availability, "broken")
        self.bat2.scrap_date = "2026-01-10"
        self.assertEqual(self.bat2.drone_availability, "retired")

    def test_15_dispatched_replacement_is_on_the_job(self):
        spare = self.env["maintenance.equipment"].create({
            "name": "Spare battery", "serial_no": "TBAT-08",
            "category_id": self.env.ref("drone_flight_log.equipment_category_battery").id,
        })
        flight = self._flight()
        self._report_breakdown(flight, self.bat1)
        request = flight.equipment_request_ids
        request.replacement_equipment_id = spare
        request.action_dispatch()
        self.assertEqual(spare.drone_project_id, self.project)
        self.assertEqual(spare.drone_availability, "busy")

    def test_16_fleet_board_shows_all_columns(self):
        groups = self.env["maintenance.equipment"].web_read_group(
            [("drone_equipment_type", "!=", False)], ["drone_availability"], ["drone_availability"])["groups"]
        self.assertEqual({g["drone_availability"] for g in groups}, {"free", "busy", "broken", "retired"})
        arch = self.env["maintenance.equipment"].get_views(
            [(self.env.ref("drone_flight_log.maintenance_equipment_view_kanban_drone").id, "kanban")]
        )["views"]["kanban"]["arch"]
        self.assertIn("drone_project_id", arch)

    def test_17_board_helpers(self):
        self.assertEqual(self.bat1.drone_kanban_color, 10)  # free: green
        for i in range(4):
            self._flight(offset_min=i * 20).action_done()
        self.assertEqual(self.bat1.drone_usage_percent, 80)  # 4 of 5 cycles
        self.assertEqual(self.bat1.drone_kanban_color, 4)  # on a job: blue
        self.assertGreater(self.drone.drone_usage_percent, 0)

    # --- Phone flow -----------------------------------------------------------------------------

    def test_18_one_tap_flight(self):
        action = self.span.action_log_drone_flight()
        self.assertEqual(action["context"]["default_task_id"], self.span.id)
        flight = self.env["drone.flight.log"].create({
            "task_id": self.span.id, "drone_id": self.drone.id, "pilot_id": self.pilot.id,
            "battery_ids": [(6, 0, self.bat1.ids)], "takeoff_time": "2026-01-05 08:00:00",
        })
        with self.assertRaises(UserError, msg="No landing time yet"):
            flight.action_done()
        flight.action_landed_now()
        self.assertTrue(flight.landing_time)
        flight.action_done()
        self.assertEqual(flight.state, "done")
        flight2 = self.env["drone.flight.log"].create({
            "task_id": self.span.id, "drone_id": self.drone.id, "pilot_id": self.pilot.id,
            "battery_ids": [(6, 0, self.bat2.ids)], "takeoff_time": "2026-01-06 08:00:00",
        })
        flight2.action_takeoff_now()
        self.assertFalse(flight2.landing_time)

    def test_19_phone_views_open_on_cards(self):
        for xmlid in ("drone_flight_log.action_drone_flight_log", "drone_flight_log.action_drone_equipment_request"):
            action = self.env.ref(xmlid)
            self.assertEqual(action.mobile_view_mode, "kanban")
            self.assertIn("kanban", action.view_mode)
        for model in ("drone.flight.log", "drone.equipment.request"):
            self.assertTrue(self.env[model].get_views([(False, "kanban")])["views"]["kanban"]["arch"])

    def test_20_form_has_one_battery_field(self):
        """The same x2many twice on a form breaks loading in Odoo 18: keep a single one."""
        arch = self.env["drone.flight.log"].get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertEqual(arch.count('name="battery_ids"'), 1)

    def test_21_log_flight_from_task_tab(self):
        """Flights can be added on the span task's Flight Log tab."""
        with Form(self.span) as task_form:
            with task_form.drone_flight_ids.new() as line:
                line.drone_id = self.drone
                line.battery_ids.add(self.bat1)
                line.pilot_id = self.pilot
                line.takeoff_time = self.start
        flight = self.span.drone_flight_ids
        self.assertEqual(len(flight), 1)
        self.assertEqual((flight.task_id, flight.project_id, flight.state), (self.span, self.project, "draft"))
        self.assertEqual(flight.battery_ids, self.bat1)
        flight.action_landed_now()
        flight.action_done()
        self.assertEqual(flight.state, "done")
        self.assertEqual(self.span.drone_flight_count, 1)
        arch = self.env["project.task"].get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn('name="drone_flight_log"', arch)
        self.assertEqual(arch.count('name="drone_flight_ids"'), 1)
