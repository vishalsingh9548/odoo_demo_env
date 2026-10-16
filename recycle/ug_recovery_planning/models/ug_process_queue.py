from odoo import _, fields, models, tools
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import SQL

from odoo.addons.ug_recycling_base.models.mrp_bom import STAGES


class UgProcessQueue(models.Model):
    """ Lots in stock waiting for their next recycling stage.

    A lot is queued when its product is the primary input of an active recycling
    BoM (packs -> dismantle, cells -> shred, black mass -> recover) and part of it
    is neither reserved by a confirmed order nor planned in a draft order.
    """
    _name = 'ug.process.queue'
    _description = 'Recycling Lots To Process'
    _auto = False
    _order = 'in_date, id'
    _rec_name = 'lot_id'

    lot_id = fields.Many2one('stock.lot', string='Lot', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    battery_chemistry_id = fields.Many2one('ug.battery.chemistry', string='Chemistry', readonly=True)
    bom_id = fields.Many2one('mrp.bom', string='Next BoM', readonly=True)
    stage = fields.Selection(STAGES, string='Next Stage', readonly=True)
    assay_state = fields.Selection([
        ('not_required', 'Not Required'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
    ], string='Assay', readonly=True)
    on_hand_kg = fields.Float('On Hand (kg)', readonly=True, digits='Product Unit of Measure')
    reserved_kg = fields.Float('Reserved (kg)', readonly=True, digits='Product Unit of Measure')
    planned_kg = fields.Float('In Draft MOs (kg)', readonly=True, digits='Product Unit of Measure')
    available_kg = fields.Float('To Process (kg)', readonly=True, digits='Product Unit of Measure')
    in_date = fields.Datetime('In Stock Since', readonly=True)
    waiting_days = fields.Integer('Days Waiting', compute='_compute_waiting_days')
    ready = fields.Boolean('Ready', readonly=True,
        help="False while a recover-stage lot is waiting for its assay approval.")
    source_production_id = fields.Many2one('mrp.production', string='Source MO',
        compute='_compute_source_production_id')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        kg = self.env.ref('uom.product_uom_kgm')
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH kg AS (
                    SELECT factor, category_id FROM uom_uom WHERE id = %(kg_id)s
                ), next_bom AS (
                    SELECT DISTINCT ON (bl.product_id, b.company_id)
                           bl.product_id, b.company_id, b.id AS bom_id, b.ug_stage AS stage
                      FROM mrp_bom_line bl
                      JOIN mrp_bom b ON b.id = bl.bom_id
                     WHERE bl.ug_is_primary_input AND b.ug_is_recycling AND b.active
                  ORDER BY bl.product_id, b.company_id, b.sequence, b.id
                ), stock AS (
                    SELECT q.lot_id, q.product_id, q.company_id,
                           SUM(q.quantity) AS qty, SUM(q.reserved_quantity) AS reserved, MIN(q.in_date) AS in_date
                      FROM stock_quant q
                      JOIN stock_location loc ON loc.id = q.location_id
                     WHERE loc.usage = 'internal' AND q.lot_id IS NOT NULL
                  GROUP BY q.lot_id, q.product_id, q.company_id
                ), planned AS (
                    SELECT il.lot_id, SUM(il.qty_kg) AS planned_kg
                      FROM ug_production_input_lot il
                      JOIN mrp_production p ON p.id = il.production_id
                     WHERE p.state = 'draft'
                  GROUP BY il.lot_id
                ), queue AS (
                    SELECT DISTINCT ON (s.lot_id)
                           s.lot_id, s.product_id, s.company_id, nb.bom_id, nb.stage,
                           lot.battery_chemistry_id, lot.ug_assay_state AS assay_state, s.in_date,
                           CASE WHEN u.category_id = kg.category_id AND u.factor > 0
                                THEN kg.factor / u.factor ELSE 0 END AS to_kg,
                           s.qty, s.reserved, COALESCE(pl.planned_kg, 0) AS planned_kg
                      FROM stock s
                      JOIN stock_lot lot ON lot.id = s.lot_id
                      JOIN product_product pp ON pp.id = s.product_id
                      JOIN product_template pt ON pt.id = pp.product_tmpl_id
                      JOIN uom_uom u ON u.id = pt.uom_id
                      JOIN next_bom nb ON nb.product_id = s.product_id
                                      AND (nb.company_id IS NULL OR nb.company_id = s.company_id)
                      LEFT JOIN planned pl ON pl.lot_id = s.lot_id
                      CROSS JOIN kg
                  ORDER BY s.lot_id, nb.company_id NULLS LAST
                )
                SELECT lot_id AS id, lot_id, product_id, company_id, bom_id, stage,
                       battery_chemistry_id, assay_state, in_date,
                       qty * to_kg AS on_hand_kg,
                       reserved * to_kg AS reserved_kg,
                       planned_kg,
                       (qty - reserved) * to_kg - planned_kg AS available_kg,
                       (stage != 'recover' OR assay_state != 'pending') AS ready
                  FROM queue
                 WHERE (qty - reserved) * to_kg - planned_kg > 0.0001
            )""", table=SQL.identifier(self._table), kg_id=kg.id))

    def _compute_waiting_days(self):
        now = fields.Datetime.now()
        for row in self:
            row.waiting_days = row.in_date and (now - row.in_date).days or 0

    def _compute_source_production_id(self):
        Production = self.env['mrp.production']
        for row in self:
            row.source_production_id = Production._ug_producers_of(row.lot_id).sorted('id')[:1]

    # ------------------------------------------------------------------
    # Create the next-stage order from selected lots
    # ------------------------------------------------------------------
    def action_create_production(self):
        if not self:
            raise UserError(_("Select the lots to process."))
        boms = self.bom_id
        if len(boms) != 1:
            raise UserError(_(
                "Select lots of the same product: one order is created per next-stage BoM (%s).",
                ", ".join(boms.mapped('display_name'))))
        if len(self.battery_chemistry_id) > 1:
            raise UserError(_("Lots of different chemistries cannot be processed in the same order (%s).",
                              ", ".join(self.battery_chemistry_id.mapped('name'))))
        if len(self.company_id) > 1:
            raise UserError(_("Select lots of a single company."))
        if boms.ug_stage == 'recover':
            pending = self.filtered(lambda r: r.assay_state != 'approved')
            if pending:
                raise UserError(_("The assay of these lots is not approved yet: %s",
                                  ", ".join(pending.lot_id.mapped('name'))))

        # read everything first: once the lots are planned, these rows leave the SQL view
        company = self.company_id or self.env.company
        quantities = [(row.lot_id, row.available_kg) for row in self]
        lot_names = ", ".join(lot.name for lot, _qty in quantities)
        production = self.env['mrp.production'].with_company(company).create({
            'product_id': boms.product_id.id or boms.product_tmpl_id.product_variant_id.id,
            'bom_id': boms.id,
            'company_id': company.id,
            'origin': lot_names,
            'ug_input_lot_line_ids': [Command.create({'lot_id': lot.id, 'qty_kg': qty}) for lot, qty in quantities],
        })
        if boms.ug_stage == 'recover':
            production.action_ug_compute_expected()
        else:
            production.ug_input_qty = sum(qty for _lot, qty in quantities)
        production.message_post(body=_("Created from the To Process queue for lots %s.", lot_names))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.production',
            'res_id': production.id,
            'views': [(False, 'form')],
        }
