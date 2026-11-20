# -*- coding: utf-8 -*-
from odoo import api, fields, models

CONFIRMED = ['sale', 'done']


class EpcStageDashboard(models.AbstractModel):
    _inherit = 'epc.stage.dashboard'

    @api.model
    def _dashboard_dealer(self):
        Lead, Order, Dealer = self.env['crm.lead'], self.env['sale.order'], self.env['epc.dealer']
        today = self._today()
        year = [('create_date', '>=', fields.Date.to_string(today.replace(month=1, day=1)))]
        leads = Lead.search(year)
        via_dealer = leads.filtered('dealer_id')
        dealers = Dealer.search([])
        top_level = dealers.filtered(lambda d: not d.parent_id)
        orders_dom = [('state', 'in', CONFIRMED), ('epc_dealer_id', '!=', False)]
        orders = Order.search(orders_dom)

        # commission: order value x the rate of the dealer on the lead
        commission, order_value, per_dealer = 0.0, 0.0, {}
        for order in orders:
            value = order.amount_untaxed
            rate = order.epc_dealer_id.commission_percent
            order_value += value
            commission += value * rate / 100.0
            stats = per_dealer.setdefault(order.epc_dealer_id.id, {'won': 0, 'value': 0.0, 'commission': 0.0, 'kw': 0.0})
            stats['won'] += 1
            stats['value'] += value
            stats['commission'] += value * rate / 100.0
            stats['kw'] += order.opportunity_id.proposed_capacity_kw

        missing_dom = ['|', ('discom_id', '=', False), ('consumer_number', '=', False)]
        incomplete = leads.filtered(lambda l: not l.discom_id or not l.consumer_number)
        lead_counts = {}
        for dealer, count in Lead._read_group(year + [('dealer_id', '!=', False)], ['dealer_id'], ['__count']):
            lead_counts[dealer.id] = count
        top_id = max(lead_counts, key=lead_counts.get) if lead_counts else None
        top = Dealer.browse(top_id) if top_id else Dealer

        kpis = [
            self._kpi('Active dealers', len(dealers), sub='%s dealer(s) and %s sub-dealer(s)' % (len(top_level), len(dealers) - len(top_level)),
                      icon='fa-users', model='epc.dealer', domain=[]),
            self._kpi('Leads through dealers', self._pct(len(via_dealer), len(leads)), 'pct',
                      sub='of %s lead(s) this year' % len(leads), icon='fa-handshake-o',
                      model='crm.lead', domain=year + [('dealer_id', '!=', False)]),
            self._kpi('Order value via dealers', order_value, 'money', sub='confirmed orders', tone='good', icon='fa-money',
                      model='sale.order', domain=orders_dom),
            self._kpi('Commission payable', commission, 'money', sub='on confirmed orders', tone='warn' if commission else '',
                      icon='fa-percent', model='sale.order', domain=orders_dom),
            self._kpi('Leads with full DISCOM details', self._pct(len(leads) - len(incomplete), len(leads)), 'pct',
                      sub='%s lead(s) miss DISCOM or consumer no.' % len(incomplete), tone='warn' if incomplete else 'good',
                      icon='fa-plug', model='crm.lead', domain=year + missing_dom),
            self._kpi('Top dealer: %s' % (top.complete_name or 'none yet'), lead_counts.get(top_id, 0),
                      sub='lead(s) this year', icon='fa-flag-o', model='crm.lead',
                      domain=year + [('dealer_id', '=', top_id)] if top_id else [('id', '=', 0)]),
        ]

        by_l, by_c, by_d = self._group_selection('crm.lead', 'dealer_id', year + [('dealer_id', '!=', False)], order='desc')
        by_l, by_c, by_d = by_l[:6], by_c[:6], by_d[:6]
        comm_rank = sorted(per_dealer.items(), key=lambda kv: -kv[1]['commission'])[:6]
        comm_l = [Dealer.browse(i).complete_name for i, _s in comm_rank]
        comm_c = [round(s['commission'], 2) for _i, s in comm_rank]
        comm_d = [orders_dom[:1] + [('epc_dealer_id', '=', i)] for i, _s in comm_rank]
        sub_dom = year + [('sub_dealer_id', '!=', False)]
        dealer_only = year + [('dealer_id', '!=', False), ('sub_dealer_id', '=', False)]
        direct_dom = year + [('dealer_id', '=', False)]
        discom_l, discom_c, discom_d = self._group_selection('crm.lead', 'discom_id', year, empty_label='No DISCOM set', order='desc')
        discom_l, discom_c, discom_d = discom_l[:5], discom_c[:5], discom_d[:5]
        months = self._months(6)
        dealer_m, direct_m, dealer_md, direct_md = [], [], [], []
        for _l, start, end in months:
            span = self._range('create_date', start, end)
            dealer_md.append(span + [('dealer_id', '!=', False)])
            direct_md.append(span + [('dealer_id', '=', False)])
            dealer_m.append(Lead.search_count(dealer_md[-1]))
            direct_m.append(Lead.search_count(direct_md[-1]))

        cards = [
            self._card('by_dealer', 'Leads by dealer', 'Top six, this year', 'hbar', by_l,
                       [{'label': 'Leads', 'data': by_c, 'domains': by_d}],
                       model='crm.lead', span=3, source='crm.lead · dealer_id'),
            self._card('commission', 'Commission payable by dealer', 'Confirmed orders, top six', 'bar', comm_l,
                       [{'label': 'Commission', 'color': 'warn', 'data': comm_c, 'domains': comm_d}],
                       model='sale.order', span=3, source='epc.dealer · commission_percent x sale.order amount'),
            self._card('source', 'Where leads come from', 'Dealer, sub-dealer or direct', 'doughnut',
                       ['Dealer', 'Sub-dealer', 'Direct'],
                       [{'label': 'Leads', 'color': ['accent', 'neutral', 'warn'],
                         'data': [Lead.search_count(dealer_only), Lead.search_count(sub_dom), Lead.search_count(direct_dom)],
                         'domains': [dealer_only, sub_dom, direct_dom]}],
                       model='crm.lead', span=2, source='crm.lead · dealer_id, sub_dealer_id'),
            self._card('discom', 'Leads by DISCOM', 'Top five boards, this year', 'hbar', discom_l,
                       [{'label': 'Leads', 'data': discom_c, 'domains': discom_d}],
                       model='crm.lead', span=2, source='crm.lead · discom_id'),
            self._card('monthly', 'Leads per month', 'Through dealers against direct', 'bar', [m[0] for m in months],
                       [{'label': 'Through dealers', 'data': dealer_m, 'domains': dealer_md},
                        {'label': 'Direct', 'data': direct_m, 'domains': direct_md}],
                       model='crm.lead', span=2, source='crm.lead · create_date, dealer_id'),
        ]
        self._axis_titles(cards, {'by_dealer': ('Number of leads', 'Dealer'), 'commission': ('Dealer', 'Commission'),
                                  'discom': ('Number of leads', 'DISCOM'), 'monthly': ('Month', 'Leads')})

        rows = []
        for dealer_id in sorted(lead_counts, key=lambda i: -lead_counts[i])[:8]:
            dealer = Dealer.browse(dealer_id)
            stats = per_dealer.get(dealer_id, {'won': 0, 'value': 0.0, 'commission': 0.0, 'kw': 0.0})
            leads_n = lead_counts[dealer_id]
            rows.append({'id': dealer_id, 'cells': [
                dealer.complete_name, str(len(dealer.child_ids)), str(leads_n), str(stats['won']),
                '%s%%' % round(self._pct(stats['won'], leads_n)), '%.0f' % stats['kw'],
                self._money_text(stats['value']), self._money_text(stats['commission'])]})
        table = self._tbl(
            'Dealer leaderboard', 'epc.dealer',
            [('Dealer', 'start'), ('Sub-dealers', 'end'), ('Leads', 'end'), ('Won', 'end'), ('Win rate', 'end'),
             ('kW sold', 'end'), ('Order value', 'end'), ('Commission', 'end')],
            rows, source='crm.lead + sale.order · dealer_id', empty='No dealer has brought a lead this year.')

        return {'title': 'Dealers & DISCOM', 'accent': '#c8a0fa',
                'intro': 'Which dealers bring the leads, what they earn, and where lead details are still incomplete.',
                'kpis': kpis, 'cards': cards, 'table': table}
