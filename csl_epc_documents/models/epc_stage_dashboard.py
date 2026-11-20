# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

DONE = ('submitted', 'accepted')
NOT_DONE = ['pending', 'ready', 'rejected']
CATEGORIES = [('kyc', 'KYC'), ('subsidy', 'Subsidy'), ('net_metering', 'Net metering'),
              ('structure', 'Structure'), ('commissioning', 'Commissioning')]


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_documents(self):
        Doc = self.env['epc.project.document']
        docs = Doc.search([])
        today = self._today()
        today_s = fields.Date.to_string(today)
        done = docs.filtered(lambda d: d.state in DONE)
        pending_dom = [('mandatory', '=', True), ('state', 'in', NOT_DONE)]
        pending = Doc.search(pending_dom)
        overdue_dom = [('due_date', '<', today_s), ('state', 'in', NOT_DONE)]
        overdue = Doc.search(overdue_dom)
        oldest = max([(today - d.due_date).days for d in overdue], default=0)
        rejected = docs.filtered(lambda d: d.state == 'rejected')
        submitted = docs.filtered(lambda d: d.submitted_date)
        avg_submit = round(sum(max((d.submitted_date - d.create_date.date()).days, 0) for d in submitted) / len(submitted), 1) if submitted else 0.0
        projects = docs.mapped('project_id')
        ready_projects = projects.filtered(lambda p: not p.epc_document_pending_mandatory)
        projects_with_pending = pending.mapped('project_id')

        kpis = [
            self._kpi('Papers done', self._pct(len(done), len(docs)), 'pct',
                      sub='%s project(s), %s paper(s)' % (len(projects), len(docs)), icon='fa-files-o',
                      model='epc.project.document', domain=[('state', 'in', list(DONE))]),
            self._kpi('Mandatory papers pending', len(pending), tone='warn' if pending else 'good',
                      sub='across %s project(s)' % len(projects_with_pending), icon='fa-hourglass-half',
                      model='epc.project.document', domain=pending_dom),
            self._kpi('Overdue', len(overdue), tone='bad' if overdue else 'good',
                      sub=('oldest %s days late' % oldest) if overdue else 'nothing late', trend='down' if overdue else '',
                      icon='fa-exclamation-triangle', model='epc.project.document', domain=overdue_dom),
            self._kpi('Sent back by authority', len(rejected), sub='need correction and resubmission', icon='fa-flag',
                      model='epc.project.document', domain=[('state', '=', 'rejected')]),
            self._kpi('Average time to submit', avg_submit, 'dec', 'days', sub='from the paper being created', icon='fa-clock-o',
                      model='epc.project.document', domain=[('submitted_date', '!=', False)]),
            self._kpi('Projects fully ready', len(ready_projects), tone='good' if ready_projects else '',
                      sub='every mandatory paper submitted', icon='fa-check-circle-o',
                      model='project.project', domain=[('id', 'in', ready_projects.ids)]),
        ]

        recent = projects.sorted('id', reverse=True)[:6]
        matrix_rows = []
        for project in recent:
            cells = []
            for key, _label in CATEGORIES:
                group = project.epc_document_ids.filtered(lambda d, k=key: d.category == k)
                cells.append(bool(group) and all(d.state in DONE for d in group))
            matrix_rows.append({'id': project.id, 'label': project.display_name, 'cells': cells})
        state_l, state_c, state_d = self._group_selection('epc.project.document', 'state')
        state_color = {'Pending': 'warn', 'Ready': 'neutral', 'Submitted': 'accent', 'Accepted': 'pass', 'Rejected': 'fail'}
        cat_l, cat_c, cat_d = self._group_selection('epc.project.document', 'category', pending_dom, order='desc')
        over_l, over_c, over_d = self._group_selection('epc.project.document', 'project_id', overdue_dom, order='desc')
        over_l, over_c, over_d = over_l[:6], over_c[:6], over_d[:6]
        monday = today - timedelta(days=today.weekday())
        week_l, week_c, week_d = [], [], []
        for back in range(5, -1, -1):
            start = monday - timedelta(days=7 * back)
            end = start + timedelta(days=7)
            dom = self._range('submitted_date', start, end)
            week_l.append('W%s' % start.isocalendar()[1])
            week_c.append(Doc.search_count(dom))
            week_d.append(dom)

        cards = [
            self._card('matrix', 'Paper checklist by project', 'Latest projects. A tick means every paper of that kind is submitted or accepted.',
                       'matrix', [], [], model='project.project', span=4, source='epc.project.document · category, state',
                       cols=[l for _k, l in CATEGORIES], rows=matrix_rows),
            self._card('status', 'Status of all papers', 'Every paper on every project', 'doughnut', state_l,
                       [{'label': 'Papers', 'data': state_c, 'domains': state_d,
                         'color': [state_color.get(l, 'neutral') for l in state_l]}],
                       model='epc.project.document', span=2, source='epc.project.document · state'),
            self._card('category', 'Still pending, by category', 'Mandatory papers only', 'hbar', cat_l,
                       [{'label': 'Papers', 'color': 'warn', 'data': cat_c, 'domains': cat_d}],
                       model='epc.project.document', span=2, source='epc.project.document · category, mandatory'),
            self._card('weekly', 'Submitted per week', 'Last six weeks', 'bar', week_l,
                       [{'label': 'Papers', 'data': week_c, 'domains': week_d}],
                       model='epc.project.document', span=2, source='epc.project.document · submitted_date'),
            self._card('overdue', 'Overdue by project', 'Papers past their due date', 'hbar', over_l,
                       [{'label': 'Papers', 'color': 'fail', 'data': over_c, 'domains': over_d}],
                       model='epc.project.document', span=2, source='epc.project.document · due_date'),
        ]
        self._axis_titles(cards, {'category': ('Number of papers', 'Category'), 'weekly': ('Week', 'Papers submitted'),
                                  'overdue': ('Number of papers', 'Project')})

        state_names = dict(Doc._fields['state'].selection)
        cat_names = dict(Doc._fields['category'].selection)
        rows = []
        for doc in overdue.sorted('due_date')[:8]:
            late = (today - doc.due_date).days
            rows.append({'id': doc.id, 'cells': [
                doc.project_id.display_name or '', doc.name, cat_names.get(doc.category, ''), self._short_date(doc.due_date),
                {'text': str(late), 'pill': 'bad'},
                {'text': state_names.get(doc.state, ''), 'pill': 'bad' if doc.state in ('pending', 'rejected') else 'warn'}]})
        table = self._tbl(
            'Overdue papers', 'epc.project.document',
            [('Project', 'start'), ('Paper', 'start'), ('Category', 'start'), ('Due', 'start'), ('Days late', 'end'), ('Status', 'start')],
            rows, source='epc.project.document · due_date', empty='No paper is overdue.')

        return {'title': 'Government Documents', 'accent': '#9fb4d8',
                'intro': "How complete each project's paperwork is, what is overdue, and what the authority sent back.",
                'kpis': kpis, 'cards': cards, 'table': table}
