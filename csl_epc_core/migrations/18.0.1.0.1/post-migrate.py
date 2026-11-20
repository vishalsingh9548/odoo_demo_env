# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Delivery / Freight terms moved to the EPC-only fields epc_delivery_type / epc_freight_type:
    copy what was typed on Solar EPC orders so nothing is lost."""
    cr.execute("""
        UPDATE sale_order
           SET epc_delivery_type = delivery_type
         WHERE is_epc_order AND delivery_type IN ('immediate', 'scheduled') AND epc_delivery_type IS NULL
    """)
    cr.execute("""
        UPDATE sale_order
           SET epc_freight_type = freight_type
         WHERE is_epc_order AND freight_type IN ('extra', 'included') AND epc_freight_type IS NULL
    """)
