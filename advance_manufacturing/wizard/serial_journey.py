from markupsafe import Markup

from odoo import api, fields, models, _

GREEN, BLUE, AMBER, GRAY, RED = '#178A62', '#2F7FD1', '#C77A12', '#9AA8B7', '#C0392B'
OK_TXT, MUTED, WAIT_TXT, INK = '#116A47', '#5B6776', '#8A5300', '#1F2A37'


class AdvmfgSerialJourney(models.TransientModel):
    """The live 'Serial Journey' screen: everything about one serial number, read fresh every time it opens.

    Nothing is copied or stored: each time the screen is opened or refreshed it looks at the unit, its
    quality checks, pallet, pack and delivery as they are right now.
    """
    _name = 'advmfg.serial.journey'
    _description = 'Serial Journey'

    unit_id = fields.Many2one('advmfg.unit', required=True)
    serial_no = fields.Char(related='unit_id.name')
    journey_html = fields.Html(compute='_compute_journey_html', sanitize=False)
    can_update = fields.Boolean(compute='_compute_can_update')

    @api.depends('unit_id.state')
    def _compute_can_update(self):
        """Update Status is only offered while the unit is still being made."""
        for rec in self:
            rec.can_update = rec.unit_id.state in ('yet_to_start', 'in_progress')

    def _compute_journey_html(self):
        """Draw the whole screen from the live data."""
        for rec in self:
            values = rec._journey_values()
            rec.journey_html = Markup(self.env['ir.qweb']._render('advance_manufacturing.journey_card', values))

    # ------------------------------------------------------------------ buttons
    def action_refresh(self):
        """Refresh: show the same screen again with the latest data."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new', 'name': _('Serial Journey: %s', self.unit_id.name)}

    def action_update_status(self):
        """Open the Update Status window (stage move, grade, QC) for a unit still being made."""
        self.ensure_one()
        wizard_id = self.env['advmfg.scan.wizard'].create_and_return_lookup_wizard(self.unit_id.name)
        return {'type': 'ir.actions.act_window', 'res_model': 'advmfg.serial.lookup.wizard', 'res_id': wizard_id,
                'view_mode': 'form', 'target': 'new', 'name': _('Serial Details: %s', self.unit_id.name)}

    def action_print(self):
        """Print the journey as a PDF."""
        self.ensure_one()
        return self.env.ref('advance_manufacturing.action_report_advmfg_journey').report_action(self)

    # ------------------------------------------------------------------ data
    def _fmt(self, dt):
        """A date/time in the user's time zone, short form; blank when unknown."""
        if not dt:
            return ''
        return fields.Datetime.context_timestamp(self, dt).strftime('%d %b %Y, %H:%M')

    def _journey_values(self):
        """Collect every fact about the unit (stage, quality, pallet, pack, delivery, history)."""
        self.ensure_one()
        unit = self.unit_id.sudo()
        mo = unit.production_id
        so = unit.sale_order_id or (self.env['sale.order'].sudo().search([('name', '=', mo.origin)], limit=1) if mo.origin else False)
        pool = self.env['advmfg.serial'].sudo().search([('name', '=', unit.name), ('production_id', '=', mo.id)], limit=1)
        pallet = unit.pallet_id
        packs = self.env['advmfg.delivery.pack'].sudo().search([('pallet_ids', 'in', pallet.ids)]) if pallet else self.env['advmfg.delivery.pack']
        pack = packs[:1]
        picking = pack.picking_id
        qcs = unit.qc_ids.sorted('id')
        delivered = bool(picking and picking.state == 'done')
        qc_pass = len(qcs.filtered(lambda q: q.state == 'pass'))
        qc_fail = len(qcs.filtered(lambda q: q.state == 'fail'))
        pending = qcs.filtered(lambda q: q.state == 'todo')

        # --- headline chips and tiles
        if unit.state == 'cancel':
            status, where, status_sub = _('Scrapped'), _('Scrapped (Grade C)'), _('This unit was cancelled')
        elif delivered:
            status, where, status_sub = _('Delivered'), _('At the customer'), self._fmt(picking.advmfg_delivered_on or picking.date_done)
        elif unit.state == 'completed':
            status = _('Completed')
            where = _('On %s', pallet.name) if pallet else _('Finished, waiting for a pallet')
            status_sub = _('Packed in %s', pack.name) if pack else _('Ready for packing')
        else:
            status = _('In progress') if unit.state == 'in_progress' else _('Yet to start')
            where = _('%s station', unit.stage_id.name or '-')
            status_sub = unit.floor_id.name or ''
        chips = [{'label': status, 'bg': '#E8F6EF' if unit.state == 'completed' else '#E6F0FB', 'fg': OK_TXT if unit.state == 'completed' else '#1D5FA8'}]
        if unit.state == 'cancel':
            chips[0].update(bg='#FDECEA', fg=RED)
        if pending and unit.state not in ('cancel', 'completed'):
            chips.append({'label': _('QC pending at %s', pending[-1].stage_id.name), 'bg': '#FFF3DF', 'fg': WAIT_TXT})
        elif qc_fail and not qc_pass:
            chips.append({'label': _('Quality check failed'), 'bg': '#FDECEA', 'fg': RED})
        elif qcs:
            chips.append({'label': _('Quality: %s of %s checks passed', qc_pass, len(qcs)), 'bg': '#E8F6EF', 'fg': OK_TXT})
        chips.append({'label': _('Grade %s', unit.grade) if unit.grade else _('Not graded yet'),
                      'bg': '#E6F0FB' if unit.grade else '#EEF3F8', 'fg': '#1D5FA8' if unit.grade else MUTED})
        if pallet:
            chips.append({'label': ('%s' % pallet.name) + (' · %s' % pack.name if pack else ''), 'bg': '#FFF3DF', 'fg': WAIT_TXT})
        else:
            chips.append({'label': _('Not on a pallet'), 'bg': '#EEF3F8', 'fg': MUTED})
        facts = [
            {'k': _('Where is it now'), 'v': where, 's': unit.floor_id.name or ''},
            {'k': _('Current status'), 'v': status, 's': status_sub},
            {'k': _('Quality result'), 'v': _('%s of %s passed', qc_pass, len(qcs)) if qcs else _('No checks'),
             's': (_('%s check(s) failed', qc_fail) if qc_fail else (_('%s check is pending', pending[-1].stage_id.name) if pending else _('No failed checks')))},
            {'k': _('Grade'), 'v': unit.grade or _('Not yet'), 's': '' if unit.grade else _('Given after the last stage')},
        ]

        # --- stage strip
        top = self.env['advmfg.stage'].sudo().search([('company_id', '=', unit.company_id.id), ('parent_id', '=', False)], order='sequence, id')
        cur_seq = unit.stage_id.sequence if unit.stage_id else 0
        stages = []
        for st in top:
            qc = qcs.filtered(lambda q: q.stage_id == st or q.stage_id.parent_id == st)[-1:]
            if unit.state == 'completed' or (unit.state != 'cancel' and st.sequence < cur_seq):
                state = 'done'
            elif unit.state != 'cancel' and st == (unit.stage_id.parent_id or unit.stage_id):
                state = 'current'
            else:
                state = 'todo'
            when = self._fmt(qc.write_date if qc and qc.state == 'pass' else False) or (_('In progress') if state == 'current' else _('Waiting') if state == 'todo' else '')
            if st.qc_required:
                qc_label = _('QC pass') if (qc and qc.state == 'pass') else (_('QC failed') if (qc and qc.state == 'fail') else (_('QC pending') if state == 'current' else (_('Not started') if state == 'todo' else _('Done'))))
            else:
                qc_label = _('Done') if state == 'done' else (_('In progress') if state == 'current' else _('Not started'))
            stages.append({
                'name': st.name, 'when': when, 'qc': qc_label,
                'dot': GREEN if state == 'done' else (BLUE if state == 'current' else '#C9D6E3'),
                'mark': '✓' if state == 'done' else ('…' if state == 'current' else ''),
                'left': '#DCE5EE' if state == 'todo' else (BLUE if state == 'current' else GREEN),
                'right': GREEN if state == 'done' else '#DCE5EE',
                'qc_fg': OK_TXT if qc_label in ('QC pass', 'Done') else (WAIT_TXT if qc_label == 'QC pending' else (RED if qc_label == 'QC failed' else MUTED)),
                'qc_bg': '#E8F6EF' if qc_label in ('QC pass', 'Done') else ('#FFF3DF' if qc_label == 'QC pending' else ('#FDECEA' if qc_label == 'QC failed' else '#EEF3F8')),
            })

        # --- detail cards
        origin = [
            {'k': _('Sale order'), 'v': ('%s · %s' % (so.name, so.partner_id.name)) if so else '-'},
            {'k': _('Manufacturing order'), 'v': mo.name or '-'},
            {'k': _('Product'), 'v': unit.product_id.display_name or '-'},
            {'k': _('Floor'), 'v': unit.floor_id.name or '-'},
            {'k': _('Serial booked'), 'v': ('%s%s' % (self._fmt(pool.create_date), (' by %s' % pool.create_uid.name) if pool else '')) if pool else '-'},
            {'k': _('Allocated to unit'), 'v': self._fmt(unit.create_date)},
            {'k': _('Line number'), 'v': '%s of %s' % (unit.line_no or '-', len(mo.advmfg_unit_ids.filtered(lambda u: u.state != 'cancel')) or 1)},
            {'k': _('Replacement of'), 'v': mo.advmfg_parent_mo_id.name if mo.advmfg_parent_mo_id else _('Not a replacement')},
        ]
        packing = [
            {'k': _('Pallet'), 'v': ('%s (%s units)' % (pallet.name, pallet.unit_count)) if pallet else _('Not on a pallet yet'), 'c': INK if pallet else MUTED},
            {'k': _('Pallet status'), 'v': (_('Confirmed') if pallet.state == 'confirmed' else _('Draft')) if pallet else _('Not applicable'), 'c': OK_TXT if pallet.state == 'confirmed' else MUTED},
            {'k': _('Delivery pack'), 'v': ('%s · %s' % (pack.name, _('confirmed') if pack.state == 'confirmed' else _('draft'))) if pack else _('Not packed yet'), 'c': OK_TXT if pack.state == 'confirmed' else MUTED},
            {'k': _('Delivery order'), 'v': ('%s · %s' % (picking.name, _('done') if picking.state == 'done' else _('waiting'))) if picking else _('Not created yet'), 'c': OK_TXT if delivered else (WAIT_TXT if picking else MUTED)},
        ]
        na = _('Not assigned')
        delivery = [
            {'k': _('Vehicle'), 'v': picking.advmfg_vehicle_name or na, 'c': INK if picking.advmfg_vehicle_name else MUTED},
            {'k': _('Vehicle number'), 'v': picking.advmfg_vehicle_number or na, 'c': INK if picking.advmfg_vehicle_number else MUTED},
            {'k': _('Driver'), 'v': picking.advmfg_driver_name or na, 'c': INK if picking.advmfg_driver_name else MUTED},
            {'k': _('Driver contact'), 'v': picking.advmfg_driver_contact or na, 'c': INK if picking.advmfg_driver_contact else MUTED},
            {'k': _('Delivered to' if delivered else 'Deliver to'), 'v': (picking.advmfg_ship_to or (so.partner_shipping_id.display_name if so else '')) or '-', 'c': INK},
            {'k': _('Dispatched'), 'v': self._fmt(picking.advmfg_dispatch_time) or _('Not yet'), 'c': INK if picking.advmfg_dispatch_time else MUTED},
            {'k': _('Expected arrival'), 'v': self._fmt(picking.advmfg_estimated_arrival) or _('Not set'), 'c': INK if picking.advmfg_estimated_arrival else MUTED},
            {'k': _('Delivered on'), 'v': self._fmt(picking.advmfg_delivered_on or (picking.date_done if delivered else False)) or _('Not yet'), 'c': OK_TXT if delivered else MUTED},
            {'k': _('Received by'), 'v': picking.advmfg_received_by or _('Not yet'), 'c': INK if picking.advmfg_received_by else MUTED},
        ]
        delivery_badge = ({'label': _('Delivered'), 'bg': '#E8F6EF', 'fg': OK_TXT} if delivered else
                          {'label': _('Dispatched'), 'bg': '#E6F0FB', 'fg': '#1D5FA8'} if picking.advmfg_dispatch_time else
                          {'label': _('Not dispatched'), 'bg': '#EEF3F8', 'fg': MUTED})

        # --- timeline
        ev = []
        if pool:
            ev.append((pool.create_date, _('Serial number booked'), _('Reserved in the serial pool by %s', pool.create_uid.name), GRAY))
        ev.append((unit.create_date, _('Allocated to a unit'), _('Unit created for %s', mo.name), BLUE))
        for q in qcs:
            if q.state == 'pass':
                ev.append((q.write_date, _('%s passed', q.stage_id.name), _('Quality check passed'), GREEN))
            elif q.state == 'fail':
                ev.append((q.write_date, _('%s failed', q.stage_id.name), q.fail_reason or _('Quality check failed'), RED))
            else:
                ev.append((q.create_date, _('%s: quality check pending', q.stage_id.name), _('The unit cannot move on until this check is passed'), AMBER))
        for sc in unit.scrap_ids:
            ev.append((sc.create_date, _('Scrapped %s', sc.product_id.display_name), _('Quantity %s', sc.scrap_qty), RED))
        if unit.state == 'completed':
            ev.append((max(qcs.mapped('write_date') or [unit.write_date]), _('Unit completed') + (_(', graded %s', unit.grade) if unit.grade else ''), _('All stages done'), GREEN))
        if pallet:
            ev.append((pallet.create_date, _('Added to %s', pallet.name), _('Pallet confirmed') if pallet.state == 'confirmed' else _('Pallet still open'), AMBER))
        if pack:
            ev.append((pack.write_date if pack.state == 'confirmed' else pack.create_date, _('Packed in %s', pack.name),
                       _('Pack confirmed for delivery %s', picking.name) if pack.state == 'confirmed' else _('Pack not confirmed yet'), AMBER))
        if picking and picking.advmfg_dispatch_time:
            ev.append((picking.advmfg_dispatch_time, _('Dispatched by vehicle %s', picking.advmfg_vehicle_number or '-'),
                       _('Driver %s', picking.advmfg_driver_name or '-'), BLUE))
        if delivered:
            ev.append((picking.advmfg_delivered_on or picking.date_done, _('Delivered to customer'), picking.advmfg_ship_to or '', GREEN))
        ev.sort(key=lambda e: (e[0] is None, e[0] or fields.Datetime.now()))
        events = [{'when': self._fmt(e[0]), 'title': e[1], 'note': e[2], 'color': e[3]} for e in ev]

        return {'serial': unit.name, 'product': unit.product_id.display_name, 'chips': chips, 'facts': facts,
                'stages': stages, 'origin': origin, 'packing': packing, 'delivery': delivery,
                'delivery_badge': delivery_badge, 'events': events, 'now': self._fmt(fields.Datetime.now())}
