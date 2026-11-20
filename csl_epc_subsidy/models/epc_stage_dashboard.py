# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

OPEN_STATES = ('applied', 'approved')
STUCK_DAYS = 30


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_subsidy(self):
        App = self.env['epc.subsidy.application']
        apps = App.search([])
        today = self._today()
        year_start = today.replace(month=1, day=1)
        last_year_start = year_start.replace(year=year_start.year - 1)

        waiting = apps.filtered(lambda a: a.state in OPEN_STATES)
        waiting_dom = [('state', 'in', list(OPEN_STATES))]
        got_now = apps.filtered(lambda a: a.disbursed_date and a.disbursed_date >= year_start)
        got_before = apps.filtered(lambda a: a.disbursed_date and last_year_start <= a.disbursed_date < year_start)
        now_sum, before_sum = sum(got_now.mapped('disbursed_amount')), sum(got_before.mapped('disbursed_amount'))
        if before_sum:
            change = round((now_sum - before_sum) * 100.0 / before_sum)
            year_sub, year_trend = '%s%s%% on last year' % ('up ' if change >= 0 else 'down ', abs(change)), 'up' if change >= 0 else 'down'
        else:
            year_sub, year_trend = 'since 1 January', ''
        paid = apps.filtered(lambda a: a.state == 'disbursed' and a.applied_date and a.disbursed_date)
        avg_days = round(sum((a.disbursed_date - a.applied_date).days for a in paid) / len(paid), 1) if paid else 0.0
        stuck = waiting.filtered(lambda a: a.days_pending > STUCK_DAYS)
        oldest = max(waiting.mapped('days_pending'), default=0)
        rejected = apps.filtered(lambda a: a.state == 'rejected')
        closed = len(rejected) + len(apps.filtered(lambda a: a.state == 'disbursed'))

        # subsidy expected on quotations that are still open (needs access to sales orders)
        expected, quote_ids = 0.0, []
        try:
            quotes = self.env['sale.order'].search([('state', 'in', ('draft', 'sent')), ('is_epc_order', '=', True)])
            quotes = quotes.filtered('epc_expected_subsidy')
            expected, quote_ids = sum(quotes.mapped('epc_expected_subsidy')), quotes.ids
        except AccessError:
            pass

        kpis = [
            self._kpi('Money waiting', sum(waiting.mapped('claimed_amount')), 'money',
                      sub='claimed, across %s application(s)' % len(waiting), tone='warn' if waiting else 'good',
                      icon='fa-money', model='epc.subsidy.application', domain=waiting_dom),
            self._kpi('Received this year', now_sum, 'money', sub=year_sub, trend=year_trend, tone='good',
                      icon='fa-line-chart', model='epc.subsidy.application', domain=[('disbursed_date', '>=', fields.Date.to_string(year_start))]),
            self._kpi('Average time to money', avg_days, 'dec', 'days', sub='applied to disbursed', icon='fa-clock-o',
                      model='epc.subsidy.application', domain=[('state', '=', 'disbursed')]),
            self._kpi('Stuck over %s days' % STUCK_DAYS, len(stuck), tone='bad' if stuck else 'good',
                      sub=('oldest waiting %s days' % oldest) if stuck else 'nothing stuck', trend='down' if stuck else '',
                      icon='fa-exclamation-triangle', model='epc.subsidy.application', domain=[('id', 'in', stuck.ids)]),
            self._kpi('Rejection rate', self._pct(len(rejected), closed), 'pct',
                      sub='%s of %s closed application(s)' % (len(rejected), closed), icon='fa-percent',
                      model='epc.subsidy.application', domain=[('state', '=', 'rejected')]),
            self._kpi('Expected on open quotes', expected, 'money', sub='not an application yet', icon='fa-sun-o',
                      model='sale.order', domain=[('id', 'in', quote_ids)]),
        ]

        state_l, state_c, state_d = self._group_selection('epc.subsidy.application', 'state')
        months = self._months(6)
        series = []
        for label, field, date_field in (('Claimed', 'claimed_amount', 'applied_date'),
                                         ('Approved', 'approved_amount', 'approved_date'),
                                         ('Disbursed', 'disbursed_amount', 'disbursed_date')):
            data, domains = [], []
            for _l, start, end in months:
                dom = self._range(date_field, start, end)
                data.append(round(sum(App.search(dom).mapped(field)), 2))
                domains.append(dom)
            series.append({'label': label, 'data': data, 'domains': domains})
        scheme_l, scheme_c, scheme_d = [], [], []
        for scheme in apps.mapped('scheme_id'):
            dom = [('scheme_id', '=', scheme.id)]
            scheme_l.append(scheme.name)
            scheme_c.append(round(sum(App.search(dom).mapped('claimed_amount')), 2))
            scheme_d.append(dom)
        bands = [('0 to 15 days', 0, 15), ('16 to 30 days', 16, 30), ('31 to 60 days', 31, 60), ('over 60 days', 61, None)]
        age_dom = []
        for _l, low, high in bands:
            dom = list(waiting_dom) + [('applied_date', '<=', fields.Date.to_string(today - timedelta(days=low)))]
            if high is not None:
                dom.append(('applied_date', '>=', fields.Date.to_string(today - timedelta(days=high))))
            age_dom.append(dom)
        speed, speed_dom = [], []
        for _l, start, end in months:
            dom = self._range('disbursed_date', start, end) + [('applied_date', '!=', False)]
            got = App.search(dom)
            speed.append(round(sum((a.disbursed_date - a.applied_date).days for a in got) / len(got), 1) if got else 0)
            speed_dom.append(dom)

        cards = [
            self._card('funnel', 'Application funnel', 'Count of applications by status', 'hbar', state_l,
                       [{'label': 'Applications', 'data': state_c, 'domains': state_d}],
                       model='epc.subsidy.application', span=3, source='epc.subsidy.application · state'),
            self._card('money', 'Claimed, approved and received', 'Amount by month of each step', 'bar',
                       [m[0] for m in months], series,
                       model='epc.subsidy.application', span=3, source='epc.subsidy.application · claimed, approved, disbursed amounts'),
            self._card('scheme', 'Subsidy by scheme', 'Share of claimed amount', 'doughnut', scheme_l,
                       [{'label': 'Claimed', 'data': scheme_c, 'domains': scheme_d}],
                       model='epc.subsidy.application', span=2, source='epc.subsidy.application · scheme_id'),
            self._card('ageing', 'How long open ones have waited', 'Applied or approved, not yet paid', 'bar',
                       [b[0] for b in bands], [{'label': 'Applications', 'color': 'warn',
                                                'data': [App.search_count(d) for d in age_dom], 'domains': age_dom}],
                       model='epc.subsidy.application', span=2, source='epc.subsidy.application · applied_date'),
            self._card('speed', 'Days to money, by month', 'Average, applied to disbursed', 'line',
                       [m[0] for m in months], [{'label': 'Days', 'data': speed, 'domains': speed_dom}],
                       model='epc.subsidy.application', span=2, source='epc.subsidy.application · applied_date, disbursed_date'),
        ]
        self._axis_titles(cards, {'funnel': ('Number of applications', 'Status'), 'money': ('Month', 'Amount'),
                                  'ageing': ('Time waiting', 'Applications'), 'speed': ('Month paid', 'Days')})

        state_names = dict(App._fields['state'].selection)
        rows = []
        for app in waiting.sorted(lambda a: a.applied_date or today)[:8]:
            rows.append({'id': app.id, 'cells': [
                app.name, app.partner_id.display_name or '', app.scheme_id.name or '',
                self._money_text(app.claimed_amount),
                {'text': state_names.get(app.state, ''), 'pill': 'good' if app.state == 'approved' else 'warn'},
                {'text': str(app.days_pending), 'pill': 'bad' if app.days_pending > STUCK_DAYS else 'neutral'}]})
        table = self._tbl(
            'Waiting longest', 'epc.subsidy.application',
            [('Reference', 'start'), ('Customer', 'start'), ('Scheme', 'start'), ('Claimed', 'end'), ('Status', 'start'), ('Days waiting', 'end')],
            rows, source='epc.subsidy.application · applied_date', empty='No application is waiting for money.')

        return {'title': 'Subsidy', 'accent': '#7fb6ee',
                'intro': 'How much subsidy money is still to come, how long it takes, and which applications are stuck.',
                'kpis': kpis, 'cards': cards, 'table': table}
