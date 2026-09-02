# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    """Stages 5-6 of the EPC pipeline: adds solar-specific commercial terms to
    the standard Quotation/Sales Order screen, and the bridge that turns a
    confirmed order into a real EPC Project (Stage 7).
    """
    _inherit = 'sale.order'

    boq_id = fields.Many2one(
        'epc.boq', string='Source BOQ', copy=False,
        help="The Bill of Quantities this quotation was generated from, if any.",
    )

    warranty_type = fields.Selection(
        [('performance', 'Performance Warranty'), ('replacement', 'Replacement Warranty'), ('both', 'Both')],
        string='Warranty Type',
        help="What kind of warranty is being offered on this system.",
    )
    delivery_type = fields.Selection(
        [('immediate', 'Immediate'), ('scheduled', 'Scheduled'), ('as_discussed', 'As Per Discussion')],
        string='Delivery Terms',
        help="When the equipment will be delivered to site.",
    )
    freight_type = fields.Selection(
        [('extra', 'Freight Extra'), ('included', 'Freight Included')],
        string='Freight Terms',
        help="Whether transport/freight cost is already included in the quoted price.",
    )
    payment_terms_type = fields.Selection(
        [('advance', 'Advance Payment'), ('milestone', 'Milestone-wise'), ('credit', 'Credit')],
        string='EPC Payment Structure',
        help="The overall payment structure agreed with the customer (different "
             "from the accounting Payment Terms field, which controls invoice due dates).",
    )
    cancellation_policy = fields.Selection(
        [('deduction', 'Deduction on Cancellation'), ('non_refundable', 'Non-Refundable Token'), ('custom', 'Custom Terms')],
        string='Cancellation Policy',
        help="What happens to any advance paid if the customer cancels the order.",
    )
    certification_type = fields.Selection(
        [('iec', 'IEC'), ('bis', 'BIS'), ('both', 'IEC + BIS')],
        string='Certifications',
        help="Which product certifications apply to the equipment being supplied.",
    )
    tolerance_type = fields.Selection(
        [('positive', 'Positive Tolerance'), ('range', '± Range Tolerance')],
        string='Wattage Tolerance',
        help="The manufacturing tolerance allowed on the rated wattage of the modules supplied.",
    )

    epc_project_id = fields.Many2one(
        'project.project', string='EPC Project', copy=False, readonly=True,
        help="The installation Project created from this order once it is confirmed.",
    )
    epc_project_count = fields.Integer(
        string='Project Count', compute='_compute_epc_project_count',
        help="Whether an EPC Project has already been created from this order (0 or 1).",
    )

    # Shows 1 on the smart button once a Project has been created from this order, else 0
    @api.depends('epc_project_id')
    def _compute_epc_project_count(self):
        for order in self:
            order.epc_project_count = 1 if order.epc_project_id else 0

    # Confirms the order as usual, then makes sure an EPC Project exists for it
    # (Stage 6 -> Stage 7 bridge): this is where "Sales Order" hands off to "Project Creation"
    def action_confirm(self):
        result = super().action_confirm()
        for order in self:
            if not order.epc_project_id:
                order._epc_create_project()
        return result

    # Creates the EPC Project for this order, copying over the customer, capacity
    # and BOQ reference so the project starts with the right context already filled in
    def _epc_create_project(self):
        self.ensure_one()
        project = self.env['project.project'].create({
            'name': f"{self.partner_id.name} - Solar EPC ({self.name})",
            'partner_id': self.partner_id.id,
            'epc_sale_order_id': self.id,
            'boq_id': self.boq_id.id if self.boq_id else False,
            'lead_id': self.opportunity_id.id if self.opportunity_id else False,
        })
        self.epc_project_id = project.id
        project._epc_seed_default_milestones()
        return project

    # Opens the EPC Project linked to this order, called from the "Project" smart button
    def action_view_epc_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.epc_project_id.id,
            'target': 'current',
        }
