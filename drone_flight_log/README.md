# Drone - Flight Log & Equipment (`drone_flight_log`)

Flight operations for drone stringing jobs. Depends on `drone_sales_crm` (span tasks),
`maintenance` (drones and batteries as equipment) and `hr` (pilots).

## What it adds

| Feature | Where |
|---|---|
| Flight log per span: drone, pilot, batteries by serial number, take-off / landing, flight time, result, weather, wind | Drone Ops > Flight Logs, and the **Flights** button on each span task |
| Drones and batteries as Maintenance equipment, serial number required (unique, from the Maintenance app) | Drone Ops > Equipment > Drones / Batteries |
| Battery cycles (one per completed flight), flight time, last use, health: OK / Near limit (80 %) / Retire (100 %) | Battery form, "Drone Ops" tab, and the Batteries list |
| Drone flight hours and hours since last service | Drone form, "Drone Ops" tab, and the Drones list |
| Preventive service request when a drone reaches its service interval (one open request at a time) | Drone Ops > Equipment > Maintenance Requests |
| Corrective "retire battery" request when a battery reaches its cycle limit | Same |
| Completing a drone's maintenance request resets its "hours since service" | Automatic |
| Completing the repair of broken equipment puts it back in service **in the store, Free** (job cleared, location "Store") | Automatic |
| A flight with result "Rope passed" moves the span task to **Strung** (never backwards) | Automatic |
| Flight analysis per job, drone, pilot and result | Drone Ops > Reporting > Flight Analysis |
| Flights button on the job project | Project form |

## Rules

* Landing must be after take-off.
* The same drone or battery cannot be on two flights at the same time.
* A battery that reached its cycle limit, or scrapped equipment, cannot fly.
* A flight that did not pass the rope needs a reason.
* Completed flights cannot be deleted; cancel them instead (cancelled flights don't count).

## Setup

1. Equipment categories **Drones** and **Drone Batteries** are created on install
   (Maintenance > Configuration > Equipment Categories, field "Drone Equipment Type").
2. Create each drone and battery under Drone Ops > Equipment with its **serial number**.
   Set the **service interval** (flight hours) on drones and the **cycle limit** on batteries
   (manufacturer's figure; default 300).
3. Pilots are employees; the current user's employee is proposed by default.

Menus are visible to the **Drone / Stringing User** group. Logging flights needs Project
User rights; creating drones and batteries needs Maintenance (Equipment Manager) rights.

## Tests

```bash
odoo-bin -c debian/demo_nov24.conf -d <test_db> -i drone_flight_log --no-http \
  --test-enable --test-tags /drone_flight_log --stop-after-init
```
