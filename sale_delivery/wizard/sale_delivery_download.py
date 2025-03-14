# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class SaleDeliveryDownload(models.Model):
    _name="sale.delivery.download"
    _description="发货通知单下载"
    
    order_ids=fields.Many2many('sale.delivery',string='发货通知单',required=True)
    type=fields.Selection([('sale_delivery','销售发货单')],string='类型',required=True,default="sale_delivery")
    
    def action_download(self):
        datas = {
             'data': json.dumps({'order_ids':self.order_ids.ids,'type':self.type}),
             'token':fields.Datetime.now(),
            }
        webapi_url = '/web/export/sale_delivery_xls'
        return {
            'type' : 'ir.actions.act_url',
            'url'  : '{url}?{data}'.format(url=webapi_url, data=werkzeug.url_encode(datas)),
            'target': 'new',
            }
