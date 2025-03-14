# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
import json
#from odoo.addons import decimal_precision as dp
import werkzeug
from odoo.exceptions import UserError,ValidationError
from dateutil.relativedelta import relativedelta
import datetime
from odoo.tools.float_utils import float_compare
import logging
_logger = logging.getLogger(__name__)

class StockPickingInherit(models.Model):
    _inherit = "stock.picking"
    
    sale_return_id = fields.Many2one("sale.return", string=u"销售退货")
            
