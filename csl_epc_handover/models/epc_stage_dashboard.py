# -*- coding: utf-8 -*-
from odoo import api, models

# (file-name field, label) of the four documents the customer pack needs
DOCUMENTS = [
    ('as_built_drawing_filename', 'As-built drawing'),
    ('test_reports_filename', 'Test reports'),
    ('om_manual_filename', 'O&M manual'),
    ('warranty_certificate_filename', 'Warranty certificate'),
]


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_handover(self):
        Handover = self.env['epc.handover']
        handovers = Handover.search([])
        total = len(handovers)
        missing_by_doc = {f: handovers.filtered(lambda h, f=f: not h[f]) for f, _l in DOCUMENTS}
        missing_total = sum(len(v) for v in missing_by_doc.values())
        any_missing = handovers.filtered(lambda h: any(not h[f] for f, _l in DOCUMENTS))
        trained = handovers.filtered('customer_training_done')
        month_start = self._today().replace(day=1)
        month_domain = [('closure_date', '>=', month_start.isoformat())]
        this_month = Handover.search_count(month_domain)
        approved = handovers.filtered(lambda h: h.approval_state == 'approved')
        waiting = handovers.filtered(lambda h: h.approval_state == 'submitted')

        kpis = [
            self._kpi('Document pack complete', self._pct(total * len(DOCUMENTS) - missing_total, total * len(DOCUMENTS)),
                      'pct', sub='of the %s required files' % len(DOCUMENTS), tone='good' if not missing_total else 'warn',
                      icon='fa-folder-open-o', model='epc.handover', domain=[]),
            self._kpi('Handovers missing documents', len(any_missing), tone='bad' if any_missing else 'good',
                      icon='fa-exclamation-circle', sub='%s file(s) missing in total' % missing_total,
                      model='epc.handover', domain=[('id', 'in', any_missing.ids)]),
            self._kpi('Customer training done', self._pct(len(trained), total), 'pct',
                      sub='%s session(s) still pending' % (total - len(trained)), icon='fa-graduation-cap',
                      model='epc.handover', domain=[('customer_training_done', '=', True)]),
            self._kpi('Approval time', self._approval_turnaround_days(approved), 'dec', 'd',
                      sub='submitted to approved, on average', icon='fa-clock-o',
                      model='epc.handover', domain=[('approval_state', '=', 'approved')]),
            self._kpi('Closed this month', this_month, icon='fa-flag-checkered',
                      sub='%s waiting for approval' % len(waiting), model='epc.handover', domain=month_domain),
        ]

        recent = handovers.sorted('id', reverse=True)[:8]
        miss_order = sorted(DOCUMENTS, key=lambda d: -len(missing_by_doc[d[0]]))
        month = self._count_by_month('epc.handover', 'closure_date')
        training_domains = [[('customer_training_done', '=', True)], [('customer_training_done', '=', False)]]
        state_l, state_c, state_d = self._group_selection('epc.handover', 'approval_state')

        cards = [
            self._card('matrix', 'Document checklist by project', 'Latest handovers. Green means uploaded.', 'matrix', [], [],
                       model='epc.handover', span=4, source='as-built, test reports, O&M manual, warranty certificate',
                       cols=[l for _f, l in DOCUMENTS],
                       rows=[{'id': h.id, 'label': h.project_id.display_name or h.name,
                              'cells': [bool(h[f]) for f, _l in DOCUMENTS]} for h in recent]),
            self._card('missing', 'Most often missing', 'Documents not uploaded yet', 'hbar',
                       [l for _f, l in miss_order],
                       [{'label': 'Missing', 'color': 'fail', 'data': [len(missing_by_doc[f]) for f, _l in miss_order],
                         'domains': [[(f, '=', False)] for f, _l in miss_order]}],
                       model='epc.handover', span=2, source='epc.handover · document file names'),
            self._card('monthly', 'Handovers closed per month', 'By closure date', 'bar',
                       month[0], [{'label': 'Handovers', 'data': month[1], 'domains': month[2]}],
                       model='epc.handover', span=2, source='epc.handover · closure_date'),
            self._card('training', 'Customer training', 'Sessions completed vs pending', 'doughnut',
                       ['Done', 'Pending'], [{'label': 'Handovers', 'color': ['pass', 'warn'],
                                              'data': [len(trained), total - len(trained)], 'domains': training_domains}],
                       model='epc.handover', span=2, source='epc.handover · customer_training_done'),
            self._card('status', 'Approval status', 'Where each handover stands', 'doughnut', state_l,
                       [{'label': 'Handovers', 'data': state_c, 'domains': state_d,
                         'color': [{'To Submit': 'neutral', 'Submitted for Approval': 'warn', 'Approved': 'pass',
                                    'Rejected': 'fail'}.get(l, 'neutral') for l in state_l]}],
                       model='epc.handover', span=2, source='epc.handover · approval_state'),
        ]

        rows = []
        for handover in any_missing.sorted('id', reverse=True)[:8]:
            gaps = len([f for f, _l in DOCUMENTS if not handover[f]])
            rows.append({'id': handover.id, 'cells': [
                handover.name, handover.project_id.display_name or '', {'text': '%s missing' % gaps, 'pill': 'bad'},
                {'text': 'Done' if handover.customer_training_done else 'Pending',
                 'pill': 'good' if handover.customer_training_done else 'warn'},
                dict(handover._fields['approval_state'].selection).get(handover.approval_state, '')]})
        table = self._tbl(
            'Handovers with missing documents', 'epc.handover',
            [('Handover', 'start'), ('Project', 'start'), ('Documents', 'start'), ('Training', 'start'), ('Status', 'start')],
            rows, source='epc.handover · empty document fields', empty='Every handover has its full document pack.')

        return {'title': 'Handover & Closure', 'accent': '#9fb4d8',
                'intro': 'Is the customer pack complete, and how smoothly projects close out.',
                'kpis': kpis, 'cards': cards, 'table': table}
