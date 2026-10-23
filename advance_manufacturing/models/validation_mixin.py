from odoo import models, _
from odoo.exceptions import ValidationError


class AdvmfgValidationMixin(models.AbstractModel):
    """Shared checks used by every screen that moves a unit forward (Update Status, scan station).

    Keeping them in one place means the rules are identical everywhere.
    """
    _name = 'advmfg.validation.mixin'
    _description = 'Shared unit validation rules'

    def _units_in_context(self):
        """The unit(s) the current screen is working on (from the screen's context)."""
        ctx = self.env.context
        if ctx.get('active_model') == 'advmfg.status.wizard' or ctx.get('default_unit_id'):
            return self.env['advmfg.unit'].browse(ctx.get('default_unit_id'))
        if ctx.get('active_model') == 'advmfg.unit':
            return self.env['advmfg.unit'].browse(ctx.get('active_ids') or [])
        return self.env['advmfg.unit']

    def _check_attachment_count(self, units=None):
        """Documents are optional now: attaching one is allowed but never required to move on."""
        return True

    def _check_previous_line_status(self, units=None):
        """Units are worked in order: the previous unit's current stage must not be behind this one."""
        for unit in (units or self._units_in_context()):
            try:
                number = int(unit.line_no or 0)
            except ValueError:
                continue
            previous = self.env['advmfg.unit'].search([
                ('production_id', '=', unit.production_id.id), ('line_no', '=', str(number - 1)),
                ('state', 'not in', ('cancel', 'completed'))], limit=1)
            if previous and (previous.stage_id.sequence or 0) < (unit.stage_id.sequence or 0):
                raise ValidationError(_('Please complete the previous step before proceeding to the next one.'))

    def _check_quality_status(self, units=None):
        """A stage with a quality check cannot move on until that check is passed."""
        for unit in (units or self._units_in_context()):
            if unit.stage_id.qc_required and unit.qc_id.state != 'pass':
                raise ValidationError(_('Please pass the quality check before moving to the next stage.'))
