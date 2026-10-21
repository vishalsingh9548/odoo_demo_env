# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class EpcStageDashboard(models.AbstractModel):
    """Shared backend of the per-stage dashboards (Site Survey, Feasibility,
    BOQ, Material Request, Quality, Commissioning, Handover, AMC).

    Every stage module extends this model with one method named
    `_dashboard_<stage>` that returns the numbers for its own screen, built
    with the small helpers below. The one generic screen in core (the
    `epc_stage_dashboard` client action) renders whatever comes back, so a
    stage module never ships its own JavaScript.

    Numbers are read with the logged-in user's own access rights (not sudo),
    so a click on a tile or bar opens a list holding exactly the records that
    were counted, including for Field Users who only see their own records.
    """
    _name = 'epc.stage.dashboard'
    _description = 'Solar EPC Stage Dashboard'

    @api.model
    def get_data(self, stage):
        if not self.env.user.has_group('csl_epc_core.group_epc_user'):
            raise AccessError("You need Solar EPC access to view this dashboard.")
        builder = getattr(self, '_dashboard_%s' % stage, None)
        if not builder:
            raise UserError("No dashboard is installed for '%s'." % stage)
        data = builder()
        data['stage'] = stage
        data['currency_id'] = self.env.company.currency_id.id
        data['generated_at'] = fields.Datetime.to_string(fields.Datetime.now())
        data['cards'] = [card for card in data.get('cards', []) if card]
        return data

    # ------------------------------------------------------------------
    # Builders for the pieces of the payload
    # ------------------------------------------------------------------
    @api.model
    def _kpi(self, label, value, fmt='int', unit='', sub='', trend='', tone='',
             icon='fa-sun-o', model=None, domain=None, source=''):
        """One tile. `fmt` is how the screen prints `value`: int, dec, pct or
        money. `tone` colours the left edge (good, warn, bad or empty).
        `trend` colours the sub-line (up = good, down = bad)."""
        return {
            'label': label, 'value': value, 'fmt': fmt, 'unit': unit, 'sub': sub,
            'trend': trend, 'tone': tone, 'icon': icon, 'source': source,
            'model': model, 'domain': domain,
        }

    @api.model
    def _card(self, key, title, sub, kind, labels, datasets, model=None, span=2,
              source='', **extra):
        """One chart. `kind` is bar, hbar, line, doughnut or scatter.
        Each dataset is {label, data, color, domains}; `color` is a name
        (pass, fail, warn, accent, neutral...), a hex, or a list per bar.
        `domains[i]` is what opens when point i is clicked."""
        card = {'key': key, 'title': title, 'sub': sub, 'kind': kind, 'labels': labels,
                'datasets': datasets, 'model': model, 'span': span, 'source': source}
        card.update(extra)
        return card

    @api.model
    def _axis_titles(self, cards, titles):
        """Adds the axis headings to charts: `titles` maps a card key to
        (bottom axis, left axis). Pie charts have no axes and are left alone."""
        for card in cards:
            if card and card['key'] in titles:
                card['xlabel'], card['ylabel'] = titles[card['key']]
        return cards

    @api.model
    def _tbl(self, title, model, cols, rows, source='', empty='Nothing to show right now.'):
        """`cols` = [(label, 'start'|'end')], each row = {'id': record id,
        'cells': [text | {'text':..., 'pill': good|warn|bad|neutral}]}."""
        return {'title': title, 'model': model, 'source': source, 'empty': empty,
                'cols': [{'label': c[0], 'align': c[1]} for c in cols], 'rows': rows}

    @api.model
    def _safe(self, builder, *args, **kwargs):
        """A section the user has no access to is left out instead of
        breaking the whole dashboard."""
        try:
            return builder(*args, **kwargs)
        except AccessError:
            return None

    # ------------------------------------------------------------------
    # Small helpers shared by every stage
    # ------------------------------------------------------------------
    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _months(self, count=6):
        """The last `count` calendar months, oldest first: (label, first day,
        first day of the next month)."""
        first = self._today().replace(day=1)
        out = []
        for back in range(count - 1, -1, -1):
            start = first - relativedelta(months=back)
            out.append((start.strftime('%b'), start, start + relativedelta(months=1)))
        return out

    @api.model
    def _range(self, field, start, end):
        return [(field, '>=', fields.Date.to_string(start)), (field, '<', fields.Date.to_string(end))]

    @api.model
    def _count_by_month(self, model, date_field, domain=None, count=6):
        labels, counts, domains = [], [], []
        for label, start, end in self._months(count):
            dom = list(domain or []) + self._range(date_field, start, end)
            labels.append(label)
            counts.append(self.env[model].search_count(dom))
            domains.append(dom)
        return labels, counts, domains

    @api.model
    def _group_selection(self, model, field, domain=None, empty_label=None, order=None):
        """Counts per value of a selection / many2one field.
        Returns (labels, counts, domains)."""
        Model = self.env[model]
        domain = list(domain or [])
        selection = dict(Model._fields[field].selection) if Model._fields[field].type == 'selection' else None
        rows = Model._read_group(domain, [field], ['__count'])
        found = {}
        for value, count in rows:
            if selection is not None:
                key = value or False
            else:
                key = value.id if value else False
            found[key] = count
        labels, counts, domains = [], [], []
        if selection is not None:
            keys = [k for k, _ in Model._fields[field].selection if k in found]
        else:
            keys = sorted((k for k in found if k), key=lambda k: -found[k])
        if False in found:
            keys.append(False)
        for key in keys:
            if key is False:
                label = empty_label or 'Not set'
            elif selection is not None:
                label = selection[key]
            else:
                label = Model.env[Model._fields[field].comodel_name].browse(key).display_name
            labels.append(label)
            counts.append(found[key])
            domains.append(domain + [(field, '=', key)])
        if order == 'desc':
            order_idx = sorted(range(len(counts)), key=lambda i: -counts[i])
            labels = [labels[i] for i in order_idx]
            counts = [counts[i] for i in order_idx]
            domains = [domains[i] for i in order_idx]
        return labels, counts, domains

    @api.model
    def _days_since(self, value):
        """Whole days between a date or datetime and today (None if empty)."""
        if not value:
            return None
        if hasattr(value, 'date'):
            value = value.date()
        return (self._today() - value).days

    @api.model
    def _pct(self, part, whole):
        return round(part * 100.0 / whole, 1) if whole else 0.0

    @api.model
    def _short_date(self, value):
        return value.strftime('%d %b %Y') if value else ''

    @api.model
    def _approval_turnaround_days(self, records):
        """Average days between 'submitted' and 'approved' over approved records."""
        spans = [(r.approved_date - r.submitted_date).total_seconds() / 86400.0
                 for r in records if r.approved_date and r.submitted_date]
        return round(sum(spans) / len(spans), 1) if spans else 0.0

    @api.model
    def _delta_text(self, now, before, word):
        diff = now - before
        if not diff:
            return ('same as %s' % word, '')
        return ('%s%s vs %s' % ('+' if diff > 0 else '-', abs(diff), word), 'up' if diff > 0 else 'down')

    @api.model
    def _money_text(self, value):
        currency = self.env.company.currency_id
        text = '{:,.0f}'.format(value or 0)
        return '%s%s' % (currency.symbol, text) if currency.position == 'before' else '%s %s' % (text, currency.symbol)

    @api.model
    def _energy(self, kwh):
        """Scale kWh into a readable (value, unit) pair."""
        if kwh >= 1000000:
            return round(kwh / 1000000.0, 2), 'GWh'
        if kwh >= 1000:
            return round(kwh / 1000.0, 1), 'MWh'
        return round(kwh, 1), 'kWh'

    @api.model
    def _power(self, kw):
        """Scale kW into a readable (value, unit) pair."""
        if kw >= 1000:
            return round(kw / 1000.0, 2), 'MWp'
        return round(kw, 1), 'kWp'
