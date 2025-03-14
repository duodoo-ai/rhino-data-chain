# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
import logging
_logger = logging.getLogger(__name__)



class SaleOrderInherit(models.Model):
    _inherit = "sale.order"
    _check_company_auto = True

    file=fields.Binary(string='附件')
    file_name = fields.Char(string='文件名')

    picking_status = fields.Selection(
        [
            ("done", "完成"),  # order done
            ("in_progress", "等待发货"),
            ("cancel", "取消"),
        ],
        default="in_progress",
        string="发货状态",
        copy=False,
        tracking=True,
        store=True,
    )

    def _compute_picking_status(self):
        for order in self:
            if order.state == "cancel":
                order.picking_status = "cancel"
            elif order.state in ["draft", "sent"]:
                order.picking_status = "in_progress"
            else:
                if not order.picking_ids:
                    order.picking_status = "in_progress"
                else:
                    state = "done"
                    for picking in order.picking_ids:
                        if picking.state not in ["done", "cancel"]:
                            state = "in_progress"
                    order.picking_status = state

    
class SaleOrderLineInherit(models.Model):
    _inherit="sale.order.line"
    _check_company_auto = True
    
    @api.depends('qty_delivered','product_uom_qty')
    def _compute_left_qty(self):
        for line in self:
            line.left_qty = line.product_uom_qty - line.qty_delivered
            
    qty_available=fields.Float(string='库存数量',related="product_id.qty_available",check_company=True)
    team_id=fields.Many2one('crm.team',string='销售团队',related="order_id.team_id",store=True)
    date_order=fields.Datetime(string='单据日期',related="order_id.date_order",store=True)
    commitment_date=fields.Datetime(string='交货日期',related="order_id.commitment_date",store=True)
    left_qty=fields.Float(string='未发数量',compute="_compute_left_qty")
