# -*- coding: utf-8 -*-
from odoo import api, models

APPROVED = [('approval_state', '=', 'approved')]
WAITING_DAYS = 5   # a submitted design waiting longer than this is called out


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    # Domain for "field between low (inclusive) and high (exclusive)"; either end may be None
    @api.model
    def _design_band(self, base, field, low, high):
        domain = list(base)
        if low is not None:
            domain.append((field, '>=', low))
        if high is not None:
            domain.append((field, '<', high))
        return domain

    @api.model
    def _dashboard_design(self):
        Design = self.env['epc.design']
        designs = Design.search([])
        approved = designs.filtered(lambda d: d.approval_state == 'approved')
        waiting = designs.filtered(lambda d: d.approval_state == 'submitted')
        oldest = max([self._days_since(d.submitted_date) or 0 for d in waiting], default=0)
        flagged = designs.filtered('design_warning')
        capacity = sum(approved.mapped('dc_capacity_kw'))
        cap_value, cap_unit = self._power(capacity)
        ratios = approved.filtered(lambda d: d.dc_ac_ratio > 0)
        avg_ratio = round(sum(ratios.mapped('dc_ac_ratio')) / len(ratios), 2) if ratios else 0.0
        payback = approved.filtered(lambda d: d.payback_years > 0)
        avg_payback = round(sum(payback.mapped('payback_years')) / len(payback), 1) if payback else 0.0
        with_boq = approved.filtered('boq_ids')
        no_boq = approved - with_boq

        kpis = [
            self._kpi('Awaiting approval', len(waiting), tone='warn' if waiting else 'good',
                      sub=('oldest %s days' % oldest) if waiting else 'nothing waiting', icon='fa-hourglass-half',
                      model='epc.design', domain=[('approval_state', '=', 'submitted')]),
            self._kpi('Designs with warnings', len(flagged), tone='bad' if flagged else 'good',
                      sub='string voltage or count does not fit' if flagged else 'all designs fit',
                      trend='down' if flagged else '', icon='fa-exclamation-triangle',
                      model='epc.design', domain=[('id', 'in', flagged.ids)]),
            self._kpi('Designed capacity', cap_value, 'dec', cap_unit, sub='DC, approved designs', icon='fa-bolt',
                      model='epc.design', domain=APPROVED),
            self._kpi('Average DC/AC ratio', avg_ratio, 'dec', tone='good' if 1.0 <= avg_ratio <= 1.4 else 'warn',
                      sub='healthy range 1.0 to 1.4', icon='fa-tachometer',
                      model='epc.design', domain=APPROVED + [('dc_ac_ratio', '>', 0)]),
            self._kpi('Average payback', avg_payback, 'dec', 'years', sub='where a cost was entered', icon='fa-clock-o',
                      model='epc.design', domain=APPROVED + [('payback_years', '>', 0)]),
            self._kpi('Approved designs with a BOQ', self._pct(len(with_boq), len(approved)), 'pct',
                      sub='%s approved design(s) not costed yet' % len(no_boq), icon='fa-check-circle-o',
                      model='epc.design', domain=APPROVED + [('boq_ids', '=', False)]),
        ]

        state_l, state_c, state_d = self._group_selection('epc.design', 'approval_state')
        month = self._count_by_month('epc.design', 'create_date')
        mount_sel = self.env['epc.design']._fields['mounting_type'].selection
        mount_l, mount_c, mount_d = [], [], []
        for key, label in mount_sel:
            dom = APPROVED + [('mounting_type', '=', key)]
            kw = sum(Design.search(dom).mapped('dc_capacity_kw'))
            if kw:
                mount_l.append(label)
                mount_c.append(round(kw, 1))
                mount_d.append(dom)
        ratio_bands = [('below 1.0', None, 1.0), ('1.0 to 1.2', 1.0, 1.2), ('1.2 to 1.4', 1.2, 1.4), ('1.4 and above', 1.4, None)]
        ratio_dom = [self._design_band(APPROVED + [('dc_ac_ratio', '>', 0)], 'dc_ac_ratio', lo, hi) for _l, lo, hi in ratio_bands]
        pay_bands = [('under 3 years', None, 3), ('3 to 5 years', 3, 5), ('5 to 7 years', 5, 7), ('7 years and over', 7, None)]
        pay_dom = [self._design_band(APPROVED + [('payback_years', '>', 0)], 'payback_years', lo, hi) for _l, lo, hi in pay_bands]

        cards = [
            self._card('pipeline', 'Approval pipeline', 'Where every design stands', 'hbar', state_l,
                       [{'label': 'Designs', 'data': state_c, 'domains': state_d}],
                       model='epc.design', span=3, source='epc.design · approval_state'),
            self._card('monthly', 'Designs created per month', 'By creation date', 'bar', month[0],
                       [{'label': 'Designs', 'data': month[1], 'domains': month[2]}],
                       model='epc.design', span=3, source='epc.design · create_date'),
            self._card('mounting', 'Capacity by mounting type', 'kWp DC of approved designs', 'doughnut', mount_l,
                       [{'label': 'kWp', 'data': mount_c, 'domains': mount_d}],
                       model='epc.design', span=2, source='epc.design · mounting_type, dc_capacity_kw'),
            self._card('ratio', 'DC/AC ratio spread', 'Approved designs by ratio band', 'bar', [b[0] for b in ratio_bands],
                       [{'label': 'Designs', 'data': [Design.search_count(d) for d in ratio_dom], 'domains': ratio_dom}],
                       model='epc.design', span=2, source='epc.design · dc_ac_ratio'),
            self._card('payback', 'Estimated payback', 'Approved designs with a cost entered', 'bar', [b[0] for b in pay_bands],
                       [{'label': 'Designs', 'data': [Design.search_count(d) for d in pay_dom], 'domains': pay_dom}],
                       model='epc.design', span=2, source='epc.design · payback_years'),
        ]
        self._axis_titles(cards, {'pipeline': ('Number of designs', 'Status'), 'monthly': ('Month', 'Designs'),
                                  'ratio': ('DC/AC ratio', 'Designs'), 'payback': ('Payback', 'Designs')})

        attention = designs.filtered(lambda d: d.design_warning or d.approval_state == 'rejected' or (
            d.approval_state == 'submitted' and (self._days_since(d.submitted_date) or 0) >= WAITING_DAYS))
        state_names = dict(Design._fields['approval_state'].selection)
        rows = []
        for design in attention.sorted('id', reverse=True)[:8]:
            if design.design_warning:
                note = {'text': design.design_warning.split('\n')[0][:60], 'pill': 'bad'}
            elif design.approval_state == 'rejected':
                note = {'text': 'Sent back for rework', 'pill': 'bad'}
            else:
                note = {'text': 'Waiting %s days' % (self._days_since(design.submitted_date) or 0), 'pill': 'warn'}
            rows.append({'id': design.id, 'cells': [
                design.name, design.partner_id.display_name or '', '%.2f' % design.dc_capacity_kw,
                '%.2f' % design.dc_ac_ratio, note,
                {'text': state_names.get(design.approval_state, ''),
                 'pill': {'approved': 'good', 'rejected': 'bad', 'submitted': 'warn'}.get(design.approval_state, 'neutral')}]})
        table = self._tbl(
            'Designs needing attention', 'epc.design',
            [('Design', 'start'), ('Customer', 'start'), ('DC kWp', 'end'), ('DC/AC', 'end'), ('Note', 'start'), ('Status', 'start')],
            rows, source='epc.design · design_warning, approval_state', empty='No design needs attention.')

        return {'title': 'System Design', 'accent': '#8b95f0',
                'intro': 'How many designs wait for sign-off, which ones have warnings, and how much capacity is on the drawing board.',
                'kpis': kpis, 'cards': cards, 'table': table}
