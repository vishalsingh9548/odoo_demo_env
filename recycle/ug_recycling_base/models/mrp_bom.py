from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

STAGES = [
    ('dismantle', 'Dismantle'),
    ('shred', 'Shred'),
    ('recover', 'Recover'),
]


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Battery Chemistry', index=True)
    ug_is_recycling = fields.Boolean('Recycling BoM', index=True)
    ug_stage = fields.Selection(STAGES, string='Recycling Stage', index=True)
    ug_max_loss_pct = fields.Float('Max Process Loss (%)', default=5.0,
        help="Acceptable process loss for this stage. An alert is raised when a done MO exceeds it.")
    ug_primary_line_id = fields.Many2one('mrp.bom.line', compute='_compute_ug_primary_line_id',
        string='Primary Input Line')
    # yield of the main product = main output kg / primary input kg
    ug_yield_tolerance_pct = fields.Float('Yield Tolerance (%)', default=10.0,
        help="Accepted deviation of the actual yield from the BoM standard yield, relative to it "
             "(10 % on a 35 % standard yield accepts 31.5 % to 38.5 %). 0 disables the check.")
    ug_standard_yield_pct = fields.Float('Standard Yield (%)', compute='_compute_ug_yield_band', digits=(16, 2),
        help="Main product kg per 100 kg of primary input, from the BoM quantities.")
    ug_yield_min_pct = fields.Float('Min Yield (%)', compute='_compute_ug_yield_band', digits=(16, 2))
    ug_yield_max_pct = fields.Float('Max Yield (%)', compute='_compute_ug_yield_band', digits=(16, 2))

    @api.depends('bom_line_ids.ug_is_primary_input')
    def _compute_ug_primary_line_id(self):
        for bom in self:
            bom.ug_primary_line_id = bom.bom_line_ids.filtered('ug_is_primary_input')[:1]

    @api.depends('product_qty', 'product_uom_id', 'bom_line_ids.product_qty', 'bom_line_ids.product_uom_id',
                 'bom_line_ids.ug_is_primary_input', 'ug_yield_tolerance_pct')
    def _compute_ug_yield_band(self):
        for bom in self:
            primary = bom.bom_line_ids.filtered('ug_is_primary_input')[:1]
            input_kg = primary and primary.product_uom_id._ug_to_kg(primary.product_qty)
            output_kg = bom.product_uom_id._ug_to_kg(bom.product_qty) if bom.product_uom_id else 0.0
            standard = input_kg and output_kg / input_kg * 100 or 0.0
            tolerance = standard * bom.ug_yield_tolerance_pct / 100
            bom.ug_standard_yield_pct = standard
            bom.ug_yield_min_pct = standard - tolerance if bom.ug_yield_tolerance_pct else 0.0
            bom.ug_yield_max_pct = standard + tolerance if bom.ug_yield_tolerance_pct else 0.0

    def _ug_check_yield(self):
        """ Yield band applies to the weight-based stages; recover is judged on assay efficiency. """
        self.ensure_one()
        return self.ug_is_recycling and self.ug_stage in ('dismantle', 'shred') \
            and self.ug_yield_tolerance_pct > 0 and self.ug_standard_yield_pct > 0

    @api.constrains('ug_is_recycling', 'ug_stage', 'bom_line_ids', 'byproduct_ids')
    def _check_ug_recycling(self):
        for bom in self.filtered('ug_is_recycling'):
            if not bom.ug_stage:
                raise ValidationError(_("Recycling BoM %s must have a recycling stage.", bom.display_name))
            if bom.ug_stage in ('dismantle', 'shred') and not bom.byproduct_ids:
                raise ValidationError(_(
                    "Recycling BoM %s (stage dismantle or shred) must have at least one by-product.",
                    bom.display_name))
        self._ug_check_primary_input()
        self._ug_check_cost_share()

    def _ug_check_primary_input(self):
        for bom in self.filtered('ug_is_recycling'):
            primary = bom.bom_line_ids.filtered('ug_is_primary_input')
            if len(primary) != 1:
                raise ValidationError(_(
                    "Recycling BoM %(bom)s must have exactly one primary input line (found %(count)s).",
                    bom=bom.display_name, count=len(primary)))

    def _ug_check_cost_share(self):
        for bom in self.filtered('ug_is_recycling'):
            if sum(bom.byproduct_ids.mapped('cost_share')) >= 100:
                raise ValidationError(_(
                    "The total cost share of the by-products of %s must be below 100%%.", bom.display_name))

    @api.constrains('ug_max_loss_pct', 'ug_yield_tolerance_pct')
    def _check_ug_max_loss_pct(self):
        for bom in self:
            if not 0 <= bom.ug_max_loss_pct <= 100:
                raise ValidationError(_("The maximum process loss must be between 0 and 100%."))
            if not 0 <= bom.ug_yield_tolerance_pct <= 100:
                raise ValidationError(_("The yield tolerance must be between 0 and 100%."))

    @api.onchange('product_tmpl_id')
    def _onchange_ug_product_chemistry(self):
        if self.product_tmpl_id.battery_chemistry_id and not self.battery_chemistry_id:
            self.battery_chemistry_id = self.product_tmpl_id.battery_chemistry_id


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    ug_is_primary_input = fields.Boolean('Primary Input',
        help="The main material broken down by this BoM (battery pack, cells or black mass). "
             "Process chemicals are never primary.")

    @api.constrains('ug_is_primary_input', 'bom_id')
    def _check_ug_primary_input(self):
        self.bom_id._ug_check_primary_input()


class MrpBomByproduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    @api.constrains('cost_share', 'bom_id')
    def _check_ug_cost_share(self):
        self.bom_id._ug_check_cost_share()
