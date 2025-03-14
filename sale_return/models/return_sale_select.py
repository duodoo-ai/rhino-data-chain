# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ReturnSaleSelect(models.Model):
    _name="return.sale.select"
    _description="销售退货查询"
    _check_company_auto = True
    
            
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True, default=lambda self: self.env.company.id)
    sale_id=fields.Many2one('sale.order',string='销售订单',domain=[('state','in',['sale','done'])])
    partner_id = fields.Many2one('res.partner', string='客户',related="sale_id.partner_id")
    sale_return_id=fields.Many2one('sale.return',string='销售退货单')
    sale_lines=fields.Many2many("sale.order.line", string='销售明细')
    
    def action_confirm(self):
        self.sale_return_id.lines.unlink()
        for line in self.sale_lines:
            vals={
                'order_id':self.sale_return_id.id,
                'sale_line_id':line.id,
                'product_id':line.product_id.id,
                'name':line.product_id.name or '',
                'qty_delivered':line.qty_delivered,
                'product_uom':line.product_uom.id,
                'price_unit':line.price_unit,
                'tax_id':line.tax_id.ids,
                'return_qty':line.qty_delivered
                }
            self.env['sale.return.line'].create(vals)
        
