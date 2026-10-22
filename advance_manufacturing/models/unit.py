from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AdvmfgUnit(models.Model):
    """One row per physical unit (panel) being built on a manufacturing order.

    This is the heart of the module: each unit has its own serial number, its own
    current stage, its own quality check, grade, attachments and pallet.
    """
    _name = 'advmfg.unit'
    _description = 'Manufacturing Unit'
    _order = 'production_id, id'
    _rec_name = 'name'

    name = fields.Char(string='Serial Number', required=True, copy=False)
    production_id = fields.Many2one('mrp.production', string='Manufacturing Order', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    product_id = fields.Many2one(related='production_id.product_id', store=True)
    sale_order_id = fields.Many2one('sale.order', related='production_id.procurement_group_id.sale_id', string='Sale Order')
    floor_id = fields.Many2one(related='production_id.advmfg_floor_id', store=True, string='Floor')
    stage_id = fields.Many2one('advmfg.stage', string='Current Stage')
    # Yet To Start -> In Progress -> Completed ; or Cancelled (scrapped).
    state = fields.Selection([
        ('yet_to_start', 'Yet To Start'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancel', 'Cancelled'),
    ], default='yet_to_start', required=True)
    # A = good, B = needs rework (goes back), C = scrapped. Shown after "Update Status".
    grade = fields.Selection([
        ('A', 'Grade A (Quality Pass)'),
        ('B', 'Grade B (Under Maintenance)'),
        ('C', 'Grade C (Scrap)'),
    ])
    # Running line number on the order ("1" for a replacement unit).
    line_no = fields.Char(string='No.')
    # How many stages count as passed so far (a passed parent stage also counts its sub-stages).
    passed_stage_count = fields.Integer(string='Stages Passed', default=0)
    # Scrap records created for this unit by grade B / C.
    scrap_ids = fields.Many2many('stock.scrap', string='Scrap')
    qc_ids = fields.One2many('advmfg.qc', 'unit_id', string='Quality Checks')
    # Screen helpers: which buttons make sense for this unit right now.
    show_next_stage_button = fields.Boolean(compute='_compute_show_buttons')
    show_pass_button = fields.Boolean(compute='_compute_show_buttons')
    # The quality check for the stage the unit is at right now.
    qc_id = fields.Many2one('advmfg.qc', string='Current Quality Check')
    qc_state = fields.Selection(related='qc_id.state', string='Quality Result')
    qc_required = fields.Boolean(related='stage_id.qc_required')
    attachment_required = fields.Boolean(related='stage_id.attachment_required')
    show_grade = fields.Boolean(related='stage_id.show_grade')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    comment = fields.Text()
    pallet_id = fields.Many2one('advmfg.pallet', string='Pallet', copy=False, ondelete='set null')
    # True once the pallet the unit sits on has been confirmed.
    is_packed = fields.Boolean(compute='_compute_is_packed', store=True)
    # Wattage text for the sticker: the product's wattage, or the number in its name ("540W" -> "540 W").
    label_wattage = fields.Char(compute='_compute_label_wattage')
    # Where the unit physically is: on the floor, or in the packed area.
    current_location = fields.Char(compute='_compute_current_location', string='Current Location')

    # ------------------------------------------------------------------ computes
    @api.depends('pallet_id.state')
    def _compute_is_packed(self):
        """A unit counts as 'packed' once its pallet is confirmed."""
        for unit in self:
            unit.is_packed = unit.pallet_id.state == 'confirmed'

    @api.depends('product_id')
    def _compute_label_wattage(self):
        """Text for the wattage tag on the serial sticker (blank when nothing sensible is known)."""
        for unit in self:
            product = unit.product_id
            text = ''
            if product.wattage and product.wattage > 1:
                text = '%d W' % product.wattage
            else:
                for token in (product.product_tmpl_id.name or '').split():
                    if token.upper().endswith('W') and token[:-1].isdigit():
                        text = '%s W' % token[:-1]
                        break
            unit.label_wattage = text

    @api.depends('is_packed', 'floor_id', 'production_id.state', 'company_id.advmfg_packed_location_id')
    def _compute_current_location(self):
        """Show the floor while building, and the packed area once the order is done and packed."""
        for unit in self:
            packed_loc = unit.company_id.advmfg_packed_location_id
            if unit.is_packed and unit.production_id.state == 'done' and packed_loc:
                unit.current_location = packed_loc.display_name
            else:
                unit.current_location = unit.floor_id.name or ''

    @api.depends('state', 'stage_id.qc_required', 'qc_id.state')
    def _compute_show_buttons(self):
        """Decide which buttons to show: Next Stage when ready to move, Pass while the check is still open."""
        for unit in self:
            live = unit.state in ('yet_to_start', 'in_progress')
            qc_open = unit.stage_id.qc_required and unit.qc_id.state == 'todo'
            unit.show_pass_button = bool(live and qc_open)
            if unit.state == 'in_progress':
                unit.show_next_stage_button = True
            elif unit.state == 'yet_to_start':
                unit.show_next_stage_button = bool(unit.stage_id.qc_required and unit.qc_id.state == 'pass')
            else:
                unit.show_next_stage_button = False

    # ------------------------------------------------------------------ safety rules
    @api.constrains('name', 'state', 'company_id')
    def _check_unique_serial(self):
        """Two live units can never share a serial number (cancelled ones are ignored)."""
        for unit in self.filtered(lambda u: u.state != 'cancel'):
            clash = self.search_count([
                ('name', '=', unit.name), ('company_id', '=', unit.company_id.id),
                ('state', '!=', 'cancel'), ('id', '!=', unit.id)])
            if clash:
                raise ValidationError(_('Serial number %s is already used by another unit.', unit.name))

    @api.constrains('pallet_id')
    def _check_pallet_rules(self):
        """Whenever a unit is put on a pallet, re-run the pallet's own rules (finished units only, size limit)."""
        self.mapped('pallet_id')._check_units()

    # ------------------------------------------------------------------ create / write
    @api.model_create_multi
    def create(self, vals_list):
        """New units start at the first real stage; if that stage needs a quality check, create it."""
        Stage = self.env['advmfg.stage']
        counters = {}  # next line number per order, so units created together get 1, 2, 3...
        for vals in vals_list:
            production = self.env['mrp.production'].browse(vals.get('production_id'))
            if vals.get('stage_id'):
                # A sub-stage (or auto-skipped stage) can never be a starting point: move to the first real step.
                stage = Stage.browse(vals['stage_id'])
                if stage.parent_id or stage._is_auto_surpassed():
                    vals['stage_id'] = Stage._first_step(production.company_id, from_stage=stage).id
            else:
                vals['stage_id'] = Stage._first_step(production.company_id).id
            # Running line number on the order.
            if not vals.get('line_no'):
                if production.id not in counters:
                    counters[production.id] = self.search_count([('production_id', '=', production.id)])
                counters[production.id] += 1
                vals['line_no'] = str(counters[production.id])
        units = super().create(vals_list)
        for unit in units:
            unit._create_stage_qc()
        return units

    def write(self, vals):
        """Block moving a unit on/off a confirmed pallet; when the last unit of an order finishes, auto-pass leftover checks."""
        if 'pallet_id' in vals and not self.env.context.get('advmfg_allow_locked_edit'):
            for unit in self:
                if unit.pallet_id.state == 'confirmed':
                    raise UserError(_('Unit %s is on a confirmed pallet and cannot be changed.', unit.name))
        res = super().write(vals)
        if 'grade' in vals and not self.env.context.get('_advmfg_syncing'):
            # Keep any open scan-station window showing the same grade.
            self.env['advmfg.serial.lookup.wizard'].search([('unit_id', 'in', self.ids)]).with_context(
                _advmfg_syncing=True).write({'quality_status': vals['grade']})
        if vals.get('state') in ('completed', 'cancel'):
            for mo in self.mapped('production_id'):
                if mo.advmfg_unit_ids and all(u.state in ('completed', 'cancel') for u in mo.advmfg_unit_ids):
                    # Every unit is finished or scrapped: any check still open is passed automatically.
                    for qc in self.env['advmfg.qc'].search([('production_id', '=', mo.id), ('state', '!=', 'pass')]):
                        try:
                            with self.env.cr.savepoint():
                                qc.state = 'pass'
                        except Exception:  # never block finishing because of a check
                            continue
        return res

    # ------------------------------------------------------------------ stage walking
    def _get_passed_stage_ids(self):
        """Stages already behind this unit: everything earlier in the order, plus sub-stages of passed stages."""
        self.ensure_one()
        Stage = self.env['advmfg.stage']
        if not self.stage_id:
            return set()
        all_stages = Stage.search([('company_id', '=', self.company_id.id)], order='sequence asc, id asc')
        passed = {st.id for st in all_stages if (st.sequence or 0) <= (self.stage_id.sequence or 0)}
        changed = True
        while changed:  # a sub-stage counts as passed once its parent is passed
            changed = False
            for st in all_stages:
                if st.id not in passed and st.parent_id.id in passed:
                    passed.add(st.id)
                    changed = True
        return passed

    def _get_next_unpassed_stage(self):
        """The next top-level stage that has not already been covered by a passed parent."""
        self.ensure_one()
        Stage = self.env['advmfg.stage']
        if not self.stage_id:
            return Stage._first_step(self.company_id)
        passed = self._get_passed_stage_ids()
        return Stage.search([
            ('company_id', '=', self.company_id.id), ('sequence', '>', self.stage_id.sequence or 0),
            ('parent_id', '=', False), ('id', 'not in', list(passed))], order='sequence asc, id asc', limit=1)

    # ------------------------------------------------------------------ helpers
    def _create_stage_qc(self):
        """Create a fresh quality check for the unit's current stage, if that stage asks for one."""
        for unit in self:
            if unit.stage_id.qc_required:
                unit.qc_id = self.env['advmfg.qc'].create({
                    'unit_id': unit.id, 'stage_id': unit.stage_id.id})
            else:
                unit.qc_id = False

    def _enter_stage(self, stage):
        """Move the unit to a stage: clear last grade/result and create the new stage's check."""
        for unit in self:
            unit.write({'stage_id': stage.id, 'grade': False})
            unit._create_stage_qc()

    def _check_can_leave_stage(self):
        """Rules before a unit may leave its stage: the quality check must be passed (no document needed)."""
        self.ensure_one()
        if self.state == 'completed' or self.state == 'cancel':
            raise UserError(_('Unit %s is already %s.', self.name, self.state))
        if self.stage_id.qc_required and self.qc_id.state != 'pass':
            raise UserError(_('Pass the quality check for %(unit)s at stage %(stage)s first.',
                              unit=self.name, stage=self.stage_id.name))

    # ------------------------------------------------------------------ buttons
    def action_pass_qc(self):
        """Pass button on the row: passes the unit's current quality check."""
        for unit in self:
            if not unit.qc_id:
                raise UserError(_('There is no quality check to pass for unit %s.', unit.name))
            unit.qc_id.action_pass()
        return True

    def action_fail_qc(self):
        """Fail button on the row: opens the 'why did it fail' window for the unit's current quality check."""
        self.ensure_one()
        if not self.qc_id:
            raise UserError(_('There is no quality check to fail for unit %s.', self.name))
        return self.qc_id.action_fail()

    def action_start(self):
        """Start button: Yet To Start -> In Progress."""
        for unit in self:
            if unit.state != 'yet_to_start':
                raise UserError(_('Unit %s has already started.', unit.name))
            if not unit.stage_id:
                raise UserError(_('Please set up Process Stages first (Manufacturing > Configuration).'))
            unit.state = 'in_progress'
        return True

    def action_next_stage(self):
        """Next Stage button: move to the next station, or mark the unit Completed if it was the last."""
        for unit in self:
            if unit.state == 'yet_to_start':
                raise UserError(_('Click Start first, then move to the next stage.'))
            unit._check_can_leave_stage()
            next_stage = unit._get_next_unpassed_stage()
            if next_stage:
                unit._enter_stage(next_stage)
            else:
                unit.state = 'completed'
        return True

    def action_update_status(self):
        """Update Status button: opens the window where the grade (A/B/C) is chosen."""
        self.ensure_one()
        if self.state in ('completed', 'cancel'):
            raise UserError(_('Unit %s is already %s.', self.name, self.state))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Update Status'),
            'res_model': 'advmfg.status.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_unit_id': self.id},
        }

    def action_print_label(self):
        """Per-row print icon: barcode label for this one unit."""
        return self.action_print_labels()

    def action_print_labels(self):
        """Print barcode labels for the selected units."""
        return self.env.ref('advance_manufacturing.action_report_advmfg_unit_label').report_action(self)
