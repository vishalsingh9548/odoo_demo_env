/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { cookie } from "@web/core/browser/cookie";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { formatFloat, formatInteger, formatMonetary } from "@web/views/fields/formatters";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

// One colour per meaning, reused by every stage dashboard so Pass / Fail /
// Warning always read the same. "accent" is the stage's own colour.
const COLORS = {
    pass: "#7fb6ee",
    fail: "#9a8be3",
    warn: "#bcaef0",
    neutral: "#dbe1f2",
    info: "#8dbdf2",
    violet: "#b4a7f0",
};
const COLORS_DARK = {
    pass: "#8cc2f5",
    fail: "#ae9ff0",
    warn: "#c9bdf5",
    neutral: "#4a5278",
    info: "#8ad8e6",
    violet: "#b9aef5",
};
const CATEGORICAL_DARK = ["accent", "#b9aef5", "#8cc2f5", "#cdd6f8", "#8ad8e6", "#a9bcf8", "#5a6390"];
const CATEGORICAL = ["accent", "#b4a7f0", "#8dbdf2", "#c9d3f5", "#86d0e0", "#a3b5f7", "#dbe1f2"];
// Mixes a #rrggbb colour towards white (used to brighten the stage colour on dark)
function lighten(hex, amount) {
    const n = parseInt(hex.slice(1), 16);
    const mix = (c) => Math.round(c + (255 - c) * amount);
    const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(mix);
    return "#" + rgb.map((c) => c.toString(16).padStart(2, "0")).join("");
}
const REFRESH_MS = 120000;

export class EpcStageDashboard extends Component {
    static template = "csl_epc_core.StageDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.root = useRef("root");
        // Follows Odoo's own light/dark switch (user menu), which is stored in this cookie
        this.dark = cookie.get("color_scheme") === "dark";
        this.charts = [];
        this.stage = (this.props.action.params && this.props.action.params.stage)
            || (this.props.action.context && this.props.action.context.stage);
        this.state = useState({ loading: true, error: false, data: null, counts: {} });
        this.firstLoad = true;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        onMounted(() => {
            this.startCountUp();
            // Keep the screen live without anyone pressing Refresh
            this.timer = setInterval(() => this.load(true), REFRESH_MS);
        });
        onWillUnmount(() => {
            clearInterval(this.timer);
            cancelAnimationFrame(this.raf);
            clearTimeout(this.countTimer);
            this.destroyCharts();
        });
        useEffect(
            () => {
                if (!this.state.loading && this.state.data) {
                    this.renderCharts();
                }
            },
            () => [this.state.data]
        );
    }

    async load(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        try {
            const data = this.applyLayout(await this.orm.call("epc.stage.dashboard", "get_data", [this.stage]));
            if (this.firstLoad && !this.reducedMotion()) {
                // the tile numbers start at 0 and count up once the page is shown
                this.state.counts = Object.fromEntries(data.kpis.map((_k, i) => [i, 0]));
            }
            this.state.data = data;
            this.state.error = false;
        } catch (error) {
            if (!silent) {
                this.state.error = (error.data && error.data.message) || _t("The dashboard could not be loaded.");
            }
        }
        this.state.loading = false;
    }

    // Packs the cards into rows of 6 columns and removes any empty gap: a row
    // that would be left short gets its last card stretched, except the final
    // row, whose free space (3 or more columns) is given to the table so the
    // table sits right beside the last chart instead of far below it.
    applyLayout(data) {
        let used = 0;
        let last = null;
        for (const card of data.cards) {
            card._span = card.span;
            if (used + card._span > 6) {
                last._span += 6 - used;
                used = 0;
            }
            used += card._span;
            last = card;
            if (used === 6) {
                used = 0;
            }
        }
        data._tableSpan = 6;
        if (used) {
            const free = 6 - used;
            if (data.table && free >= 3) {
                data._tableSpan = free;
            } else if (last) {
                last._span += free;
            }
        }
        return data;
    }

    reducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    // Counts the tile numbers up from 0 to their value (about 0.8 s, eased out).
    // Only on the first load; later automatic refreshes just show the new numbers.
    startCountUp() {
        const data = this.state.data;
        if (!this.firstLoad || !data || !Object.keys(this.state.counts).length) {
            return;
        }
        this.firstLoad = false;
        const duration = 800;
        // wait for the tiles' fade-in so the numbers start moving as they appear
        this.countTimer = setTimeout(() => {
            const start = performance.now();
            const step = (now) => {
                const t = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - t, 3);
                data.kpis.forEach((kpi, i) => {
                    this.state.counts[i] = (kpi.value || 0) * eased;
                });
                if (t < 1) {
                    this.raf = requestAnimationFrame(step);
                } else {
                    this.state.counts = {};
                }
            };
            this.raf = requestAnimationFrame(step);
        }, 150);
    }

    // ---- formatting ------------------------------------------------------
    formatKpi(kpi, index) {
        const shown = this.state.counts[index];
        const value = shown === undefined ? kpi.value || 0 : shown;
        switch (kpi.fmt) {
            case "money":
                return formatMonetary(value, { currencyId: this.state.data.currency_id });
            case "pct":
                return formatFloat(value, { digits: [16, 1] }) + "%";
            case "dec":
                return formatFloat(value, { digits: [16, 1] });
            default:
                return formatInteger(Math.round(value));
        }
    }

    formatTime(text) {
        const date = new Date(text.replace(" ", "T") + "Z");
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    // ---- template helpers -----------------------------------------------
    hasData(card) {
        if (card.kind === "matrix") {
            return card.rows.length > 0;
        }
        return card.datasets.some((ds) => (ds.points ? ds.points.length : ds.data.some((v) => v)));
    }

    cellClass(cell) {
        return cell && cell.pill ? `o_epc_sd_pill o_epc_sd_pill_${cell.pill}` : "";
    }

    cellText(cell) {
        return cell && typeof cell === "object" ? cell.text : cell;
    }

    // ---- navigation: always the exact domain that produced the number ----
    openList(model, domain, name) {
        if (!model || !domain) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openRecord(model, resId) {
        if (!model || !resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---- charts ----------------------------------------------------------
    // The stage colour; brightened a little on the dark background
    accentColor() {
        const accent = this.state.data.accent || "#8b95f0";
        return this.dark ? lighten(accent, 0.18) : accent;
    }

    destroyCharts() {
        this.charts.forEach((chart) => chart.destroy());
        this.charts = [];
    }

    color(name, accent) {
        if (name === "accent") {
            return accent;
        }
        return (this.dark ? COLORS_DARK : COLORS)[name] || name;
    }

    renderCharts() {
        this.destroyCharts();
        const root = this.root.el;
        if (!root || !window.Chart) {
            return;
        }
        const style = getComputedStyle(root);
        const text = style.getPropertyValue("--epc-sd-muted").trim() || "#7b829f";
        const grid = style.getPropertyValue("--epc-sd-grid").trim() || "rgba(120, 130, 175, 0.16)";
        const surface = style.getPropertyValue("--epc-sd-edge").trim() || "#ffffff";
        const accent = this.accentColor();
        for (const card of this.state.data.cards) {
            const canvas = root.querySelector(`canvas[data-key="${card.key}"]`);
            if (!canvas || !this.hasData(card)) {
                continue;
            }
            this.charts.push(this.buildChart(canvas, card, { text, grid, surface, accent }));
        }
    }

    buildChart(canvas, card, theme) {
        const { text, grid, surface, accent } = theme;
        const text_ = text;
        const isPie = card.kind === "doughnut";
        const isScatter = card.kind === "scatter";
        const horizontal = card.kind === "hbar";
        const type = horizontal ? "bar" : card.kind;
        const multi = card.datasets.length > 1;
        const palette = (this.dark ? CATEGORICAL_DARK : CATEGORICAL).map((c) => this.color(c, accent));

        const datasets = card.datasets.map((ds, i) => {
            const own = Array.isArray(ds.color)
                ? ds.color.map((c) => this.color(c, accent))
                : this.color(ds.color || (multi ? palette[i % palette.length] : "accent"), accent);
            if (isPie) {
                return {
                    label: ds.label, data: ds.data, backgroundColor: Array.isArray(own) ? own : palette,
                    borderColor: surface, borderWidth: 2, hoverOffset: 8,
                };
            }
            if (isScatter) {
                return {
                    label: ds.label, data: ds.points.map((p) => ({ x: p.x, y: p.y })),
                    backgroundColor: own, pointRadius: 6, pointHoverRadius: 8,
                };
            }
            if (type === "line") {
                return {
                    label: ds.label, data: ds.data, borderColor: own, backgroundColor: own + "26",
                    fill: true, tension: 0.35, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2,
                };
            }
            return {
                label: ds.label, data: ds.data, backgroundColor: own,
                borderRadius: 5, borderSkipped: false, maxBarThickness: 40,
            };
        });

        const options = {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 600, easing: "easeOutQuart" },
            plugins: {
                legend: {
                    display: multi || isPie,
                    position: "bottom",
                    onClick: () => {},
                    labels: { color: text, usePointStyle: true, boxWidth: 8, boxHeight: 8 },
                },
            },
            onHover: (event, elements) => {
                const el = event.native && event.native.target;
                if (el) {
                    el.style.cursor = elements.length ? "pointer" : "default";
                }
            },
            onClick: (_event, elements) => {
                if (!elements.length) {
                    return;
                }
                const { datasetIndex, index } = elements[0];
                const ds = card.datasets[datasetIndex];
                if (isScatter) {
                    const point = ds.points[index];
                    this.openRecord(card.model, point && point.id);
                    return;
                }
                const domain = ds.domains && ds.domains[index];
                const label = card.labels[index];
                this.openList(card.model, domain, `${card.title} - ${label}`);
            },
        };

        if (isPie) {
            options.cutout = "60%";
        } else {
            const ticks = { color: text, precision: 0 };
            if (card.pct) {
                ticks.callback = (v) => v + "%";
            }
            const category = { ticks: { color: text }, grid: { display: false }, border: { color: grid } };
            const value = { ticks, grid: { color: grid }, border: { display: false }, beginAtZero: true };
            if (card.pct) {
                value.max = 100;
            }
            const title = (text) => ({
                display: !!text,
                text,
                color: text_,
                font: { weight: "600", size: 12 },
            });
            if (isScatter) {
                options.scales = {
                    x: { ...value, title: title(card.xlabel) },
                    y: { ...value, title: title(card.ylabel) },
                };
            } else if (horizontal) {
                options.indexAxis = "y";
                options.scales = {
                    y: { ...category, title: title(card.ylabel) },
                    x: { ...value, stacked: !!card.stack, title: title(card.xlabel) },
                };
            } else {
                options.scales = {
                    x: { ...category, stacked: !!card.stack, title: title(card.xlabel) },
                    y: { ...value, stacked: !!card.stack, title: title(card.ylabel) },
                };
            }
        }
        return new Chart(canvas, { type, data: { labels: card.labels, datasets }, options });
    }
}

registry.category("actions").add("epc_stage_dashboard", EpcStageDashboard);
