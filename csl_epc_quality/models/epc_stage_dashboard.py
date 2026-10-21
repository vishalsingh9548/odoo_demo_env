# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, models


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_quality(self):
        Check = self.env['epc.quality.check']
        today = self._today()
        month_start = today.replace(day=1)
        decided_domain = [('overall_result', 'in', ('pass', 'fail'))]
        first_try = decided_domain + [('previous_check_id', '=', False)]
        first_total = Check.search_count(first_try)
        first_passed_domain = [('overall_result', '=', 'pass'), ('previous_check_id', '=', False)]
        first_passed = Check.search_count(first_passed_domain)

        failed = Check.search([('overall_result', '=', 'fail')])
        reinspected = set(Check.search([('previous_check_id', 'in', failed.ids)]).mapped('previous_check_id').ids)
        open_failures = failed.filtered(lambda c: c.id not in reinspected)
        failed_month_domain = [('overall_result', '=', 'fail'), ('check_date', '>=', month_start.isoformat())]
        failed_month = Check.search_count(failed_month_domain)

        fixes = Check.search([('overall_result', '=', 'pass'), ('previous_check_id', '!=', False)])
        spans = [(c.check_date - c.previous_check_id.check_date).days for c in fixes
                 if c.check_date and c.previous_check_id.check_date]
        fix_days = sum(spans) / len(spans) if spans else 0.0

        Dpr = self.env['epc.dpr']
        issue_domain = [('issues_risks', '!=', False), ('report_date', '>=', (today - timedelta(days=30)).isoformat())]
        issue_count = Dpr.search_count(issue_domain)

        kpis = [
            self._kpi('First-pass yield', self._pct(first_passed, first_total), 'pct',
                      sub='%s of %s first inspections passed' % (first_passed, first_total),
                      tone='good' if first_total and first_passed == first_total else '', icon='fa-check-circle-o',
                      model='epc.quality.check', domain=first_try),
            self._kpi('Failed this month', failed_month, tone='bad' if failed_month else 'good', icon='fa-times-circle-o',
                      sub='checks marked Fail since %s' % month_start.strftime('%d %b'),
                      model='epc.quality.check', domain=failed_month_domain),
            self._kpi('Failures not re-inspected', len(open_failures), tone='bad' if open_failures else 'good',
                      icon='fa-repeat', sub='all time', model='epc.quality.check',
                      domain=[('id', 'in', open_failures.ids)]),
            self._kpi('Days from fail to pass', fix_days, 'dec', 'd', sub='average over re-inspections',
                      icon='fa-clock-o', model='epc.quality.check',
                      domain=[('overall_result', '=', 'pass'), ('previous_check_id', '!=', False)]),
            self._kpi('Site issues reported', issue_count, tone='warn' if issue_count else '', icon='fa-flag',
                      sub='in daily reports, last 30 days', model='epc.dpr', domain=issue_domain),
        ]

        # weekly pass / fail for the last 8 weeks (Monday to Sunday)
        week_start = today - timedelta(days=today.weekday())
        labels, passes, fails, pass_dom, fail_dom = [], [], [], [], []
        for back in range(7, -1, -1):
            start = week_start - timedelta(weeks=back)
            rng = self._range('check_date', start, start + timedelta(weeks=1))
            end = start + timedelta(days=6)
            labels.append('%s – %s' % (start.strftime('%d %b'), end.strftime('%d %b')))
            pdom, fdom = rng + [('overall_result', '=', 'pass')], rng + [('overall_result', '=', 'fail')]
            pass_dom.append(pdom)
            fail_dom.append(fdom)
            passes.append(Check.search_count(pdom))
            fails.append(Check.search_count(fdom))

        stage_names = dict(Check._fields['category'].selection)
        stage_labels, stage_rates, stage_domains = [], [], []
        for key, name in stage_names.items():
            total = Check.search_count(decided_domain + [('category', '=', key)])
            if total:
                stage_labels.append(name)
                stage_rates.append(self._pct(Check.search_count([('category', '=', key), ('overall_result', '=', 'pass')]), total))
                stage_domains.append([('category', '=', key), ('overall_result', 'in', ('pass', 'fail'))])

        fail_lines = self.env['epc.quality.check.line']._read_group([('result', '=', 'fail')], ['name'], ['__count'])
        fail_lines = sorted(fail_lines, key=lambda r: -r[1])[:6]

        # total workers on site per day (all projects together): several reports
        # on the same day add up instead of showing as separate dots
        day_rows = Dpr._read_group([('report_date', '!=', False)], ['report_date:day'], ['manpower_deployed:sum'],
                                   order='report_date:day desc', limit=14)
        day_rows = sorted(day_rows, key=lambda r: r[0])
        weather_l, weather_c, weather_d = self._group_selection('epc.dpr', 'weather', empty_label='Not recorded')

        cards = [
            self._card('weekly', 'Passed and failed, weekly', 'Last eight weeks', 'bar', labels, [
                {'label': 'Passed', 'color': 'pass', 'data': passes, 'domains': pass_dom},
                {'label': 'Failed', 'color': 'fail', 'data': fails, 'domains': fail_dom}],
                model='epc.quality.check', span=4, stack=True, source='epc.quality.check · check_date, overall_result'),
            self._card('stage', 'Pass rate by stage', 'Share of decided checks that passed', 'bar', stage_labels,
                       [{'label': 'Pass %', 'data': stage_rates, 'domains': stage_domains,
                         'color': ['pass' if r >= 80 else 'warn' for r in stage_rates]}],
                       model='epc.quality.check', span=2, pct=True, source='epc.quality.check · category'),
            self._card('checkpoints', 'Most failed checkpoints', 'Where inspections fail most often', 'hbar',
                       [r[0] for r in fail_lines],
                       [{'label': 'Failures', 'color': 'fail', 'data': [r[1] for r in fail_lines],
                         'domains': [[('result', '=', 'fail'), ('name', '=', r[0])] for r in fail_lines]}],
                       model='epc.quality.check.line', span=3, source='epc.quality.check.line · result = fail'),
            self._card('manpower', 'Workers on site per day', 'Total across all projects, last 14 days with reports', 'line',
                       [r[0].strftime('%d %b') for r in day_rows],
                       [{'label': 'Workers', 'data': [r[1] for r in day_rows],
                         'domains': [[('report_date', '=', r[0].isoformat())] for r in day_rows]}],
                       model='epc.dpr', span=3, source='epc.dpr · manpower_deployed summed by report_date'),
            self._card('weather', 'Weather on site', 'Daily reports by conditions', 'doughnut', weather_l,
                       [{'label': 'Reports', 'data': weather_c, 'domains': weather_d}],
                       model='epc.dpr', span=2, source='epc.dpr · weather'),
        ]

        rows = []
        for check in failed.sorted('check_date', reverse=True)[:8]:
            done = check.id in reinspected
            rows.append({'id': check.id, 'cells': [
                check.name, check.project_id.display_name or '', dict(Check._fields['category'].selection).get(check.category, ''),
                check.inspector_id.name or '', (check.fail_reason or '').strip()[:60] or '-',
                {'text': 'Re-inspected' if done else 'Open', 'pill': 'good' if done else 'bad'}]})
        table = self._tbl(
            'Recent failures and the reason given', 'epc.quality.check',
            [('Check', 'start'), ('Project', 'start'), ('Stage', 'start'), ('Inspector', 'start'),
             ('Reason', 'start'), ('Status', 'start')],
            rows, source='epc.quality.check · overall_result = fail, fail_reason', empty='No quality check has failed.')

        self._axis_titles(cards, {'weekly': ('Week (Monday to Sunday)', 'Checks'), 'stage': ('Stage', 'Pass rate (%)'), 'checkpoints': ('Number of failures', 'Checkpoint'), 'manpower': ('Date', 'Workers on site')})

        return {'title': 'Quality', 'accent': '#a3b5f7',
                'intro': 'First-pass quality, where failures come from, and what daily site reports say.',
                'kpis': kpis, 'cards': cards, 'table': table}
