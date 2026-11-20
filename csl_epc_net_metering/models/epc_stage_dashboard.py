# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

ACTIVE = ('applied', 'discom_approved', 'inspection_done', 'meter_installed')
STUCK_SUMMARY = "Net-metering application is stuck"


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_net_metering(self):
        NM = self.env['epc.net.meter']
        apps = NM.search([])
        today = self._today()
        limit_days = int(self.env['ir.config_parameter'].sudo().get_param('csl_epc.netmeter_stuck_days') or 15)
        open_apps = apps.filtered(lambda a: a.state not in ('synced', 'rejected'))
        open_dom = [('state', 'not in', ['synced', 'rejected'])]
        stuck_dom = [('state', 'in', list(ACTIVE)),
                     ('last_state_date', '<=', fields.Date.to_string(today - timedelta(days=limit_days)))]
        stuck = NM.search(stuck_dom)
        reminded = stuck.filtered(lambda a: any(act.summary == STUCK_SUMMARY for act in a.activity_ids))
        synced = apps.filtered(lambda a: a.state == 'synced' and a.applied_date and a.sync_date)
        avg_days = round(sum((a.sync_date - a.applied_date).days for a in synced) / len(synced), 1) if synced else 0.0
        fitted = apps.filtered(lambda a: a.state == 'meter_installed')
        month_start = today.replace(day=1)
        prev_start = (month_start - timedelta(days=1)).replace(day=1)
        this_dom = [('sync_date', '>=', fields.Date.to_string(month_start))]
        synced_now = NM.search_count(this_dom)
        synced_before = NM.search_count(self._range('sync_date', prev_start, month_start))
        delta_text, delta_trend = self._delta_text(synced_now, synced_before, 'last month')
        rejected = apps.filtered(lambda a: a.state == 'rejected')

        kpis = [
            self._kpi('Open applications', len(open_apps), sub='not synced, not rejected', icon='fa-plug',
                      model='epc.net.meter', domain=open_dom),
            self._kpi('Stuck over %s days' % limit_days, len(stuck), tone='bad' if stuck else 'good',
                      sub=('%s with a reminder to-do' % len(reminded)) if stuck else 'nothing stuck',
                      trend='down' if stuck else '', icon='fa-exclamation-triangle', model='epc.net.meter', domain=stuck_dom),
            self._kpi('Average time to sync', avg_days, 'dec', 'days', sub='applied to synced', icon='fa-clock-o',
                      model='epc.net.meter', domain=[('state', '=', 'synced')]),
            self._kpi('Meter fitted, not synced', len(fitted), tone='warn' if fitted else 'good',
                      sub='waiting for the grid switch-on', icon='fa-hourglass-half',
                      model='epc.net.meter', domain=[('state', '=', 'meter_installed')]),
            self._kpi('Synced this month', synced_now, tone='good', sub=delta_text, trend=delta_trend, icon='fa-check-circle-o',
                      model='epc.net.meter', domain=this_dom),
            self._kpi('Rejected', len(rejected), sub='need a new application', icon='fa-flag',
                      model='epc.net.meter', domain=[('state', '=', 'rejected')]),
        ]

        state_l, state_c, state_d = self._group_selection('epc.net.meter', 'state')
        state_names = dict(NM._fields['state'].selection)
        stage_l, stage_c, stage_d = [], [], []
        for key in ACTIVE:
            group = open_apps.filtered(lambda a, k=key: a.state == k)
            if group:
                stage_l.append(state_names[key])
                stage_c.append(round(sum(group.mapped('stuck_days')) / len(group), 1))
                stage_d.append([('state', '=', key)])
        discom_l, discom_c, discom_d = [], [], []
        discoms = open_apps.mapped('project_id.discom_id')
        for discom in discoms:
            dom = open_dom + [('project_id.discom_id', '=', discom.id)]
            discom_l.append(discom.name)
            discom_c.append(NM.search_count(dom))
            discom_d.append(dom)
        order = sorted(range(len(discom_c)), key=lambda i: -discom_c[i])[:5]
        discom_l, discom_c, discom_d = [discom_l[i] for i in order], [discom_c[i] for i in order], [discom_d[i] for i in order]
        month = self._count_by_month('epc.net.meter', 'sync_date')
        speed, speed_dom = [], []
        for _l, start, end in self._months(6):
            dom = self._range('sync_date', start, end) + [('applied_date', '!=', False)]
            got = NM.search(dom)
            speed.append(round(sum((a.sync_date - a.applied_date).days for a in got) / len(got), 1) if got else 0)
            speed_dom.append(dom)

        cards = [
            self._card('pipeline', 'Application pipeline', 'Count by status', 'hbar', state_l,
                       [{'label': 'Applications', 'data': state_c, 'domains': state_d}],
                       model='epc.net.meter', span=3, source='epc.net.meter · state'),
            self._card('stage_days', 'Days spent in the current status', 'Average, open applications only', 'hbar', stage_l,
                       [{'label': 'Days', 'color': 'warn', 'data': stage_c, 'domains': stage_d}],
                       model='epc.net.meter', span=3, source='epc.net.meter · last_state_date'),
            self._card('discom', 'Open applications by DISCOM', 'Top five boards holding them', 'hbar', discom_l,
                       [{'label': 'Applications', 'data': discom_c, 'domains': discom_d}],
                       model='epc.net.meter', span=2, source='epc.net.meter · project DISCOM'),
            self._card('monthly', 'Synced per month', 'By sync date', 'bar', month[0],
                       [{'label': 'Synced', 'data': month[1], 'domains': month[2]}],
                       model='epc.net.meter', span=2, source='epc.net.meter · sync_date'),
            self._card('speed', 'Days from application to sync', 'Average, by month of sync', 'line', [m[0] for m in self._months(6)],
                       [{'label': 'Days', 'data': speed, 'domains': speed_dom}],
                       model='epc.net.meter', span=2, source='epc.net.meter · applied_date, sync_date'),
        ]
        self._axis_titles(cards, {'pipeline': ('Number of applications', 'Status'), 'stage_days': ('Days', 'Status'),
                                  'discom': ('Number of applications', 'DISCOM'), 'monthly': ('Month', 'Synced'),
                                  'speed': ('Month synced', 'Days')})

        rows = []
        for app in stuck.sorted(lambda a: a.last_state_date or today)[:8]:
            rows.append({'id': app.id, 'cells': [
                app.name, app.partner_id.display_name or '', app.discom_id.name or '',
                {'text': state_names.get(app.state, ''), 'pill': 'warn'},
                {'text': str(app.stuck_days), 'pill': 'bad'},
                {'text': 'To-do sent' if app in reminded else 'Not yet', 'pill': 'good' if app in reminded else 'neutral'}]})
        table = self._tbl(
            'Not moving', 'epc.net.meter',
            [('Reference', 'start'), ('Customer', 'start'), ('DISCOM', 'start'), ('Status', 'start'), ('Days in status', 'end'), ('Reminder', 'start')],
            rows, source='epc.net.meter · last_state_date', empty='No application is stuck.')

        return {'title': 'Net Metering', 'accent': '#82cdf5',
                'intro': 'Where each connection stands with the electricity board, and which ones have stopped moving.',
                'kpis': kpis, 'cards': cards, 'table': table}
