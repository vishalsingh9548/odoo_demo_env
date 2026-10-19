# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, models


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_survey(self):
        Survey = self.env['epc.site.survey']
        month_start = self._today().replace(day=1)
        next_month = month_start + relativedelta(months=1)
        this_domain = self._range('survey_date', month_start, next_month)
        this_count = Survey.search_count(this_domain)
        last_count = Survey.search_count(self._range('survey_date', month_start - relativedelta(months=1), month_start))
        delta_text, delta_trend = self._delta_text(this_count, last_count, 'last month')

        feasible_domain = [('is_feasible', '=', 'yes')]
        decided = Survey.search_count([('is_feasible', 'in', ('yes', 'no'))])
        feasible = Survey.search_count(feasible_domain)

        # Surveys with no area filled in are left out of the average (and of the
        # list the tile opens), so the figure matches the footer of that list
        area_domain = [('available_area_sqft', '>', 0)]
        area_avg = Survey._read_group(area_domain, aggregates=['available_area_sqft:avg'])[0][0]
        load_sum = Survey._read_group([], aggregates=['sanctioned_load_kw:sum'])[0][0]
        area_count = Survey.search_count(area_domain)
        waiting_domain = [('approval_state', '=', 'submitted')]
        waiting = Survey.search(waiting_domain, order='submitted_date asc')
        oldest = self._days_since(waiting[:1].submitted_date) if waiting else None
        stale = len([s for s in waiting if (self._days_since(s.submitted_date) or 0) > 5])

        kpis = [
            self._kpi('Surveys this month', this_count, sub=delta_text, trend=delta_trend, icon='fa-map-marker',
                      model='epc.site.survey', domain=this_domain),
            self._kpi('Feasible rate', self._pct(feasible, decided), 'pct',
                      sub='%s of %s decided surveys' % (feasible, decided), tone='good', icon='fa-check-circle-o',
                      model='epc.site.survey', domain=feasible_domain),
            self._kpi('Avg usable area', area_avg or 0, 'int', 'sq ft', sub='over %s surveys with an area' % area_count,
                      icon='fa-arrows-alt', model='epc.site.survey', domain=area_domain),
            self._kpi('Sanctioned load surveyed', load_sum or 0, 'int', 'kW', sub='across all surveys', icon='fa-bolt',
                      model='epc.site.survey', domain=[]),
            self._kpi('Waiting for a decision', len(waiting), tone='warn' if waiting else '', icon='fa-hourglass-half',
                      sub=('%s waiting over 5 days' % stale) if stale else (
                          'oldest %s days' % oldest if oldest is not None else 'nothing pending'),
                      trend='down' if stale else '', model='epc.site.survey', domain=waiting_domain),
        ]

        monthly = self._count_by_month('epc.site.survey', 'survey_date')
        out_labels, out_counts, out_domains = self._group_selection('epc.site.survey', 'is_feasible', empty_label='Undecided')
        out_colors = [{'Yes': 'pass', 'No': 'fail'}.get(label, 'neutral') for label in out_labels]
        type_labels, type_counts, type_domains = self._group_selection('epc.site.survey', 'roof_or_land_type', empty_label='Not set')
        grid_yes = [('grid_access_available', '=', True)]
        grid_no = [('grid_access_available', '=', False)]
        tr_yes = [('has_existing_transformer', '=', True)]
        tr_no = [('has_existing_transformer', '=', False)]
        eng_labels, eng_counts, eng_domains = self._group_selection('epc.site.survey', 'engineer_id', empty_label='Unassigned', order='desc')

        cards = [
            self._card('monthly', 'Surveys completed per month', 'Intake volume over the last six months', 'bar',
                       monthly[0], [{'label': 'Surveys', 'data': monthly[1], 'domains': monthly[2]}],
                       model='epc.site.survey', span=3, source='epc.site.survey · survey_date'),
            self._card('outcome', 'Outcome of surveys', 'Verdict recorded by the engineer', 'doughnut',
                       out_labels, [{'label': 'Surveys', 'data': out_counts, 'domains': out_domains, 'color': out_colors}],
                       model='epc.site.survey', span=3, source='is_feasible'),
            self._card('type', 'Site type mix', 'What customers ask us to build on', 'hbar',
                       type_labels, [{'label': 'Sites', 'data': type_counts, 'domains': type_domains}],
                       model='epc.site.survey', span=2, source='roof_or_land_type'),
            self._card('grid', 'Grid readiness', 'Sites with grid access and a transformer', 'bar',
                       ['Grid access', 'Own transformer'],
                       [{'label': 'Yes', 'color': 'pass',
                         'data': [Survey.search_count(grid_yes), Survey.search_count(tr_yes)],
                         'domains': [grid_yes, tr_yes]},
                        {'label': 'No', 'color': 'fail',
                         'data': [Survey.search_count(grid_no), Survey.search_count(tr_no)],
                         'domains': [grid_no, tr_no]}],
                       model='epc.site.survey', span=2, source='grid_access_available · has_existing_transformer'),
            self._card('engineer', 'Surveys per engineer', 'Workload spread', 'hbar',
                       eng_labels[:8], [{'label': 'Surveys', 'data': eng_counts[:8], 'domains': eng_domains[:8]}],
                       model='epc.site.survey', span=2, source='engineer_id'),
        ]

        rows = []
        for survey in waiting[:8]:
            days = self._days_since(survey.submitted_date) or 0
            rows.append({'id': survey.id, 'cells': [
                survey.name, survey.partner_id.display_name or '', survey.engineer_id.name or '',
                '{:,.0f}'.format(survey.available_area_sqft or 0), '%s d' % days,
                {'text': 'Overdue' if days > 5 else 'Submitted', 'pill': 'bad' if days > 5 else 'warn'}]})
        table = self._tbl(
            'Surveys waiting for a decision', 'epc.site.survey',
            [('Survey', 'start'), ('Customer', 'start'), ('Engineer', 'start'), ('Area (sq ft)', 'end'),
             ('Waiting', 'end'), ('Status', 'start')],
            rows, source='epc.site.survey · approval_state = submitted', empty='No survey is waiting for approval.')

        return {'title': 'Site Survey', 'accent': '#8dbdf2',
                'intro': 'How fast surveys are done, how many are viable, and what kind of sites come in.',
                'kpis': kpis, 'cards': cards, 'table': table}
