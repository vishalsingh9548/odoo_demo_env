from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ug_epr_eligible_kg = fields.Float('EPR Eligible (kg)', compute='_compute_ug_epr_eligible_kg', store=True,
        digits='Product Unit of Measure', help="Quantity of this done order that can back EPR certificates, "
                                    "according to the company EPR basis.")
    ug_epr_allocation_ids = fields.One2many('ug.epr.allocation', 'production_id', string='EPR Claims')
    ug_epr_certificate_ids = fields.Many2many('ug.epr.certificate', 'ug_epr_certificate_production_rel',
        'production_id', 'certificate_id', string='EPR Certificates', readonly=True)
    ug_epr_claimed_kg = fields.Float('EPR Claimed (kg)', compute='_compute_ug_epr_claimed_kg', store=True,
        digits='Product Unit of Measure')
    ug_epr_available_kg = fields.Float('EPR Available (kg)', compute='_compute_ug_epr_claimed_kg', store=True,
        digits='Product Unit of Measure')

    @api.depends('state', 'ug_stage', 'ug_input_weight_kg', 'company_id.ug_epr_basis',
                 'move_finished_ids.state', 'move_finished_ids.quantity')
    def _compute_ug_epr_eligible_kg(self):
        for production in self:
            eligible = 0.0
            if production.state == 'done' and production.ug_is_recycling:
                basis = production.company_id.ug_epr_basis or 'input_battery_weight'
                if basis == 'input_battery_weight' and production.ug_stage == 'dismantle':
                    eligible = production.ug_input_weight_kg
                elif basis == 'recovered_material_weight' and production.ug_stage == 'recover':
                    moves = production.move_finished_ids.filtered(
                        lambda m: m.state == 'done' and m.product_id.ug_material_type == 'recovered_material')
                    eligible = production._ug_moves_kg(moves)
            production.ug_epr_eligible_kg = eligible

    @api.depends('ug_epr_eligible_kg', 'ug_epr_allocation_ids.quantity_kg', 'ug_epr_allocation_ids.certificate_state')
    def _compute_ug_epr_claimed_kg(self):
        for production in self:
            claimed = sum(production.ug_epr_allocation_ids.filtered(
                lambda a: a.certificate_state != 'cancelled').mapped('quantity_kg'))
            production.ug_epr_claimed_kg = claimed
            production.ug_epr_available_kg = production.ug_epr_eligible_kg - claimed

    ug_epr_certificate_count = fields.Integer(compute='_compute_ug_epr_certificate_count', string='EPR Certificate Count')

    @api.depends('ug_epr_certificate_ids')
    def _compute_ug_epr_certificate_count(self):
        for production in self:
            production.ug_epr_certificate_count = len(production.ug_epr_certificate_ids)

    def action_ug_create_epr_certificate(self):
        """ New certificate pre-filled with this order's available EPR quantity. """
        self.ensure_one()
        if self.state != 'done' or self.ug_epr_available_kg <= 0:
            raise UserError(_("%s has no EPR quantity left to claim.", self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': _("New EPR Certificate"),
            'res_model': 'ug.epr.certificate',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_production_ids': [Command.set(self.ids)],
                'default_quantity_kg': self.ug_epr_available_kg,
                'default_battery_chemistry_id': self.battery_chemistry_id.id,
                'default_company_id': self.company_id.id,
            },
        }

    def action_ug_view_epr_certificates(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ug_epr.ug_epr_certificate_action')
        action['domain'] = [('id', 'in', self.ug_epr_certificate_ids.ids)]
        action['context'] = {'create': False}
        if len(self.ug_epr_certificate_ids) == 1:
            action.update({'views': [(False, 'form')], 'res_id': self.ug_epr_certificate_ids.id})
        return action
