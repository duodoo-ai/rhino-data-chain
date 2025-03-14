# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class PurchaseChangeDownload(models.Model):
    _name="purchase.change.download"
    _description="采购变更下载"
    
    order_ids=fields.Many2many('purchase.change',string='销售变更单',required=True)
    type=fields.Selection([('purchase_change','采购变更单')],string='类型',required=True,default="purchase_change")
    
    def action_download(self):
        datas = {
             'data': json.dumps({'order_ids':self.order_ids.ids,'type':self.type}),
             'token':fields.Datetime.now(),
            }
        webapi_url = '/web/export/purchase_change_xls'
        return {
            'type' : 'ir.actions.act_url',
            'url'  : '{url}?{data}'.format(url=webapi_url, data=werkzeug.url_encode(datas)),
            'target': 'new',
            }
