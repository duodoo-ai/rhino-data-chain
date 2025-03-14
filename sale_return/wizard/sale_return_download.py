# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class SaleReturnDownload(models.Model):
    _name="sale.return.download"
    _description="销售退货下载"
    
    order_ids = fields.Many2many('sale.return',string='销售退货单',required=True)
    type = fields.Selection([('return','销售退货单')],string='类型',required=True,default="return")
    
    def action_download(self):
        datas = {
             'data': json.dumps({'order_ids':self.order_ids.ids,'type':self.type}),
             'token':fields.Datetime.now(),
            }
        webapi_url = '/web/export/sale_return_xls'
        return {
            'type' : 'ir.actions.act_url',
            'url'  : '{url}?{data}'.format(url=webapi_url, data=werkzeug.url_encode(datas)),
            'target': 'new',
            }
