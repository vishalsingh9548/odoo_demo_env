# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError

# The stages shown on the Pipeline Activity chart, each paired with the model
# and domain that counts as "still open" for that stage — i.e. work someone
# still needs to act on, not everything that was ever created.
_PIPELINE_STAGES = [
    ('epc.site.survey', 'Site Surveys', [('approval_state', 'in', ('to_submit', 'submitted'))]),
    ('epc.feasibility', 'Feasibility Studies', [('approval_state', 'in', ('to_submit', 'submitted'))]),
    ('epc.boq', 'BOQs Pending Approval', [('approval_state', 'in', ('to_submit', 'submitted'))]),
    ('epc.material.request', 'Material Requests', [('approval_state', 'in', ('to_submit', 'submitted'))]),
    ('epc.quality.check', 'Quality Checks Pending', [('overall_result', '=', 'pending')]),
]

# Every Purchase Order status shown on the Procurement Status chart, in the
# order the RFQ-to-PO process actually moves through
_PURCHASE_STATES = [
    ('draft', 'RFQ'),
    ('sent', 'RFQ Sent'),
    ('to approve', 'To Approve'),
    ('purchase', 'Purchase Order'),
    ('done', 'Locked'),
]

# Every AMC contract status shown on the AMC Contract Health chart
_AMC_STATES = [
    ('draft', 'Draft'),
    ('active', 'Active'),
    ('expired', 'Expired'),
    ('terminated', 'Terminated'),
]


class EpcDashboard(models.AbstractModel):
    """The data backend for the 'Solar EPC Dashboard' screen (see the matching
    OWL component in static/src/js/epc_dashboard.js). This model has no
    database table of its own (it's an AbstractModel) — its only job is to
    gather live numbers from the real EPC records and hand them to the
    dashboard as one JSON-friendly package, one method call at a time,
    so the dashboard always shows what's true right now, never a stale copy.

    Every number handed back is paired with the exact Odoo search domain that
    produced it, so a click on a tile or chart bar opens a list of exactly
    those records — the count on screen and the list that opens always match.
    """
    _name = 'epc.dashboard'
    _description = 'Solar EPC Dashboard'

    # Gathers every number the dashboard screen needs in one go, so the
    # frontend only has to make a single request when it opens
    @api.model
    def get_dashboard_data(self):
        # The dashboard summarises records across many different EPC models
        # (surveys, BOQs, material requests, quality checks, AMC contracts...),
        # some of which a plain Field User only has partial access to by
        # design (e.g. read-only on AMC contracts). Rather than widen every
        # individual model's access rules just so aggregate counts can be
        # read, this checks once that the caller is genuinely an EPC app user
        # (the same check the dashboard's menu item already uses to decide
        # whether to even show the link), then reads everything as an
        # aggregate summary — no individual record's sensitive detail is
        # exposed by a count or a sum.
        if not self.env.user.has_group('csl_solar_epc.group_epc_user'):
            raise AccessError("You need Solar EPC access to view this dashboard.")
        self = self.sudo()

        project_model = self.env['project.project']
        currency_id = self.env.company.currency_id.id

        return {
            'currency_id': currency_id,
            'kpis': self._get_kpis(project_model),
            'portfolio_phase': self._get_portfolio_phase(project_model),
            'pipeline_activity': self._get_pipeline_activity(),
            'amc_contract_health': self._get_amc_contract_health(),
            'procurement_status': self._get_procurement_status(),
            'upcoming_amc_services': self._get_upcoming_amc_services(),
        }

    # The 7 headline numbers across the top of the dashboard: how many
    # projects are running, how much they're worth, and how much work is
    # still waiting on someone's approval or attention right now
    def _get_kpis(self, project_model):
        all_projects_domain = [('boq_id', '!=', False)]
        handed_over_project_ids = self.env['epc.handover'].search(
            [('approval_state', '=', 'approved')]).mapped('project_id').ids
        active_projects_domain = all_projects_domain + [('id', 'not in', handed_over_project_ids)]
        active_projects = project_model.search(active_projects_domain)
        all_projects = project_model.search(all_projects_domain)

        material_request_domain = [('approval_state', 'in', ('to_submit', 'submitted'))]
        quality_check_domain = [('overall_result', 'in', ('pending', 'fail'))]
        amc_active_domain = [('state', '=', 'active')]
        open_ticket_domain = [('amc_contract_id', '!=', False), ('close_date', '=', False)]

        completed_projects_domain = [('id', 'in', handed_over_project_ids)]

        return {
            'active_projects': {'count': len(active_projects), 'domain': active_projects_domain},
            'contract_value': {'value': sum(all_projects.mapped('boq_total_sell_price'))},
            'completed_projects': {'count': len(handed_over_project_ids), 'domain': completed_projects_domain},
            'pending_material_requests': {
                'count': self.env['epc.material.request'].search_count(material_request_domain),
                'domain': material_request_domain,
            },
            'pending_quality_checks': {
                'count': self.env['epc.quality.check'].search_count(quality_check_domain),
                'domain': quality_check_domain,
            },
            'active_amc_contracts': {
                'count': self.env['epc.amc.contract'].search_count(amc_active_domain),
                'domain': amc_active_domain,
            },
            'open_tickets': {
                'count': self.env['helpdesk.ticket'].search_count(open_ticket_domain),
                'domain': open_ticket_domain,
            },
        }

    # Buckets every EPC project into one plain-language phase — Execution,
    # Commissioned, Handed Over, or Under AMC — based on which milestone
    # documents it already has, so a manager can see the whole portfolio's
    # spread across the pipeline at a glance
    def _get_portfolio_phase(self, project_model):
        projects = project_model.search([('boq_id', '!=', False)])
        commissioned_ids = set(self.env['epc.commissioning'].search(
            [('approval_state', '=', 'approved')]).mapped('project_id').ids)
        handed_over_ids = set(self.env['epc.handover'].search(
            [('approval_state', '=', 'approved')]).mapped('project_id').ids)
        amc_active_ids = set(self.env['epc.amc.contract'].search(
            [('state', '=', 'active')]).mapped('project_id').ids)

        buckets = {
            'execution': {'label': 'Execution', 'ids': []},
            'commissioned': {'label': 'Commissioned', 'ids': []},
            'handed_over': {'label': 'Handed Over', 'ids': []},
            'amc': {'label': 'Under AMC', 'ids': []},
        }
        for project in projects:
            if project.id in amc_active_ids:
                buckets['amc']['ids'].append(project.id)
            elif project.id in handed_over_ids:
                buckets['handed_over']['ids'].append(project.id)
            elif project.id in commissioned_ids:
                buckets['commissioned']['ids'].append(project.id)
            else:
                buckets['execution']['ids'].append(project.id)

        return {
            'labels': [b['label'] for b in buckets.values()],
            'counts': [len(b['ids']) for b in buckets.values()],
            'domains': [[('id', 'in', b['ids'])] for b in buckets.values()],
        }

    # How much open, not-yet-cleared work is sitting at each stage of the
    # pipeline right now — an operational "what needs attention" view, not
    # a financial one, so a bottleneck (e.g. a pile of unapproved BOQs)
    # stands out immediately
    def _get_pipeline_activity(self):
        counts, domains, labels = [], [], []
        for model_name, label, domain in _PIPELINE_STAGES:
            labels.append(label)
            counts.append(self.env[model_name].search_count(domain))
            domains.append({'model': model_name, 'domain': domain})
        return {'labels': labels, 'counts': counts, 'domains': domains}

    # Every AMC contract, grouped by its own status, so the health of the
    # whole maintenance book is visible without opening the list
    def _get_amc_contract_health(self):
        groups = {state: 0 for state, _label in _AMC_STATES}
        for group in self.env['epc.amc.contract'].read_group([], ['state'], ['state'], lazy=False):
            if group['state'] in groups:
                groups[group['state']] = group['__count']
        return {
            'labels': [label for _state, label in _AMC_STATES],
            'counts': [groups[state] for state, _label in _AMC_STATES],
            'domains': [[('state', '=', state)] for state, _label in _AMC_STATES],
        }

    # Every Purchase Order raised for a project, grouped by its stage in the
    # RFQ-to-PO process — a status/process view, deliberately not a spend
    # figure, so it answers "what's stuck" rather than "how much did we buy"
    def _get_procurement_status(self):
        groups = {state: 0 for state, _label in _PURCHASE_STATES}
        for group in self.env['purchase.order'].read_group(
                [('project_id', '!=', False)], ['state'], ['state'], lazy=False):
            if group['state'] in groups:
                groups[group['state']] = group['__count']
        return {
            'labels': [label for _state, label in _PURCHASE_STATES],
            'counts': [groups[state] for state, _label in _PURCHASE_STATES],
            'domains': [[('project_id', '!=', False), ('state', '=', state)] for state, _label in _PURCHASE_STATES],
        }

    # The next 8 preventive-maintenance visits coming due across every active
    # AMC contract, so nothing gets missed
    def _get_upcoming_amc_services(self):
        today = fields.Date.context_today(self)
        contracts = self.env['epc.amc.contract'].search(
            [('state', '=', 'active'), ('next_service_date', '!=', False)],
            order='next_service_date', limit=8,
        )
        return [{
            'id': contract.id,
            'name': contract.name,
            'project': contract.project_id.display_name,
            'next_service_date': contract.next_service_date and contract.next_service_date.isoformat(),
            'days_until': (contract.next_service_date - today).days,
        } for contract in contracts]
