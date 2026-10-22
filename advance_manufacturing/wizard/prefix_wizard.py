import re

from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgPrefixWizard(models.TransientModel):
    """Change the serial-number prefix of the not-yet-allocated serials of one or more orders."""
    _name = 'advmfg.prefix.wizard'
    _description = 'MO Prefix Update'

    name = fields.Char(string='Prefix', required=True)

    def update_mo_serial_prefix(self):
        """Update Prefix: rename every unallocated serial of the selected orders (company default is left alone)."""
        self.ensure_one()
        orders = self.env['mrp.production'].browse(self.env.context.get('active_ids') or [])
        for mo in orders:
            if mo.state == 'cancel':
                raise UserError(_('You cannot change serial numbers on cancelled MOs.'))
            config = self.env['advmfg.serial.prefix'].search([('company_id', '=', mo.company_id.id)], limit=1)
            if not config:
                raise UserError(_('No configuration found for company %s.', mo.company_id.name))
            if not mo.advmfg_serial_ids:
                raise UserError(_('No serial numbers found for Manufacturing Order %s.', mo.name))
            free = mo.advmfg_serial_ids.filtered(lambda s: s.state == 'available')
            if not free:
                raise UserError(_('All serial numbers in Manufacturing Order %s are allocated. Cannot change prefix.', mo.name))
            for serial in free:
                old = config.prefix or ''
                tail = serial.name[len(old):] if old and serial.name.startswith(old) else re.sub(r'^\D*', '', serial.name)
                serial.name = '%s%s' % (self.name, tail)
        return {'type': 'ir.actions.act_window_close'}
