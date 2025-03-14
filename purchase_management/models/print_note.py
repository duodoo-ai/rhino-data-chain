# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class PurchasePrintNote(models.Model):
    _name = "purchase.print.note"
    _description=u"采购打印条款"
    
    name=fields.Char(string=u"名称",required=True)
    print_note=fields.Text(string='条款',required=True)
    