# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, models


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_amc(self):
        Contract = self.env['epc.amc.contract']
        today = self._today()
        iso = lambda d: d.isoformat()
        active = [('state', '=', 'active')]
        contracts = Contract.search(active)

        renew_domain = active + [('end_date', '>=', iso(today)), ('end_date', '<=', iso(today + timedelta(days=90)))]
        renewing = Contract.search(renew_domain)
        warranty_domain = [('warranty_end_date', '>=', iso(today)), ('warranty_end_date', '<=', iso(today + timedelta(days=60)))]
        sla = [c.sla_response_hours for c in contracts if c.sla_response_hours]
        six_months = today - relativedelta(months=6)
        Ticket = self.env['helpdesk.ticket']
        ticket_domain = [('amc_contract_id', '!=', False), ('create_date', '>=', iso(six_months))]
        tickets = Ticket.search_count(ticket_domain)

        kpis = [
            self._kpi('Renewals due in 90 days', len(renewing), tone='warn' if renewing else 'good', icon='fa-refresh',
                      sub='%s at stake' % self._money_text(sum(renewing.mapped('contract_value'))),
                      model='epc.amc.contract', domain=renew_domain),
            self._kpi('Annual contract value', sum(contracts.mapped('contract_value')), 'money',
                      sub='%s active contract(s)' % len(contracts), icon='fa-money', model='epc.amc.contract', domain=active),
            self._kpi('Tickets per contract', tickets / len(contracts) if contracts else 0, 'dec',
                      sub='%s tickets in the last 6 months' % tickets, icon='fa-headphones',
                      model='helpdesk.ticket', domain=ticket_domain),
            self._kpi('Avg SLA promise', sum(sla) / len(sla) if sla else 0, 'dec', 'h', sub='response time target',
                      icon='fa-hourglass-half', model='epc.amc.contract', domain=active + [('sla_response_hours', '>', 0)]),
            self._kpi('Warranty ends in 60 days', Contract.search_count(warranty_domain), icon='fa-shield',
                      sub='good moment to offer an AMC', model='epc.amc.contract', domain=warranty_domain),
        ]

        buckets = [('Overdue', None, -1), ('0 - 30 days', 0, 30), ('31 - 60 days', 31, 60),
                   ('61 - 90 days', 61, 90), ('91 - 180 days', 91, 180)]
        b_counts, b_domains = [], []
        for _label, low, high in buckets:
            dom = list(active)
            if low is None:
                dom.append(('end_date', '<', iso(today)))
            else:
                dom += [('end_date', '>=', iso(today + timedelta(days=low))), ('end_date', '<=', iso(today + timedelta(days=high)))]
            b_domains.append(dom)
            b_counts.append(Contract.search_count(dom))

        freq_names = dict(Contract._fields['service_frequency'].selection)
        freq_rows = Contract._read_group(active, ['service_frequency'], ['contract_value:sum'])
        freq_rows = [r for r in freq_rows if r[1]]
        month = self._count_by_month('helpdesk.ticket', 'create_date', [('amc_contract_id', '!=', False)])
        busy = sorted(Ticket._read_group([('amc_contract_id', '!=', False), ('create_date', '>=', iso(six_months))],
                                         ['amc_contract_id'], ['__count']), key=lambda r: -r[1])[:5]

        cards = [
            self._card('renewals', 'Renewal pipeline', 'Active contracts by time left before they end', 'bar',
                       [b[0] for b in buckets],
                       [{'label': 'Contracts', 'data': b_counts, 'domains': b_domains,
                         'color': ['fail', 'warn', 'warn', 'accent', 'pass']}],
                       model='epc.amc.contract', span=3, source='epc.amc.contract · end_date'),
            self._card('frequency', 'Value by service frequency', 'Where the AMC income comes from', 'doughnut',
                       [freq_names.get(r[0], 'Not set') for r in freq_rows],
                       [{'label': 'Contract value', 'data': [round(r[1], 2) for r in freq_rows],
                         'domains': [active + [('service_frequency', '=', r[0])] for r in freq_rows]}],
                       model='epc.amc.contract', span=3, source='epc.amc.contract · service_frequency, contract_value'),
            self._card('tickets', 'Tickets raised each month', 'Support demand from AMC customers', 'bar',
                       month[0], [{'label': 'Tickets', 'data': month[1], 'domains': month[2]}],
                       model='helpdesk.ticket', span=3, source='helpdesk.ticket · amc_contract_id, create_date'),
            self._card('busiest', 'Busiest contracts', 'Tickets in the last six months', 'hbar',
                       [r[0].display_name for r in busy],
                       [{'label': 'Tickets', 'color': 'warn', 'data': [r[1] for r in busy],
                         'domains': [[('amc_contract_id', '=', r[0].id)] for r in busy]}],
                       model='helpdesk.ticket', span=3, source='helpdesk.ticket · amc_contract_id'),
        ]

        due = Contract.search(active + [('end_date', '!=', False), ('end_date', '<=', iso(today + timedelta(days=90)))],
                              order='end_date', limit=8)
        rows = []
        for contract in due:
            left = (contract.end_date - today).days
            rows.append({'id': contract.id, 'cells': [
                contract.name, contract.partner_id.display_name or '', self._short_date(contract.end_date),
                '%s d' % left if left >= 0 else '%s d ago' % abs(left), self._money_text(contract.contract_value),
                {'text': 'Overdue' if left < 0 else ('Renew now' if left <= 30 else 'Upcoming'),
                 'pill': 'bad' if left < 0 else ('warn' if left <= 30 else 'neutral')}]})
        table = self._tbl(
            'Contracts to renew next', 'epc.amc.contract',
            [('Contract', 'start'), ('Customer', 'start'), ('Ends', 'start'), ('Left', 'end'), ('Value', 'end'),
             ('Status', 'start')],
            rows, source='epc.amc.contract · active, end_date within 90 days', empty='No contract ends in the next 90 days.')

        return {'title': 'AMC', 'accent': '#86d0e0',
                'intro': 'Renewals, service load and warranty cliffs. Contract status and next visits stay on the main dashboard.',
                'kpis': kpis, 'cards': cards, 'table': table}
