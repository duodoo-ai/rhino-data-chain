# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class PurchaseDownloadSelect(models.Model):
    _name="purchase.download.select"
    _description="采购合同下载"
    
    order_ids=fields.Many2many('purchase.order',string='采购订单',required=True)
    type=fields.Selection([('complete','采购合同')],string='类型',required=True,default="complete")
    
    def action_download(self):
        datas = {
             'data': json.dumps({'order_ids':self.order_ids.ids,'type':self.type}),
             'token':fields.Datetime.now(),
            }
        webapi_url = '/web/export/purchase_xls'
        return {
            'type' : 'ir.actions.act_url',
            'url'  : '{url}?{data}'.format(url=webapi_url, data=werkzeug.url_encode(datas)),
            'target': 'new',
            }
