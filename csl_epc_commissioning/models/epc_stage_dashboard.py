# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models

PUNCH_OLD_DAYS = 14   # an open punch item older than this is called out


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_commissioning(self):
        Comm = self.env['epc.commissioning']
        Punch = self.env['epc.commissioning.punch']
        comms = Comm.search([])
        total = len(comms)
        today = self._today()
        now = fields.Datetime.now()

        awaiting_domain = [('customer_approved', '=', False)]
        awaiting = comms.filtered(lambda c: not c.customer_approved)
        oldest = max([self._days_since(c.create_date) or 0 for c in awaiting], default=0)
        open_punch = Punch.search([('done', '=', False)])
        old_punch = open_punch.filtered(lambda p: p.create_date and p.create_date < now - timedelta(days=PUNCH_OLD_DAYS))
        verified = sum(comms.mapped('generation_verification_kwh'))
        cert_domain = [('commissioning_certificate_filename', '!=', False)]
        certified = comms.filtered('commissioning_certificate_filename')

        # days from commissioning to the handover of the same project
        gaps, gap_ids = [], []
        for handover in self.env['epc.handover'].search([('closure_date', '!=', False)]):
            comm = comms.filtered(lambda c, h=handover: c.project_id == h.project_id and c.commissioning_date)[:1]
            if comm:
                gaps.append((handover.closure_date - comm.commissioning_date).days)
                gap_ids.append(handover.id)

        kpis = [
            self._kpi('Awaiting customer approval', len(awaiting), tone='warn' if awaiting else 'good',
                      sub=('oldest %s days' % oldest) if awaiting else 'nothing waiting', icon='fa-hourglass-half',
                      model='epc.commissioning', domain=awaiting_domain),
            self._kpi('Open punch items', len(open_punch), tone='bad' if old_punch else ('warn' if open_punch else 'good'),
                      sub='%s older than %s days' % (len(old_punch), PUNCH_OLD_DAYS), trend='down' if old_punch else '',
                      icon='fa-list-ul', model='epc.commissioning.punch', domain=[('done', '=', False)]),
            self._kpi('Commissioning to handover', sum(gaps) / len(gaps) if gaps else 0, 'dec', 'd',
                      sub='average, project by project', icon='fa-clock-o',
                      model='epc.handover', domain=[('id', 'in', gap_ids)]),
            self._kpi('Verified generation', verified, 'int', 'kWh', sub='measured on commissioning', icon='fa-bolt',
                      model='epc.commissioning', domain=[('generation_verification_kwh', '>', 0)]),
            self._kpi('Certificates uploaded', len(certified), 'int', '/ %s' % total,
                      sub='%s still missing' % (total - len(certified)), icon='fa-certificate',
                      tone='good' if total and len(certified) == total else '', model='epc.commissioning', domain=cert_domain),
        ]

        gates = [
            ('Logged', []),
            ('System testing done', [('system_testing_done', '=', True)]),
            ('Customer walkthrough', [('customer_walkthrough_done', '=', True)]),
            ('Customer approved', [('customer_approved', '=', True)]),
            ('Certificate uploaded', cert_domain),
            ('Manager approved', [('approval_state', '=', 'approved')]),
        ]
        owner_l, owner_c, owner_d = self._group_selection(
            'epc.commissioning.punch', 'owner_id', [('done', '=', False)], empty_label='Unassigned', order='desc')

        age_bands = [('0 - 3 days', 0, 3), ('4 - 7 days', 4, 7), ('8 - 14 days', 8, 14), ('15+ days', 15, None)]
        age_counts, age_domains = [], []
        for _label, low, high in age_bands:
            dom = [('done', '=', False), ('create_date', '<', fields.Datetime.to_string(
                now - timedelta(days=low) if low else now + timedelta(seconds=1)))]
            if high is not None:
                dom.append(('create_date', '>=', fields.Datetime.to_string(now - timedelta(days=high + 1))))
            age_domains.append(dom)
            age_counts.append(Punch.search_count(dom))

        per_project = defaultdict(float)
        for comm in comms:
            if comm.generation_verification_kwh:
                per_project[comm] += comm.generation_verification_kwh
        top = sorted(per_project, key=lambda c: -per_project[c])[:6]
        month = self._count_by_month('epc.commissioning', 'commissioning_date')

        cards = [
            self._card('gates', 'Sign-off steps', 'How many commissionings cleared each step', 'hbar',
                       [g[0] for g in gates],
                       [{'label': 'Commissionings', 'color': 'accent', 'data': [Comm.search_count(g[1]) for g in gates],
                         'domains': [g[1] for g in gates]}],
                       model='epc.commissioning', span=3, source='testing, walkthrough, customer approval, certificate'),
            self._card('generation', 'Verified generation by project', 'kWh measured at commissioning', 'bar',
                       [c.project_id.display_name or c.name for c in top],
                       [{'label': 'kWh', 'color': 'accent', 'data': [round(per_project[c], 1) for c in top],
                         'domains': [[('id', '=', c.id)] for c in top]}],
                       model='epc.commissioning', span=3, source='epc.commissioning · generation_verification_kwh'),
            self._card('owners', 'Open punch items by owner', 'Who has work left to close', 'hbar',
                       owner_l[:8], [{'label': 'Open items', 'color': 'warn', 'data': owner_c[:8], 'domains': owner_d[:8]}],
                       model='epc.commissioning.punch', span=2, source='epc.commissioning.punch · owner_id'),
            self._card('ageing', 'How old open punch items are', 'Days since each item was logged', 'bar',
                       [b[0] for b in age_bands],
                       [{'label': 'Items', 'data': age_counts, 'domains': age_domains,
                         'color': ['pass', 'pass', 'warn', 'fail']}],
                       model='epc.commissioning.punch', span=2, source='epc.commissioning.punch · create_date'),
            self._card('monthly', 'Commissionings per month', 'By commissioning date', 'line',
                       month[0], [{'label': 'Commissionings', 'data': month[1], 'domains': month[2]}],
                       model='epc.commissioning', span=2, source='epc.commissioning · commissioning_date'),
        ]

        def stuck_at(comm):
            if not comm.system_testing_done:
                return 'System testing'
            if not comm.customer_walkthrough_done:
                return 'Customer walkthrough'
            if not comm.customer_approved:
                return 'Customer approval'
            if not comm.commissioning_certificate_filename:
                return 'Certificate upload'
            return 'Manager approval'
        pending = comms.filtered(lambda c: c.approval_state != 'approved').sorted('create_date')[:8]
        rows = []
        for comm in pending:
            punch = comm.open_punch_count
            rows.append({'id': comm.id, 'cells': [
                comm.name, comm.project_id.display_name or '', {'text': stuck_at(comm), 'pill': 'warn'},
                '%s' % (self._days_since(comm.create_date) or 0),
                {'text': '%s' % punch, 'pill': 'bad' if punch else 'good'}]})
        table = self._tbl(
            'Commissionings not signed off yet', 'epc.commissioning',
            [('Commissioning', 'start'), ('Project', 'start'), ('Waiting on', 'start'), ('Days open', 'end'),
             ('Open punch', 'end')],
            rows, source='epc.commissioning · approval_state, sign-off checkboxes',
            empty='Every commissioning is signed off.')

        return {'title': 'Commissioning', 'accent': '#c1b0f2',
                'intro': 'Sign-off progress, punch list clearance and measured generation.',
                'kpis': kpis, 'cards': cards, 'table': table}
