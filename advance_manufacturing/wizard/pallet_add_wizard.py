from odoo import fields, models, _
from odoo.exceptions import UserError


class AdvmfgPalletAddWizard(models.TransientModel):
    """The scan box: type or scan a serial and it is checked, then added to the pallet.

    Each serial must pass five checks before it goes on the pallet (see action_add).
    """
    _name = 'advmfg.pallet.add.wizard'
    _description = 'Add Serial to Pallet'

    pallet_id = fields.Many2one('advmfg.pallet', required=True)
    serial = fields.Char(string='Serial Number', required=True)

    def action_add(self):
        """Run the five checks, then put the unit on the pallet."""
        self.ensure_one()
        pallet = self.pallet_id
        serial = (self.serial or '').strip()
        # 1. Something must be typed.
        if not serial:
            raise UserError(_('No serial number scanned.'))
        # 2. The serial must exist as a completed unit.
        unit = self.env['advmfg.unit'].search([
            ('name', '=', serial), ('company_id', '=', pallet.company_id.id),
            ('state', '=', 'completed')], limit=1)
        if not unit:
            raise UserError(_("Serial '%s' was not found or is not completed.", serial))
        # 3. It must belong to this pallet's manufacturing order.
        if unit.production_id != pallet.production_id:
            raise UserError(_("Serial '%(s)s' does not belong to this order. It belongs to %(mo)s.",
                              s=serial, mo=unit.production_id.name))
        # 4. It must not already be on this pallet.
        if unit.pallet_id == pallet:
            raise UserError(_("Serial '%s' is already on this pallet.", serial))
        # 5. It must not be on a different pallet.
        if unit.pallet_id:
            raise UserError(_("Serial '%(s)s' is already on pallet '%(p)s'. One serial cannot be on two pallets.",
                              s=serial, p=unit.pallet_id.name))
        unit.pallet_id = pallet
        # Re-open the scan box so the next serial can be scanned straight away.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Serial to Pallet'),
            'res_model': 'advmfg.pallet.add.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_pallet_id': pallet.id},
        }
