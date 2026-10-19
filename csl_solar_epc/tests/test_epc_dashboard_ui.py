# -*- coding: utf-8 -*-
"""Opens every stage dashboard in a real (headless) browser: tiles and charts
render without JavaScript errors, a click opens the matching list, and the
layout fits every screen width from a phone to a projector."""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

ACTIONS = [
    'csl_epc_site_survey.epc_dashboard_survey_action',
    'csl_epc_feasibility.epc_dashboard_feasibility_action',
    'csl_epc_boq.epc_dashboard_boq_action',
    'csl_epc_material_request.epc_dashboard_material_action',
    'csl_epc_quality.epc_dashboard_quality_action',
    'csl_epc_commissioning.epc_dashboard_commissioning_action',
    'csl_epc_handover.epc_dashboard_handover_action',
    'csl_epc_amc.epc_dashboard_amc_action',
]

WAIT = """
const wait = async (fn, ms = 20000) => {
    const start = Date.now();
    while (Date.now() - start < ms) {
        const value = fn();
        if (value) { return value; }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error('Timed out waiting for the dashboard');
};
"""

RENDER = WAIT + """
(async () => {
    await wait(() => document.querySelectorAll('.o_epc_sd .o_epc_sd_kpi').length === 5);
    await wait(() => {
        const canvases = [...document.querySelectorAll('.o_epc_sd canvas')];
        return canvases.length && canvases.every((c) => window.Chart.getChart(c));
    });
    console.log('test successful');
})();
"""

SIZES = WAIT + """
(async () => {
    await wait(() => document.querySelectorAll('.o_epc_sd .o_epc_sd_kpi').length === 5);
    await wait(() => [...document.querySelectorAll('.o_epc_sd canvas')].every((c) => window.Chart.getChart(c)));
    const root = document.querySelector('.o_epc_sd');
    for (const width of [360, 768, 1280, 1920, 3840]) {
        root.style.width = width + 'px';
        await new Promise((resolve) => setTimeout(resolve, 250));
        const box = root.getBoundingClientRect();
        if (root.scrollWidth > root.clientWidth + 1) {
            throw new Error('Horizontal overflow at ' + width + 'px');
        }
        for (const card of root.querySelectorAll('.o_epc_sd_card, .o_epc_sd_kpi')) {
            if (card.getBoundingClientRect().right > box.right + 1) {
                throw new Error('A card sticks out at ' + width + 'px');
            }
        }
        const columns = getComputedStyle(root.querySelector('.o_epc_sd_grid')).gridTemplateColumns.split(' ').length;
        if (width <= 640 && columns !== 1) {
            throw new Error('Phone width should use one column, got ' + columns);
        }
    }
    console.log('test successful');
})();
"""

CLICK = WAIT + """
(async () => {
    await wait(() => document.querySelectorAll('.o_epc_sd .o_epc_sd_kpi').length === 5);
    document.querySelector('.o_epc_sd .o_epc_sd_click').click();
    await wait(() => document.querySelector('.o_list_view, .o_form_view, .o_kanban_view'));
    console.log('test successful');
})();
"""


MAIN = WAIT + """
(async () => {
    await wait(() => document.querySelectorAll('.o_epc_dashboard .o_epc_tile').length === 7);
    await wait(() => {
        const canvases = [...document.querySelectorAll('.o_epc_dashboard canvas')];
        return canvases.length && canvases.every((c) => window.Chart.getChart(c));
    });
    console.log('test successful');
})();
"""

MAIN_DARK = "document.cookie = 'color_scheme=dark; path=/';" + MAIN


@tagged('post_install', '-at_install')
class TestEpcDashboardUi(HttpCase):

    def _url(self, xmlid):
        return '/odoo/action-%s' % xmlid

    def test_each_dashboard_renders(self):
        for xmlid in ACTIONS:
            with self.subTest(action=xmlid):
                self.browser_js(self._url(xmlid), RENDER, login='admin')

    def test_dashboard_fits_every_screen_width(self):
        for xmlid in ACTIONS:
            with self.subTest(action=xmlid):
                self.browser_js(self._url(xmlid), SIZES, login='admin')

    def test_clicking_a_tile_opens_records(self):
        self.browser_js(self._url(ACTIONS[0]), CLICK, login='admin')

    def test_main_dashboard_renders_in_light_and_dark(self):
        self.browser_js('/odoo/action-csl_solar_epc.epc_dashboard_action', MAIN, login='admin')
        self.browser_js('/odoo/action-csl_solar_epc.epc_dashboard_action', MAIN_DARK, login='admin')
