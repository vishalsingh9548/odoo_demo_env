# -*- coding: utf-8 -*-
"""Tests for the per-stage dashboards: every stage returns a complete,
JSON-safe payload, and the numbers on screen match the lists they open."""
import json

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

STAGES = ['survey', 'feasibility', 'boq', 'material', 'quality', 'commissioning', 'handover', 'amc']

# Charts that count records: each bar must equal the size of the list it opens
COUNT_CARDS = {
    'survey': {'monthly', 'outcome', 'type', 'grid', 'engineer'},
    'feasibility': {'system', 'size', 'orientation', 'pr'},
    'boq': {'revisions'},
    'material': {'issue', 'monthly'},
    'quality': {'weekly', 'checkpoints', 'weather'},
    'commissioning': {'gates', 'owners', 'ageing', 'monthly'},
    'handover': {'missing', 'monthly', 'training', 'status'},
    'amc': {'renewals', 'tickets', 'busiest'},
}


@tagged('post_install', '-at_install')
class TestEpcDashboards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.manager = Users.create({
            'name': 'Dash Manager', 'login': 'test_dash_manager', 'email': 'dm@example.com',
            'groups_id': [(6, 0, [cls.env.ref('csl_epc_core.group_epc_manager').id])],
        })
        cls.field_user = Users.create({
            'name': 'Dash Field', 'login': 'test_dash_field', 'email': 'df@example.com',
            'groups_id': [(6, 0, [cls.env.ref('csl_epc_core.group_epc_user').id])],
        })
        cls.outsider = Users.create({
            'name': 'Dash Outsider', 'login': 'test_dash_out', 'email': 'do@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _data(self, user, stage):
        return self.env['epc.stage.dashboard'].with_user(user).get_data(stage)

    def test_every_stage_returns_a_complete_payload(self):
        for stage in STAGES:
            for user in (self.manager, self.field_user):
                data = self._data(user, stage)
                json.dumps(data)
                self.assertTrue(data['title'] and data['accent'] and data['kpis'], stage)
                self.assertEqual(len(data['kpis']), 5, stage)
                self.assertTrue(data['cards'], stage)
                for card in data['cards']:
                    self.assertIn(card['kind'], ('bar', 'hbar', 'line', 'doughnut', 'scatter', 'matrix'))
                    for ds in card['datasets']:
                        if ds.get('domains') is not None:
                            self.assertEqual(len(ds['domains']), len(ds['data']), '%s/%s' % (stage, card['key']))

    def test_tiles_match_the_list_they_open(self):
        for stage in STAGES:
            data = self._data(self.manager, stage)
            for kpi in data['kpis']:
                if kpi['model'] and kpi['fmt'] == 'int' and not kpi['unit']:
                    count = self.env[kpi['model']].search_count(kpi['domain'])
                    self.assertEqual(count, kpi['value'], '%s: %s' % (stage, kpi['label']))

    def test_count_charts_match_the_list_they_open(self):
        for stage, keys in COUNT_CARDS.items():
            data = self._data(self.manager, stage)
            for card in data['cards']:
                if card['key'] not in keys:
                    continue
                for ds in card['datasets']:
                    for value, domain in zip(ds['data'], ds['domains']):
                        self.assertEqual(self.env[card['model']].search_count(domain), value,
                                         '%s/%s' % (stage, card['key']))

    def test_dashboard_follows_live_data(self):
        before = self._data(self.manager, 'survey')['kpis'][0]['value']
        partner = self.env['res.partner'].create({'name': 'Dash Customer'})
        lead = self.env['crm.lead'].create({'name': 'Dash Lead', 'partner_id': partner.id, 'type': 'opportunity'})
        self.env['epc.site.survey'].create({'lead_id': lead.id, 'survey_date': self.env['epc.stage.dashboard']._today()})
        after = self._data(self.manager, 'survey')['kpis'][0]['value']
        self.assertEqual(after, before + 1)

    def test_users_without_epc_access_are_refused(self):
        with self.assertRaises(AccessError):
            self._data(self.outsider, 'survey')

    def test_unknown_stage_is_refused(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self._data(self.manager, 'nope')
