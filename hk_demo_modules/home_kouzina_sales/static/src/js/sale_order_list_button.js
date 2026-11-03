/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";

export class SaleListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        // Buttons below are only shown to members of the FMGC Access group
        this.hkAccess = false;
        onWillStart(async () => {
            this.hkAccess = await user.hasGroup("hk_access.group_hk_access");
        });
    }

    async DownloadTemplate() {
    await this.actionService.doAction({
        type: "ir.actions.act_window",
        res_model: "marketplace.template.download.wizard",
        views: [[false, "form"]],
        target: "new",
        context: {},
    });
    }

    async OnUpload() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "marketplace.order.import.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {},
        });
    }
}
registry.category("views").add("button_in_tree", {
    ...listView,
    Controller: SaleListController,
    buttonTemplate: "button_sale.ListView.Buttons",
});
