# -*- coding: utf-8 -*-
from odoo import api, fields, models


class EpcConfig(models.AbstractModel):
    """Tiny helper that reads the Solar EPC switches (Solar Dashboard >
    Configuration > Settings). Every switch that makes the app stricter is OFF
    unless someone turns it on, so existing behaviour never changes by itself.
    """
    _name = 'epc.config'
    _description = 'Solar EPC settings helper'

    # True when the named switch (stored as a system parameter) is switched on
    @api.model
    def flag(self, name):
        return bool(self.env['ir.config_parameter'].sudo().get_param('csl_epc.%s' % name))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    epc_block_self_approval = fields.Boolean(
        string='Block Self-Approval', config_parameter='csl_epc.block_self_approval',
        help="The person who submitted a document cannot approve or reject it themselves.",
    )
    epc_lock_approved = fields.Boolean(
        string='Lock Approved Documents', config_parameter='csl_epc.lock_approved',
        help="Once a document is approved its details can no longer be edited "
             "(use Reset to Draft to change it).",
    )
    epc_disable_notifications = fields.Boolean(
        string='Turn Off Notifications', config_parameter='csl_epc.disable_notifications',
        help="Stops the automatic to-do activities and messages (approval requests, "
             "rejections, failed quality checks, AMC reminders).",
    )

    epc_block_not_feasible = fields.Boolean(
        string='Stop Work on "Not Feasible"', config_parameter='csl_epc.block_not_feasible',
        help="A site survey or feasibility study with the verdict 'no' cannot be moved "
             "to the next stage unless a manager ticks 'Proceed anyway'.",
    )

    epc_strict_boq = fields.Boolean(
        string='Strict BOQ Check', config_parameter='csl_epc.strict_boq',
        help="Before a quotation is created from a BOQ, every line must have a product "
             "(except service lines such as labour or civil work) and a unit cost, "
             "or be ticked 'Zero cost is correct'.",
    )

    epc_mr_block_over_boq = fields.Boolean(
        string='Block Over-BOQ Requests', config_parameter='csl_epc.mr_block_over_boq',
        help="A material request cannot be submitted for more of a product than the "
             "project's BOQ allows (otherwise only a warning is written in the chatter).",
    )
    epc_qc_require_fail_remark = fields.Boolean(
        string='Failed Items Need a Remark', config_parameter='csl_epc.qc_require_fail_remark',
        help="Every failed quality-check item must have a remark explaining why.",
    )
    epc_qc_lock_results = fields.Boolean(
        string='Lock Finished Quality Checks', config_parameter='csl_epc.qc_lock_results',
        help="Once a quality check is Pass or Fail only a Project Manager can change its items.",
    )
    epc_comm_require_testing = fields.Boolean(
        string='Commissioning: Testing Done', config_parameter='csl_epc.comm_require_testing',
        help="'System Testing Done' must be ticked before commissioning is submitted.",
    )
    epc_comm_require_walkthrough = fields.Boolean(
        string='Commissioning: Customer Walkthrough', config_parameter='csl_epc.comm_require_walkthrough',
        help="'Customer Walkthrough Done' must be ticked before commissioning is submitted.",
    )
    epc_comm_require_generation = fields.Boolean(
        string='Commissioning: Verified Generation', config_parameter='csl_epc.comm_require_generation',
        help="A verified generation figure (kWh) must be entered before commissioning is submitted.",
    )
    epc_comm_require_customer_approval = fields.Boolean(
        string='Commissioning: Customer Approved', config_parameter='csl_epc.comm_require_customer_approval',
        help="'Customer Approved' must be ticked before commissioning can be approved.",
    )
    epc_comm_require_certificate = fields.Boolean(
        string='Commissioning: Certificate Uploaded', config_parameter='csl_epc.comm_require_certificate',
        help="The commissioning certificate must be uploaded before commissioning can be approved.",
    )
    epc_comm_single_per_project = fields.Boolean(
        string='One Commissioning per Project', config_parameter='csl_epc.comm_single_per_project',
        help="A project can only have one commissioning record (a rejected one does not count).",
    )
    epc_handover_require_commissioning = fields.Boolean(
        string='Handover Needs Approved Commissioning', config_parameter='csl_epc.handover_require_commissioning',
        help="A handover can only be approved once the project's commissioning is approved.",
    )
    epc_handover_require_docs = fields.Boolean(
        string='Handover Needs Documents', config_parameter='csl_epc.handover_require_docs',
        help="The four handover documents and the customer training must be in place before a handover is approved.",
    )
    epc_amc_generate_services = fields.Boolean(
        string='Create AMC Service Visits Automatically', config_parameter='csl_epc.amc_generate_services',
        help="Each day, creates a Field Service task for every active AMC contract whose preventive service is due.",
    )
