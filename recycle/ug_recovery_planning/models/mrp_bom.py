from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    ug_recovery_line_ids = fields.One2many('ug.bom.recovery.line', 'bom_id', string='Recovery Rates', copy=True)


class UgBomRecoveryLine(models.Model):
    _name = 'ug.bom.recovery.line'
    _description = 'BoM Recovery Rate'
    _order = 'bom_id, sequence, id'

    bom_id = fields.Many2one('mrp.bom', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='bom_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    element_id = fields.Many2one('ug.assay.element', string='Element', required=True)
    output_product_id = fields.Many2one('product.product', string='Output Product', required=True,
        help="The finished product or one of the by-products of this BoM.")
    recovery_pct = fields.Float('Recovery (%)', digits=(5, 2), default=95.0)

    @api.constrains('element_id', 'output_product_id', 'bom_id', 'recovery_pct')
    def _check_output(self):
        for line in self:
            bom = line.bom_id
            if bom.ug_stage != 'recover':
                raise ValidationError(_("Recovery rates can only be set on recover-stage recycling BoMs."))
            outputs = bom.byproduct_ids.product_id | bom.product_id | bom.product_tmpl_id.product_variant_ids
            if line.output_product_id not in outputs:
                raise ValidationError(_(
                    "%(product)s is neither the finished product nor a by-product of BoM %(bom)s.",
                    product=line.output_product_id.display_name, bom=bom.display_name))
            if line.output_product_id.ug_metal_element_id != line.element_id:
                raise ValidationError(_(
                    "%(product)s carries %(carried)s, not %(element)s. Set its metal element on the product.",
                    product=line.output_product_id.display_name,
                    carried=line.output_product_id.ug_metal_element_id.display_name or _("no element"),
                    element=line.element_id.display_name))
            if not 0 < line.recovery_pct <= 100:
                raise ValidationError(_("Recovery rates must be between 0 and 100%."))
