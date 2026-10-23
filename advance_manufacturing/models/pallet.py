from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AdvmfgPallet(models.Model):
    """A pallet (tray) of finished units, with its own QR code.

    Draft = still being filled. Confirmed = locked; units can no longer be added or removed.
    """
    _name = 'advmfg.pallet'
    _description = 'Pallet'
    _order = 'id'

    name = fields.Char(default='New', copy=False, readonly=True)
    production_id = fields.Many2one('mrp.production', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='production_id.company_id', store=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')], default='draft', required=True)
    unit_ids = fields.One2many('advmfg.unit', 'pallet_id', string='Units')
    # The delivery pack(s) this pallet has been put into (used to hide pallets that are already packed).
    delivery_pack_ids = fields.Many2many('advmfg.delivery.pack', 'advmfg_delivery_pack_advmfg_pallet_rel',
                                         'advmfg_pallet_id', 'advmfg_delivery_pack_id', string='Delivery Packs', copy=False)
    # Same units as 'unit_ids', but editable as tags on the pallet line: picking a serial puts it on the pallet,
    # removing it takes it off (only while the pallet is still a draft).
    unit_pick_ids = fields.Many2many('advmfg.unit', string='Serial Numbers', compute='_compute_unit_pick_ids',
                                     inverse='_inverse_unit_pick_ids')
    unit_count = fields.Integer(compute='_compute_unit_count')
    # Text packed inside the QR code: pallet name, how many units, and the serial list.
    qr_text = fields.Char(compute='_compute_qr_text')

    @api.depends('unit_ids')
    def _compute_unit_pick_ids(self):
        """The serials currently on the pallet."""
        for pallet in self:
            pallet.unit_pick_ids = pallet.unit_ids

    def _inverse_unit_pick_ids(self):
        """Apply the serials chosen on the line: new ones go on the pallet, removed ones come off."""
        for pallet in self:
            if pallet.state == 'confirmed':
                continue
            chosen = pallet.unit_pick_ids
            (pallet.unit_ids - chosen).write({'pallet_id': False})
            for unit in chosen - pallet.unit_ids:
                if unit.production_id != pallet.production_id:
                    raise ValidationError(_("Serial '%(s)s' belongs to %(mo)s, not to this order.",
                                            s=unit.name, mo=unit.production_id.name))
                if unit.pallet_id:
                    raise ValidationError(_("Serial '%(s)s' is already on pallet '%(p)s'.", s=unit.name, p=unit.pallet_id.name))
                if unit.state != 'completed':
                    raise ValidationError(_("Serial '%s' is not completed yet.", unit.name))
                unit.pallet_id = pallet.id

    @api.depends('unit_ids')
    def _compute_unit_count(self):
        """How many units are on this pallet."""
        for pallet in self:
            pallet.unit_count = len(pallet.unit_ids)

    @api.depends('unit_ids', 'name')
    def _compute_qr_text(self):
        """Build the text that the QR code will hold."""
        for pallet in self:
            pallet.qr_text = '%s | Units: %s | %s' % (
                pallet.name, len(pallet.unit_ids), ', '.join(pallet.unit_ids.mapped('name')))

    @api.model_create_multi
    def create(self, vals_list):
        """Give every new pallet its next number (PALLET0001...)."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('advmfg.pallet') or 'New'
        return super().create(vals_list)

    @api.constrains('unit_ids')
    def _check_units(self):
        """Pallet rules: only finished units of this order, and never over the pallet limit."""
        for pallet in self:
            limit = pallet.company_id.advmfg_max_pallet_qty or 28
            if len(pallet.unit_ids) > limit:
                raise ValidationError(_('A pallet can hold at most %s units.', limit))
            for unit in pallet.unit_ids:
                if unit.state != 'completed':
                    raise ValidationError(_('Unit %s is not completed yet.', unit.name))
                if unit.production_id != pallet.production_id:
                    raise ValidationError(_('Unit %s belongs to another manufacturing order.', unit.name))

    def unlink(self):
        """A confirmed pallet cannot be deleted."""
        if any(p.state == 'confirmed' for p in self):
            raise UserError(_('Confirmed pallets cannot be deleted.'))
        return super().unlink()

    def action_add_serial(self):
        """Open the scan box where a serial is typed/scanned onto this pallet."""
        self.ensure_one()
        if self.state == 'confirmed':
            raise UserError(_('This pallet is confirmed and locked.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Serial to Pallet'),
            'res_model': 'advmfg.pallet.add.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_pallet_id': self.id},
        }

    def action_confirm(self):
        """Confirm: needs at least one unit; locks the pallet."""
        for pallet in self:
            if not pallet.unit_ids:
                raise UserError(_('Pallet %s has no units. Add serial numbers before confirming.', pallet.name))
            pallet.state = 'confirmed'
        return True

    def action_reset_draft(self):
        """Reset to Draft: only flips the label back so units can be edited again."""
        self.write({'state': 'draft'})
        return True

    def action_print(self):
        """Print the pallet sheet with its QR code."""
        return self.env.ref('advance_manufacturing.action_report_advmfg_pallet').report_action(self)
