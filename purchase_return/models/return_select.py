# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ReturnSelect(models.Model):
    _name="return.select"
    _description="退货查询"
    
            
#     name=fields.Char(string='名称',required=True)
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True, default=lambda self: self.env.company.id)
    purchase_id=fields.Many2one('purchase.order',string='采购订单',domain=[('state','=','done')])
    partner_id = fields.Many2one('res.partner', string='供应商',related="purchase_id.partner_id")
    purchase_return_id=fields.Many2one('purchase.return',string='采购退货单')
    purchase_lines=fields.Many2many("purchase.order.line", string='采购明细')
    
    def action_confirm(self):
        self.purchase_return_id.lines.unlink()
        for line in self.purchase_lines:
            vals={
                'order_id':self.purchase_return_id.id,
                'purchase_line_id':line.id,
                'return_qty':line.qty_received
                }
            self.env['purchase.return.line'].create(vals)
#         self.purchase_return_id.lines=self.purchase_lines.ids
        
#     @api.onchange('purchase_id')
#     def onchange_purchase_id(self):
#         if self.purchase_id:
#             self.purchase_lines=self.purchase_id.order_line.ids
    