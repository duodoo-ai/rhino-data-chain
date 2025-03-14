# -*- encoding: utf-8 -*-
from . import public
from . import models
from . import accounts
from . import wizard
from odoo import api, SUPERUSER_ID

def _update_rules(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    purchases = env['purchase.order'].search([('state','!=','cancel')])
    for record in purchases:
        record.tax_id = record.partner_id.account_tax_id.id