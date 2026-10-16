from datetime import date

from odoo import _, api, fields, models

from odoo.addons.ug_epr.models.ug_epr_certificate import indian_financial_year

STAGE_CARDS = ('dismantle', 'shred', 'recover')
OPEN_STATES = ('confirmed', 'progress', 'to_close')


class UgRecyclingOverview(models.Model):
    """ Cards of the Recycling > Overview dashboard (one record per card). """
    _name = 'ug.recycling.overview'
    _description = 'Recycling Overview Card'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    card_type = fields.Selection([
        ('dismantle', 'Dismantle'),
        ('shred', 'Shred'),
        ('recover', 'Recover'),
        ('lab', 'Lab'),
        ('epr', 'EPR'),
    ], required=True)
    description = fields.Char(translate=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_metrics')

    # stage cards
    queue_count = fields.Integer(compute='_compute_metrics')
    queue_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    waiting_lab_count = fields.Integer(compute='_compute_metrics')
    mo_draft_count = fields.Integer(compute='_compute_metrics')
    mo_open_count = fields.Integer(compute='_compute_metrics')
    mo_late_count = fields.Integer(compute='_compute_metrics')
    loss_alert_count = fields.Integer(compute='_compute_metrics')
    month_input_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    month_output_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    month_loss_pct = fields.Float(compute='_compute_metrics', digits=(16, 1))
    month_recovered_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    month_efficiency_pct = fields.Float(compute='_compute_metrics', digits=(16, 1))
    # lab card
    assay_submitted_count = fields.Integer(compute='_compute_metrics')
    assay_draft_count = fields.Integer(compute='_compute_metrics')
    lot_pending_count = fields.Integer(compute='_compute_metrics')
    assay_month_approved_count = fields.Integer(compute='_compute_metrics')
    # EPR card
    epr_available_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    epr_draft_count = fields.Integer(compute='_compute_metrics')
    epr_listed_count = fields.Integer(compute='_compute_metrics')
    epr_fy_sold_kg = fields.Float(compute='_compute_metrics', digits=(16, 0))
    epr_fy_sold_amount = fields.Monetary(compute='_compute_metrics')
    financial_year = fields.Char(compute='_compute_metrics')

    # ------------------------------------------------------------------
    # Domains
    # ------------------------------------------------------------------
    def _companies(self):
        return self.env.companies.ids

    def _month_start(self):
        return fields.Datetime.to_datetime(date.today().replace(day=1))

    def _mo_domain(self, view=None):
        self.ensure_one()
        domain = [('ug_is_recycling', '=', True), ('ug_stage', '=', self.card_type),
                  ('company_id', 'in', self._companies())]
        if view == 'draft':
            domain.append(('state', '=', 'draft'))
        elif view == 'open':
            domain.append(('state', 'in', OPEN_STATES))
        elif view == 'late':
            domain += [('state', 'in', OPEN_STATES), ('date_finished', '<', fields.Datetime.now())]
        elif view == 'loss':
            domain += [('state', '=', 'done'), ('ug_loss_exceeded', '=', True),
                       ('date_finished', '>=', self._month_start())]
        elif view == 'month':
            domain += [('state', '=', 'done'), ('date_finished', '>=', self._month_start())]
        return domain

    def _queue_domain(self, ready=True):
        self.ensure_one()
        return [('stage', '=', self.card_type), ('ready', '=', ready), ('company_id', 'in', self._companies())]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    @api.depends_context('allowed_company_ids')
    def _compute_metrics(self):
        self.env.flush_all()  # the queue is an SQL view
        Production = self.env['mrp.production']
        Queue = self.env['ug.process.queue']
        Assay = self.env['ug.lot.assay']
        Certificate = self.env['ug.epr.certificate']
        companies = self._companies()
        month_start = self._month_start()
        fy = indian_financial_year(date.today())
        for card in self:
            values = dict.fromkeys([
                'queue_count', 'queue_kg', 'waiting_lab_count', 'mo_draft_count', 'mo_open_count',
                'mo_late_count', 'loss_alert_count', 'month_input_kg', 'month_output_kg', 'month_loss_pct',
                'month_recovered_kg', 'month_efficiency_pct', 'assay_submitted_count', 'assay_draft_count',
                'lot_pending_count', 'assay_month_approved_count', 'epr_available_kg', 'epr_draft_count',
                'epr_listed_count', 'epr_fy_sold_kg', 'epr_fy_sold_amount'], 0)
            values.update(currency_id=self.env.company.currency_id, financial_year=fy)

            if card.card_type in STAGE_CARDS:
                queue = Queue.search(card._queue_domain())
                values.update(
                    queue_count=len(queue),
                    queue_kg=sum(queue.mapped('available_kg')),
                    waiting_lab_count=Queue.search_count(card._queue_domain(ready=False)),
                    mo_draft_count=Production.search_count(card._mo_domain('draft')),
                    mo_open_count=Production.search_count(card._mo_domain('open')),
                    mo_late_count=Production.search_count(card._mo_domain('late')),
                    loss_alert_count=Production.search_count(card._mo_domain('loss')),
                )
                done = Production.search(card._mo_domain('month'))
                input_kg = sum(done.mapped('ug_input_weight_kg'))
                output_kg = sum(done.mapped('ug_output_weight_kg'))
                values.update(
                    month_input_kg=input_kg,
                    month_output_kg=output_kg,
                    month_loss_pct=input_kg and (input_kg - output_kg) / input_kg * 100 or 0.0,
                )
                if card.card_type == 'recover':
                    lines = done.ug_recovery_line_ids
                    contained = sum(lines.mapped('contained_kg'))
                    recovered = done.move_finished_ids.filtered(
                        lambda m: m.state == 'done' and m.product_id.ug_material_type == 'recovered_material')
                    values.update(
                        month_recovered_kg=Production._ug_moves_kg(recovered),
                        month_efficiency_pct=contained and sum(lines.mapped('actual_metal_kg')) / contained * 100 or 0.0,
                    )

            elif card.card_type == 'lab':
                company_domain = [('company_id', 'in', companies)]
                values.update(
                    assay_submitted_count=Assay.search_count(company_domain + [('state', '=', 'submitted')]),
                    assay_draft_count=Assay.search_count(company_domain + [('state', '=', 'draft')]),
                    lot_pending_count=self.env['stock.lot'].search_count(
                        [('ug_assay_state', '=', 'pending'), ('product_qty', '>', 0),
                         '|', ('company_id', '=', False), ('company_id', 'in', companies)]),
                    assay_month_approved_count=Assay.search_count(
                        company_domain + [('state', '=', 'approved'), ('approved_date', '>=', month_start)]),
                )

            elif card.card_type == 'epr':
                available = Production.search([('ug_epr_available_kg', '>', 0), ('state', '=', 'done'),
                                                ('company_id', 'in', companies)])
                sold = Certificate.search([('company_id', 'in', companies), ('financial_year', '=', fy),
                                           ('state', 'in', ('sold', 'transferred'))])
                values.update(
                    epr_available_kg=sum(available.mapped('ug_epr_available_kg')),
                    epr_draft_count=Certificate.search_count([('company_id', 'in', companies), ('state', '=', 'draft')]),
                    epr_listed_count=Certificate.search_count([('company_id', 'in', companies),
                                                               ('state', 'in', ('generated', 'listed'))]),
                    epr_fy_sold_kg=sum(sold.mapped('quantity_kg')),
                    epr_fy_sold_amount=sum(sold.mapped('amount')),
                )
            card.update(values)

    # ------------------------------------------------------------------
    # Card actions (the clicked view is passed in the context as 'ug_view')
    # ------------------------------------------------------------------
    def action_open(self):
        self.ensure_one()
        view = self.env.context.get('ug_view')
        if self.card_type in STAGE_CARDS:
            if view in ('queue', 'waiting_lab'):
                action = self.env['ir.actions.act_window']._for_xml_id('ug_recovery_planning.ug_process_queue_action')
                action['domain'] = self._queue_domain(ready=view == 'queue')
                action['context'] = {'search_default_groupby_chemistry': 1}
                action['name'] = _("%(stage)s – To Process", stage=self.name)
                return action
            action = self.env['ir.actions.act_window']._for_xml_id('ug_recycling_base.ug_mrp_production_action')
            action['domain'] = self._mo_domain(view)
            action['context'] = {'create': view in (None, 'draft')}
            action['name'] = _("%(stage)s Orders", stage=self.name)
            return action
        if self.card_type == 'lab':
            if view == 'lots':
                action = self.env['ir.actions.act_window']._for_xml_id('stock.action_production_lot_form')
                action['domain'] = [('ug_assay_state', '=', 'pending'), ('product_qty', '>', 0)]
                action['context'] = {}
                action['name'] = _("Lots Pending Assay")
                return action
            action = self.env['ir.actions.act_window']._for_xml_id('ug_lot_assay.ug_lot_assay_action')
            state = {'draft': 'draft', 'approved': 'approved'}.get(view, 'submitted')
            action['domain'] = [('state', '=', state)]
            action['context'] = {'create': False}
            return action
        # EPR
        if view == 'available':
            action = self.env['ir.actions.act_window']._for_xml_id('ug_recycling_base.ug_mrp_production_action')
            action['domain'] = [('ug_epr_available_kg', '>', 0), ('state', '=', 'done')]
            action['context'] = {'create': False}
            action['name'] = _("Orders with EPR to Claim")
            return action
        action = self.env['ir.actions.act_window']._for_xml_id('ug_epr.ug_epr_certificate_action')
        states = {'draft': ['draft'], 'listed': ['generated', 'listed'], 'sold': ['sold', 'transferred']}.get(view)
        if states:
            action['domain'] = [('state', 'in', states)]
        return action
