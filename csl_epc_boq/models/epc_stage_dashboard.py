# -*- coding: utf-8 -*-
from odoo import api, fields, models

MARGIN_FLOOR = 12.0   # margin (%) under which a BOQ is flagged for a pricing review
MANY_REVISIONS = 3    # a BOQ on this version or later is flagged as heavily revised


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_boq(self):
        Boq = self.env['epc.boq']
        live_domain = [('superseded', '=', False)]
        live = Boq.search(live_domain)
        total_cost = sum(live.mapped('total_cost'))
        total_kw = sum(live.mapped('capacity_kw'))
        margins = live.mapped('margin_percent')
        low_domain = live_domain + [('margin_percent', '<', MARGIN_FLOOR)]
        low = live.filtered(lambda b: b.margin_percent < MARGIN_FLOOR)
        revised_domain = [('revision_number', '>', 1)]
        approved = live.filtered(lambda b: b.approval_state == 'approved')
        quoted = approved.filtered('sale_order_id')
        all_boqs = Boq.search_count([])

        kpis = [
            self._kpi('Avg cost per kW', total_cost / total_kw if total_kw else 0, 'money', '/kW',
                      sub='latest versions of every BOQ', icon='fa-calculator', model='epc.boq', domain=live_domain),
            self._kpi('Avg margin', sum(margins) / len(margins) if margins else 0, 'pct',
                      sub='floor is %s%%' % int(MARGIN_FLOOR), icon='fa-percent', model='epc.boq', domain=live_domain),
            self._kpi('Lowest margin', min(margins) if margins else 0, 'pct',
                      sub=('%s under the floor' % len(low)) if low else 'none under the floor',
                      tone='bad' if low else 'good', trend='down' if low else '', icon='fa-arrow-down',
                      model='epc.boq', domain=low_domain),
            self._kpi('Revised BOQs', Boq.search_count(revised_domain), sub='%s BOQ records in total' % all_boqs,
                      icon='fa-refresh', model='epc.boq', domain=revised_domain),
            self._kpi('Quotation created', self._pct(len(quoted), len(approved)), 'pct',
                      sub='%s of %s approved BOQs' % (len(quoted), len(approved)), icon='fa-file-text-o',
                      model='epc.boq', domain=live_domain + [('approval_state', '=', 'approved')]),
        ]

        Line = self.env['epc.boq.line']
        category_names = dict(Line._fields['category'].selection)
        line_domain = [('boq_id.superseded', '=', False)]
        rows = Line._read_group(line_domain, ['category'], ['subtotal:sum'])
        rows = sorted(rows, key=lambda r: -(r[1] or 0))
        cat_labels = [category_names.get(r[0], 'Other') for r in rows if r[1]]
        cat_values = [round(r[1], 2) for r in rows if r[1]]
        cat_domains = [line_domain + [('category', '=', r[0])] for r in rows if r[1]]

        latest = Boq.search(live_domain, order='create_date desc', limit=10)
        latest = latest.sorted('create_date')
        margin_card = self._card(
            'margin', 'Margin by BOQ', 'Red bars are below the %s%% margin floor' % int(MARGIN_FLOOR), 'bar',
            [b.name for b in latest],
            [{'label': 'Margin %', 'data': [round(b.margin_percent, 1) for b in latest],
              'color': ['fail' if b.margin_percent < MARGIN_FLOOR else 'pass' for b in latest],
              'domains': [[('id', '=', b.id)] for b in latest]}],
            model='epc.boq', span=4, source='epc.boq · margin_percent (latest 10)')

        trend_labels, trend_values, trend_domains = [], [], []
        for label, start, end in self._months():
            dom = live_domain + [('create_date', '>=', fields.Date.to_string(start)), ('create_date', '<', fields.Date.to_string(end))]
            month_boqs = Boq.search(dom)
            kw = sum(month_boqs.mapped('capacity_kw'))
            trend_labels.append(label)
            trend_values.append(round(sum(month_boqs.mapped('total_cost')) / kw) if kw else None)
            trend_domains.append(dom)

        rev_rows = sorted(Boq._read_group([], ['revision_number'], ['__count']), key=lambda r: r[0])
        rev_labels = ['v%s' % r[0] for r in rev_rows]
        rev_counts = [r[1] for r in rev_rows]
        rev_colors = ['pass' if r[0] <= 1 else 'warn' if r[0] < MANY_REVISIONS else 'fail' for r in rev_rows]
        rev_domains = [[('revision_number', '=', r[0])] for r in rev_rows]

        cards = [
            self._card('category', 'Where the cost goes', 'Cost by category across current BOQs', 'doughnut',
                       cat_labels, [{'label': 'Cost', 'data': cat_values, 'domains': cat_domains}],
                       model='epc.boq.line', span=2, source='epc.boq.line · category, subtotal'),
            margin_card,
            self._card('trend', 'Cost per kW over time', 'BOQs created in each month, cost divided by capacity', 'line',
                       trend_labels, [{'label': 'Cost per kW', 'data': trend_values, 'domains': trend_domains}],
                       model='epc.boq', span=3, source='epc.boq · total_cost ÷ capacity_kw by create_date'),
            self._card('revisions', 'Versions per BOQ', 'How many BOQ records sit at each version', 'bar',
                       rev_labels, [{'label': 'BOQs', 'data': rev_counts, 'domains': rev_domains, 'color': rev_colors}],
                       model='epc.boq', span=3, source='epc.boq · revision_number'),
        ]

        review = live.filtered(lambda b: b.margin_percent < MARGIN_FLOOR or b.revision_number >= MANY_REVISIONS)
        table_rows = []
        for boq in review.sorted('margin_percent')[:8]:
            table_rows.append({'id': boq.id, 'cells': [
                boq.name, boq.partner_id.display_name or '', '{:,.0f}'.format(boq.capacity_kw or 0),
                self._money_text(boq.total_cost),
                {'text': '%.1f%%' % boq.margin_percent, 'pill': 'bad' if boq.margin_percent < MARGIN_FLOOR else 'good'},
                'v%s' % boq.revision_number]})
        table = self._tbl(
            'BOQs that need a pricing review', 'epc.boq',
            [('BOQ', 'start'), ('Customer', 'start'), ('kW', 'end'), ('Cost', 'end'), ('Margin', 'end'), ('Version', 'end')],
            table_rows, source='epc.boq · margin below floor or revision_number >= %s' % MANY_REVISIONS,
            empty='No BOQ needs a pricing review.')

        self._axis_titles(cards, {'margin': ('BOQ', 'Margin (%)'), 'trend': ('Month', 'Cost per kW'), 'revisions': ('Version', 'Number of BOQs')})

        return {'title': 'BOQ & Costing', 'accent': '#b4a7f0',
                'intro': 'Cost and margin health of every bill of quantities, and how often prices were revised.',
                'kpis': kpis, 'cards': cards, 'table': table}
