# Tells Odoo which python files inside models/ to load, in a safe order:
# the approval mixin first (other files build on top of it), then the new
# EPC documents in pipeline order, then the extensions to standard Odoo models.
from . import epc_approval_mixin
from . import epc_site_survey
from . import epc_feasibility
from . import epc_boq
from . import epc_material_request
from . import epc_dpr
from . import epc_quality_checkpoint
from . import epc_quality_check
from . import epc_commissioning
from . import epc_handover
from . import epc_amc_contract
from . import crm_lead
from . import sale_order
from . import project_project
from . import project_task
from . import purchase_order
from . import stock_picking
from . import helpdesk_ticket
from . import epc_dashboard
