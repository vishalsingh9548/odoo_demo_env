from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AdvmfgStage(models.Model):
    """One station on the unit's journey (for example 'Testing' or 'Lamination').

    You create these yourself under Manufacturing > Configuration > Process Stages.
    """
    _name = 'advmfg.stage'
    _description = 'Process Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    # Lower number = earlier station.
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    # If ticked, every unit gets a pass/fail quality check when it reaches this station.
    qc_required = fields.Boolean(string='Quality Check Required')
    # Kind of check. Only a simple pass/fail check is supported (no spreadsheet checks).
    test_type = fields.Selection([('passfail', 'Pass - Fail')], string='Quality Test Type', default='passfail')
    # If ticked, a document must be attached before the unit can leave this station.
    attachment_required = fields.Boolean(string='Attachment Required')
    # If unticked, the A/B/C grade choice is hidden here and "A" is assumed.
    show_grade = fields.Boolean(string='Ask for Grade', default=True)
    # A child stage is a sub-test of a parent: passing the parent counts the child as passed too.
    parent_id = fields.Many2one('advmfg.stage', string='Parent Stage', ondelete='restrict')
    child_ids = fields.One2many('advmfg.stage', 'parent_id', string='Sub-stages')

    @api.constrains('parent_id')
    def _check_parent_loop(self):
        """Stop a stage from being its own parent, directly or through a circle."""
        if self._has_cycle('parent_id'):
            raise ValidationError(_('A stage cannot be its own parent (circular link).'))

    def _is_auto_surpassed(self):
        """True when a stage is skipped because one of its parents sits LATER in the order.

        Example: stage 1 whose parent is stage 3 - passing stage 3 covers stage 1, so stage 1 is never a step.
        """
        self.ensure_one()
        cursor = self.parent_id
        while cursor:
            if (cursor.sequence or 0) > (self.sequence or 0):
                return True
            cursor = cursor.parent_id
        return False

    @api.model
    def _first_step(self, company, from_stage=None):
        """The first real step: lowest-numbered top-level stage that is not auto-skipped.

        With `from_stage`, only stages at or after that stage's order are considered.
        """
        domain = [('company_id', '=', company.id), ('parent_id', '=', False)]
        if from_stage:
            domain.append(('sequence', '>=', from_stage.sequence or 0))
        for stage in self.search(domain, order='sequence asc, id asc'):
            if not stage._is_auto_surpassed():
                return stage
        return from_stage or self.browse()

    def _descendants(self):
        """All stages hanging under this one (children, grand-children...)."""
        self.ensure_one()
        found, queue = self.browse(), self.child_ids
        while queue:
            found |= queue
            queue = queue.child_ids - found
        return found

    @api.model
    def _cumulative_count_map(self, company):
        """For each top-level stage: how many stages are covered once it is passed.

        Running total, in order, of (1 + number of sub-stages) for every top-level stage.
        """
        total, mapping = 0, {}
        for parent in self.search([('company_id', '=', company.id), ('parent_id', '=', False)],
                                  order='sequence asc, id asc'):
            total += 1 + len(parent._descendants())
            mapping[parent.id] = total
        return mapping
