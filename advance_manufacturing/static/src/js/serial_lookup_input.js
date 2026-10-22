/** @odoo-module **/
// The scan box: when a serial is typed or scanned, ask the server what to do and open its details window.
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SerialLookupInput extends Component {
    static template = "advance_manufacturing.SerialLookupInput";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    // Runs when the typed value changes (scanners press Enter after the serial).
    async onSerialChange(ev) {
        const serial = ev.target.value.trim();
        if (!serial) {
            return;
        }
        const result = await this.orm.call("advmfg.scan.wizard", "lookup_serial", [serial]);
        if (result.status === "ok") {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: result.res_model || "advmfg.serial.lookup.wizard",
                res_id: result.wizard_id,
                views: [[false, "form"]],
                target: "new",
                name: result.title,
            });
        } else {
            const types = { info: "info", completed: "info", cancel: "warning", missing: "danger", failed: "warning" };
            const titles = { missing: "Validation Error", failed: "Serial Lookup Info" };
            this.notification.add(result.message, {
                type: types[result.status] || "info",
                title: titles[result.status] || "Message",
            });
            ev.target.value = "";
        }
    }
}

registry.category("fields").add("advmfg_serial_lookup_input", {
    component: SerialLookupInput,
    supportedTypes: ["char"],
});
