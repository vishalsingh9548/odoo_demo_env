# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EpcDealer(models.Model):
    """A dealer who brings solar leads. A sub-dealer is simply a dealer that
    has a parent dealer."""
    _name = 'epc.dealer'
    _description = 'Solar Dealer / Sub-dealer'
    _order = 'complete_name'

    name = fields.Char(
        string='Dealer Name', required=True,
        help="Name of the dealer or sub-dealer.",
    )
    parent_id = fields.Many2one(
        'epc.dealer', string='Parent Dealer', ondelete='restrict',
        domain="[('parent_id', '=', False)]",
        help="Fill this in to make this a sub-dealer under another dealer.",
    )
    child_ids = fields.One2many(
        'epc.dealer', 'parent_id', string='Sub-dealers',
        help="The sub-dealers working under this dealer.",
    )
    complete_name = fields.Char(
        string='Full Name', compute='_compute_complete_name', store=True, recursive=True,
        help="Dealer name, with the parent dealer in front for a sub-dealer.",
    )
    phone = fields.Char(string='Phone', help="Contact number of the dealer.")
    email = fields.Char(string='Email', help="Contact email of the dealer.")
    commission_percent = fields.Float(
        string='Commission (%)',
        help="Commission this dealer earns on the order value. Used for the "
             "commission-payable figure; it does not change the quote.",
    )
    active = fields.Boolean(
        default=True,
        help="Untick to hide this dealer from new leads without deleting it.",
    )
    lead_count = fields.Integer(
        string='Leads', compute='_compute_lead_count',
        help="How many leads this dealer (or its sub-dealers) brought.",
    )

    # Shows "Parent / Child" for sub-dealers so they are easy to tell apart
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for dealer in self:
            dealer.complete_name = (
                "%s / %s" % (dealer.parent_id.complete_name, dealer.name)
                if dealer.parent_id else dealer.name)

    # Counts leads linked to this dealer or one of its sub-dealers
    def _compute_lead_count(self):
        for dealer in self:
            dealer.lead_count = self.env['crm.lead'].search_count([
                '|', ('dealer_id', '=', dealer.id), ('sub_dealer_id', 'in', dealer.child_ids.ids)])

    @api.constrains('parent_id')
    def _check_parent(self):
        for dealer in self:
            if dealer.parent_id and (dealer.parent_id == dealer or dealer.parent_id.parent_id):
                raise ValidationError("A sub-dealer can only sit under a top-level dealer.")

    # Opens the leads brought by this dealer, from the "Leads" smart button
    def action_view_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Leads of %s' % self.complete_name,
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': ['|', ('dealer_id', '=', self.id), ('sub_dealer_id', 'in', self.child_ids.ids)],
        }
