# -*- coding: utf-8 -*-
from odoo import fields, models

DOCUMENT_CATEGORIES = [
    ('kyc', 'KYC / ID Proof'),
    ('subsidy', 'Subsidy'),
    ('net_metering', 'Net Metering'),
    ('structure', 'Structure Certificate'),
    ('commissioning', 'Commissioning'),
    ('other', 'Other'),
]


class EpcDocumentTemplate(models.Model):
    """One kind of paper that must be collected or filed for a project
    (e.g. 'Latest electricity bill'). Templates are copied onto every new
    project when its order is confirmed."""
    _name = 'epc.document.template'
    _description = 'Solar Document Template'
    _order = 'sequence, id'

    name = fields.Char(string='Document', required=True, help="Name of the paper, e.g. 'Latest electricity bill'.")
    sequence = fields.Integer(default=10, help="Order in which documents are listed.")
    category = fields.Selection(
        DOCUMENT_CATEGORIES, string='Category', required=True, default='kyc',
        help="Which group of papers this belongs to.",
    )
    mandatory = fields.Boolean(
        string='Mandatory', default=True,
        help="A mandatory paper must be done before the project can move on "
             "(when the 'Documents Block Commissioning' switch is on).",
    )
    segment = fields.Selection(
        [('all', 'All customers'), ('residential', 'Residential'),
         ('commercial', 'Commercial'), ('industrial', 'Industrial')],
        string='Applies To', default='all', required=True,
        help="Only projects for this type of customer get this document.",
    )
    auto_create = fields.Boolean(
        string='Create Automatically', default=True,
        help="Create this document on every matching project when its order is "
             "confirmed. Untick for papers that are only needed in special cases "
             "(for example a subsidy scheme adds its own papers).",
    )
    active = fields.Boolean(default=True, help="Untick to stop using this template.")
    notes = fields.Text(string='Instructions', help="Tips for the person collecting this paper.")
