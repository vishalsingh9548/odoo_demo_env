# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, models


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_material(self):
        Request = self.env['epc.material.request']
        Line = self.env['epc.material.request.line']
        requests = Request.search([])
        lines = Line.search([])
        # Most quantity columns are computed on the fly, so the maths is done
        # here on the records instead of in SQL.
        short = lines.filtered(lambda l: l.quantity_to_purchase > 0)
        required = sum(lines.mapped('quantity_required'))
        issued = sum(lines.mapped('quantity_issued'))
        remaining = sum(lines.mapped('quantity_remaining_to_order'))
        approved = requests.filtered(lambda r: r.approval_state == 'approved')
        turnaround = self._approval_turnaround_days(approved)
        blocking = len(short.mapped('request_id'))

        kpis = [
            self._kpi('Lines short on stock', len(short), tone='bad' if short else 'good', icon='fa-exclamation-triangle',
                      sub='across %s request(s)' % blocking, model='epc.material.request.line',
                      domain=[('id', 'in', short.ids)]),
            self._kpi('Fulfilment rate', self._pct(issued, required), 'pct', sub='issued ÷ required quantity',
                      tone='good' if required and issued >= required else '', icon='fa-truck',
                      model='epc.material.request.line', domain=[]),
            self._kpi('Request approval time', turnaround, 'dec', 'd', sub='submitted to approved, on average',
                      icon='fa-clock-o', model='epc.material.request', domain=[('approval_state', '=', 'approved')]),
            self._kpi('Still to order', remaining, 'int', 'units', sub='not yet on a purchase order',
                      tone='warn' if remaining else '', icon='fa-shopping-cart',
                      model='epc.material.request.line', domain=[('id', 'in', lines.filtered(
                          lambda l: l.quantity_remaining_to_order > 0).ids)]),
            self._kpi('Issued to site', issued, 'int', 'units', sub='all requests', icon='fa-check-square-o',
                      model='epc.material.request.line', domain=[('id', 'in', lines.filtered('quantity_issued').ids)]),
        ]

        # --- per product: required / in stock / ordered / issued -------------
        by_product = defaultdict(lambda: {'req': 0.0, 'hand': 0.0, 'ord': 0.0, 'iss': 0.0})
        for line in lines:
            key = line.product_id.id or 0
            bucket = by_product[key]
            bucket['req'] += line.quantity_required
            bucket['hand'] = max(bucket['hand'], line.quantity_on_hand)
            bucket['ord'] += line.quantity_ordered
            bucket['iss'] += line.quantity_issued
            bucket['name'] = line.product_id.display_name or line.description or 'Other'
        top = sorted(by_product.items(), key=lambda kv: -kv[1]['req'])[:6]
        names = [v['name'] for _k, v in top]
        domains = [[('product_id', '=', k)] if k else [('product_id', '=', False)] for k, _v in top]

        # --- issue status (computed field, so counted here) ------------------
        status_names = dict(Request._fields['issue_status'].selection)
        status_ids = defaultdict(list)
        for request in requests:
            status_ids[request.issue_status].append(request.id)
        status_keys = [k for k in ('none', 'partial', 'full') if status_ids.get(k)]

        vendor_qty, vendor_ids = defaultdict(float), defaultdict(list)
        for line in lines:
            if line.vendor_id and line.quantity_ordered:
                vendor_qty[line.vendor_id] += line.quantity_ordered
                vendor_ids[line.vendor_id].append(line.id)
        vendors = sorted(vendor_qty, key=lambda v: -vendor_qty[v])[:6]

        month = self._count_by_month('epc.material.request', 'request_date')

        project_lines = defaultdict(lambda: [0.0, 0.0])
        for line in lines:
            if line.request_id.project_id:
                project_lines[line.request_id.project_id][0] += line.quantity_required
                project_lines[line.request_id.project_id][1] += line.quantity_issued
        projects = sorted((p for p, v in project_lines.items() if v[0]),
                          key=lambda p: project_lines[p][1] / project_lines[p][0])[:6]

        cards = [
            self._card('products', 'Required vs in stock vs ordered vs issued', 'The six most requested products, in units',
                       'bar', names, [
                           {'label': 'Required', 'color': 'accent', 'data': [round(v['req'], 1) for _k, v in top], 'domains': domains},
                           {'label': 'In stock', 'color': 'neutral', 'data': [round(v['hand'], 1) for _k, v in top], 'domains': domains},
                           {'label': 'Ordered', 'color': 'warn', 'data': [round(v['ord'], 1) for _k, v in top], 'domains': domains},
                           {'label': 'Issued', 'color': 'pass', 'data': [round(v['iss'], 1) for _k, v in top], 'domains': domains}],
                       model='epc.material.request.line', span=4, source='epc.material.request.line · quantity_*'),
            self._card('issue', 'Issue status', 'How much of each request has reached site', 'doughnut',
                       [status_names[k] for k in status_keys],
                       [{'label': 'Requests', 'data': [len(status_ids[k]) for k in status_keys],
                         'domains': [[('id', 'in', status_ids[k])] for k in status_keys],
                         'color': [{'none': 'fail', 'partial': 'warn', 'full': 'pass'}[k] for k in status_keys]}],
                       model='epc.material.request', span=2, source='epc.material.request · issue_status'),
            self._card('vendors', 'Vendors by quantity ordered', 'Who we buy the most from', 'hbar',
                       [v.display_name for v in vendors],
                       [{'label': 'Units ordered', 'data': [round(vendor_qty[v], 1) for v in vendors],
                         'domains': [[('id', 'in', vendor_ids[v])] for v in vendors]}],
                       model='epc.material.request.line', span=3, source='vendor_id · quantity_ordered'),
            self._card('monthly', 'Requests raised per month', 'Demand on the store', 'line',
                       month[0], [{'label': 'Requests', 'data': month[1], 'domains': month[2]}],
                       model='epc.material.request', span=3, source='epc.material.request · request_date'),
            self._card('projects', 'Fulfilment by project', 'Issued quantity as a share of required, lowest first', 'hbar',
                       [p.display_name for p in projects],
                       [{'label': 'Fulfilled %', 'color': 'pass',
                         'data': [self._pct(project_lines[p][1], project_lines[p][0]) for p in projects],
                         'domains': [[('request_id.project_id', '=', p.id)] for p in projects]}],
                       model='epc.material.request.line', span=6, pct=True, source='epc.material.request · project_id'),
        ]

        rows = []
        for line in short.sorted('quantity_to_purchase', reverse=True)[:8]:
            rows.append({'id': line.request_id.id, 'cells': [
                line.product_id.display_name or line.description or '', line.request_id.name,
                '{:,.0f}'.format(line.quantity_required), '{:,.0f}'.format(line.quantity_on_hand),
                {'text': '{:,.0f}'.format(line.quantity_to_purchase), 'pill': 'bad'},
                line.vendor_id.display_name or '-']})
        table = self._tbl(
            'Items short on stock', 'epc.material.request',
            [('Product', 'start'), ('Request', 'start'), ('Required', 'end'), ('In stock', 'end'),
             ('To buy', 'end'), ('Vendor', 'start')],
            rows, source='epc.material.request.line · quantity_to_purchase > 0',
            empty='Every requested item is covered by stock.')

        return {'title': 'Material Requests', 'accent': '#7fc8e8',
                'intro': 'Whether stock covers site needs, what is still to buy, and how much material has reached site.',
                'kpis': kpis, 'cards': cards, 'table': table}
