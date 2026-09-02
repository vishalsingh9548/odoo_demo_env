/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { formatMonetary } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

// Solar-EPC colour palette for the dashboard: warm solar-panel blue/orange as
// the accent (instead of a generic brand colour), plus one clear colour each
// for the three Quality Check results so Pass/Fail/Pending always read the
// same way across every chart on the page.
const CHART_COLORS = {
    pass: "#46b980",
    fail: "#e0684f",
    pending: "#eba93f",
    accent: "#2f7fb6",
    grid: "#eaecf1",
    // A light sky blue for "RFQ Sent" on the Procurement Status chart —
    // there was no "warn" key in this palette, so that bar was quietly
    // falling back to Chart.js's default black.
    sentLight: "#7ec8e3",
    categorical: ["#2f7fb6", "#eba93f", "#46b980", "#8b8fd6", "#e0684f", "#6fc48a"],
};

const CHART_ANIMATION = { duration: 700, easing: "easeOutQuart" };
const NO_TOGGLE_LEGEND_CLICK = () => {};

export class EpcDashboard extends Component {
    static template = "csl_solar_epc.EpcDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.charts = {};
        this.chartRefs = {
            portfolioPhase: useRef("portfolioPhaseChart"),
            pipelineActivity: useRef("pipelineActivityChart"),
            amcHealth: useRef("amcHealthChart"),
            procurementStatus: useRef("procurementStatusChart"),
        };

        this.state = useState({ loading: true, data: null });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadDashboardData();
        });

        onWillUnmount(() => {
            Object.values(this.charts).forEach((chart) => chart && chart.destroy());
        });

        // Charts read from <canvas> nodes via t-ref, which only exist once Owl has
        // actually patched the DOM for the loaded state - useEffect's callback is
        // guaranteed to run after that patch, unlike a plain post-await call.
        useEffect(
            () => {
                if (!this.state.loading) {
                    this.renderCharts();
                }
            },
            () => [this.state.loading, this.state.data],
        );
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.data = await this.orm.call("epc.dashboard", "get_dashboard_data", []);
        this.state.loading = false;
    }

    formatMoney(value) {
        return formatMonetary(value || 0, { currencyId: this.state.data && this.state.data.currency_id });
    }

    // Every tile/chart click drills into a list view built from the EXACT domain
    // the backend used to compute that number, so what opens always matches what
    // was shown on the dashboard.
    openList(domain, name, resModel) {
        if (!domain) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: resModel,
            domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openRecord(resModel, resId) {
        if (!resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ------------------------------------------------------------------
    // Charts
    // ------------------------------------------------------------------
    renderCharts() {
        if (!this.state.data) {
            return;
        }
        this._renderPortfolioPhaseChart();
        this._renderPipelineActivityChart();
        this._renderAmcHealthChart();
        this._renderProcurementStatusChart();
    }

    _destroy(key) {
        if (this.charts[key]) {
            this.charts[key].destroy();
            this.charts[key] = undefined;
        }
    }

    _renderPortfolioPhaseChart() {
        this._destroy("portfolioPhase");
        const el = this.chartRefs.portfolioPhase.el;
        if (!el) {
            return;
        }
        const phase = this.state.data.portfolio_phase;
        this.charts.portfolioPhase = new Chart(el, {
            type: "doughnut",
            data: {
                labels: phase.labels,
                datasets: [{
                    data: phase.counts,
                    backgroundColor: CHART_COLORS.categorical,
                    borderColor: "#fff",
                    borderWidth: 2,
                    hoverOffset: 10,
                }],
            },
            options: {
                animation: CHART_ANIMATION,
                plugins: { legend: { position: "bottom", onClick: NO_TOGGLE_LEGEND_CLICK } },
                maintainAspectRatio: false,
                onClick: (_ev, elements) => {
                    if (!elements.length) return;
                    const i = elements[0].index;
                    this.openList(phase.domains[i], `${_t("Projects")} - ${phase.labels[i]}`, "project.project");
                },
            },
        });
    }

    // How much open work is sitting at each pipeline stage right now — an
    // operational view (what needs attention), not a financial one
    _renderPipelineActivityChart() {
        this._destroy("pipelineActivity");
        const el = this.chartRefs.pipelineActivity.el;
        if (!el) {
            return;
        }
        const pipeline = this.state.data.pipeline_activity;
        this.charts.pipelineActivity = new Chart(el, {
            type: "bar",
            data: {
                labels: pipeline.labels,
                datasets: [{
                    label: _t("Open Items"), data: pipeline.counts, backgroundColor: CHART_COLORS.accent,
                    borderRadius: 6, borderSkipped: false, maxBarThickness: 28,
                }],
            },
            options: {
                animation: CHART_ANIMATION,
                indexAxis: "y",
                plugins: { legend: { display: false } },
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: CHART_COLORS.grid } },
                    y: { grid: { display: false } },
                },
                onClick: (_ev, elements) => {
                    if (!elements.length) return;
                    const i = elements[0].index;
                    const { model, domain } = pipeline.domains[i];
                    this.openList(domain, `${_t("Pipeline")} - ${pipeline.labels[i]}`, model);
                },
            },
        });
    }

    // Every AMC contract, by status — the health of the maintenance book at a
    // glance, drawn as a funnel (Draft -> Active -> Expired -> Terminated)
    // instead of a pie so the natural progression of a contract's lifecycle
    // reads top-to-bottom. Chart.js has no built-in funnel type, so this is
    // a standard funnel-without-a-plugin trick: a horizontal bar chart where
    // each bar is a "floating" [-count/2, +count/2] segment centered on the
    // same vertical axis, which reads as a symmetric funnel narrowing down
    // the page instead of a plain bar list.
    _renderAmcHealthChart() {
        this._destroy("amcHealth");
        const el = this.chartRefs.amcHealth.el;
        if (!el) {
            return;
        }
        const amc = this.state.data.amc_contract_health;
        // Same fix as the Procurement Status chart below: there was no
        // "warn" key in the palette, so "Expired" would render as an
        // undefined-color (black) bar the moment its count went above 0.
        const rawColors = [CHART_COLORS.pass, CHART_COLORS.accent, CHART_COLORS.pending, CHART_COLORS.fail];
        // A funnel only reads as a funnel if the bars actually narrow going
        // down the page. The backend always returns Draft/Active/Expired/
        // Terminated in that fixed order, which is rarely in descending
        // count order (e.g. 1/3/0/1 doesn't taper at all) -- sorting by
        // count here, largest first, is what turns this into a real funnel
        // shape instead of a lopsided bar chart with a "missing" small bar.
        // A stage with 0 contracts is dropped entirely (not shown as an
        // empty zero-width row) -- there's nothing to fill a funnel stage
        // with, so it shouldn't take up a slot in it.
        const order = amc.labels
            .map((_l, i) => i)
            .filter((i) => amc.counts[i] > 0)
            .sort((a, b) => amc.counts[b] - amc.counts[a]);
        const labels = order.map((i) => amc.labels[i]);
        const counts = order.map((i) => amc.counts[i]);
        const colors = order.map((i) => rawColors[i]);
        const domains = order.map((i) => amc.domains[i]);
        this.charts.amcHealth = new Chart(el, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    data: counts.map((count) => [-(count / 2), count / 2]),
                    backgroundColor: colors,
                    borderRadius: 4,
                    borderSkipped: false,
                    maxBarThickness: 40,
                }],
            },
            options: {
                animation: CHART_ANIMATION,
                indexAxis: "y",
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        onClick: NO_TOGGLE_LEGEND_CLICK,
                        // The chart has one dataset (multi-coloured per bar), so
                        // Chart.js's default legend (one entry per dataset) would
                        // show nothing useful — build the label/colour pairs by
                        // hand instead, the same way the doughnut charts' legend
                        // already reads one entry per slice.
                        labels: {
                            generateLabels: () => labels.map((label, i) => ({
                                text: `${label} (${counts[i]})`,
                                fillStyle: colors[i],
                                strokeStyle: colors[i],
                                index: i,
                            })),
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${counts[ctx.dataIndex]}`,
                        },
                    },
                },
                scales: {
                    x: { display: false, grid: { display: false } },
                    y: { grid: { display: false } },
                },
                onClick: (_ev, elements) => {
                    if (!elements.length) return;
                    const i = elements[0].index;
                    this.openList(domains[i], `${_t("AMC Contracts")} - ${labels[i]}`, "epc.amc.contract");
                },
            },
        });
    }

    // Purchase Orders raised for a project, by stage in the RFQ-to-PO
    // process — deliberately a status/process view, not a spend figure
    _renderProcurementStatusChart() {
        this._destroy("procurementStatus");
        const el = this.chartRefs.procurementStatus.el;
        if (!el) {
            return;
        }
        const proc = this.state.data.procurement_status;
        this.charts.procurementStatus = new Chart(el, {
            type: "bar",
            data: {
                labels: proc.labels,
                datasets: [{
                    label: _t("Purchase Orders"), data: proc.counts,
                    backgroundColor: [
                        CHART_COLORS.pending, CHART_COLORS.sentLight, CHART_COLORS.categorical[3],
                        CHART_COLORS.accent, CHART_COLORS.pass,
                    ],
                    borderRadius: 6, borderSkipped: false, maxBarThickness: 46,
                }],
            },
            options: {
                animation: CHART_ANIMATION,
                plugins: { legend: { display: false } },
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: CHART_COLORS.grid } },
                    x: { grid: { display: false } },
                },
                onClick: (_ev, elements) => {
                    if (!elements.length) return;
                    const i = elements[0].index;
                    this.openList(proc.domains[i], `${_t("Purchase Orders")} - ${proc.labels[i]}`, "purchase.order");
                },
            },
        });
    }
}

registry.category("actions").add("epc_dashboard", EpcDashboard);
