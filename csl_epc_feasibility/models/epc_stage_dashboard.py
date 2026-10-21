# -*- coding: utf-8 -*-
from odoo import api, models

PR_TARGET = 80.0  # performance ratio (%) the average is compared with


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_feasibility(self):
        Feas = self.env['epc.feasibility']
        studies = Feas.search([])
        capacity = sum(studies.mapped('proposed_capacity_kw'))
        generation = sum(studies.mapped('annual_generation_estimate_kwh'))
        ratios = [s.performance_ratio for s in studies if s.performance_ratio]
        avg_pr = sum(ratios) / len(ratios) if ratios else 0.0
        cap_value, cap_unit = self._power(capacity)
        gen_value, gen_unit = self._energy(generation)
        Survey = self.env['epc.site.survey']
        survey_total = Survey.search_count([])
        surveyed = Survey.search_count([('feasibility_ids', '!=', False)])

        kpis = [
            self._kpi('Capacity under study', cap_value, 'dec', cap_unit, sub='%s proposals' % len(studies),
                      icon='fa-sun-o', model='epc.feasibility', domain=[]),
            self._kpi('Avg performance ratio', avg_pr, 'pct', sub='target %s%%' % int(PR_TARGET),
                      tone='good' if avg_pr >= PR_TARGET else 'warn', icon='fa-tachometer',
                      model='epc.feasibility', domain=[('performance_ratio', '>', 0)]),
            self._kpi('Expected generation', gen_value, 'dec', gen_unit + '/yr', sub='all proposals combined',
                      icon='fa-bolt', model='epc.feasibility', domain=[]),
            self._kpi('Specific yield', generation / capacity if capacity else 0, 'int', 'kWh/kWp',
                      sub='yearly kWh per kWp installed', icon='fa-line-chart',
                      model='epc.feasibility', domain=[]),
            self._kpi('Survey to feasibility', self._pct(surveyed, survey_total), 'pct',
                      sub='%s of %s surveys studied' % (surveyed, survey_total), icon='fa-exchange',
                      model='epc.site.survey', domain=[]),
        ]

        type_l, type_c, type_d = self._group_selection('epc.feasibility', 'system_type', empty_label='Not set')
        orient_l, orient_c, orient_d = self._group_selection('epc.feasibility', 'module_orientation', empty_label='Not set')
        size_bands = [('Under 25 kW', None, 25), ('25 - 100 kW', 25, 100), ('100 - 500 kW', 100, 500), ('500 kW +', 500, None)]
        size_domains, size_counts = [], []
        for _label, low, high in size_bands:
            dom = []
            if low is not None:
                dom.append(('proposed_capacity_kw', '>=', low))
            if high is not None:
                dom.append(('proposed_capacity_kw', '<', high))
            size_domains.append(dom)
            size_counts.append(Feas.search_count(dom))
        pr_bands = [('Below 70%', None, 70), ('70 - 80%', 70, 80), ('80 - 90%', 80, 90), ('90% +', 90, None)]
        pr_domains, pr_counts = [], []
        for _label, low, high in pr_bands:
            dom = [('performance_ratio', '>', 0)]
            if low is not None:
                dom.append(('performance_ratio', '>=', low))
            if high is not None:
                dom.append(('performance_ratio', '<', high))
            pr_domains.append(dom)
            pr_counts.append(Feas.search_count(dom))

        points = [{'x': s.proposed_capacity_kw, 'y': round(s.annual_generation_estimate_kwh / 1000.0, 1), 'id': s.id}
                  for s in studies if s.proposed_capacity_kw and s.annual_generation_estimate_kwh]

        cards = [
            self._card('system', 'System type', 'Share of proposals', 'doughnut', type_l,
                       [{'label': 'Proposals', 'data': type_c, 'domains': type_d}],
                       model='epc.feasibility', span=2, source='system_type'),
            self._card('size', 'Proposal size bands', 'Number of proposals by capacity', 'bar',
                       [b[0] for b in size_bands], [{'label': 'Proposals', 'data': size_counts, 'domains': size_domains}],
                       model='epc.feasibility', span=2, source='proposed_capacity_kw'),
            self._card('orientation', 'Module orientation', 'Direction the panels face', 'hbar', orient_l,
                       [{'label': 'Proposals', 'data': orient_c, 'domains': orient_d}],
                       model='epc.feasibility', span=2, source='module_orientation'),
            self._card('scatter', 'Capacity vs yearly generation', 'Each dot is a proposal. Click one to open it.',
                       'scatter', [], [{'label': 'Proposal', 'points': points}], model='epc.feasibility', span=3,
                       xlabel='Capacity (kWp)', ylabel='MWh / year',
                       source='proposed_capacity_kw × annual_generation_estimate_kwh'),
            self._card('pr', 'Performance ratio spread', 'How many proposals fall in each range', 'bar',
                       [b[0] for b in pr_bands],
                       [{'label': 'Proposals', 'data': pr_counts, 'domains': pr_domains,
                         'color': ['fail', 'warn', 'pass', 'pass']}],
                       model='epc.feasibility', span=3, source='performance_ratio'),
        ]

        def yield_of(study):
            return study.annual_generation_estimate_kwh / study.proposed_capacity_kw if study.proposed_capacity_kw else 0
        ranked = sorted(studies, key=yield_of, reverse=True)[:6]
        rows = [{'id': s.id, 'cells': [
            s.name, s.partner_id.display_name or '', '{:,.0f}'.format(s.proposed_capacity_kw or 0),
            '%s°' % int(s.module_tilt_angle or 0), '{:,.0f}'.format(yield_of(s)),
            '%.1f%%' % (s.performance_ratio or 0)]} for s in ranked if yield_of(s)]
        table = self._tbl(
            'Best-yield proposals', 'epc.feasibility',
            [('Feasibility', 'start'), ('Customer', 'start'), ('kWp', 'end'), ('Tilt', 'end'),
             ('kWh/kWp', 'end'), ('PR', 'end')],
            rows, source='epc.feasibility · annual_generation_estimate_kwh ÷ proposed_capacity_kw',
            empty='No proposal has capacity and generation filled in yet.')

        self._axis_titles(cards, {'size': ('Capacity band', 'Proposals'), 'orientation': ('Number of proposals', 'Orientation'), 'pr': ('Performance ratio range', 'Proposals')})

        return {'title': 'Feasibility', 'accent': '#8b95f0',
                'intro': 'Technical sizing and yield: what we are proposing and how well it should perform.',
                'kpis': kpis, 'cards': cards, 'table': table}
