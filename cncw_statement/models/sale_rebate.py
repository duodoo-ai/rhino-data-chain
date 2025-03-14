# -*- encoding: utf-8 -*-

import time, datetime
from odoo import models, fields, api, _
from odoo.exceptions import except_orm

from odoo.tools import float_compare, float_round



# class stock_picking(models.Model):
#     _inherit = 'stock.picking'
#     _description = '销售折让'
#     @api.multi
#     def action_rebate_confirm(self):
#         self.write(dict(state='done',date_done=fields.Date.context_today(self)))
#         self.move_lines.line_rebate_confirm(state='done')
#
#     @api.multi
#     def action_cancel_rebate_confirm(self):
#         self.write(dict(state='draft'))
#         self.move_lines.line_rebate_confirm()
#
#     @api.one
#     def create_sale_rate_line(self,sale_line_id,product_id,price_unit):
#         move_obj = self.env['stock.move']
#         rebate_op_obj = self.env['stock.pack.operation']
#         link_obj = self.env['stock.move.operation.link']
#         move_id = move_obj.create({
#             "picking_id": self.id,
#             "picking_type_id": self.picking_type_id.id,
#             "origin": sale_line_id and sale_line_id.order_id.name,
#             "product_id": product_id.id,
#             "product_uom_qty": 1,
#             "location_id": self.picking_type_id.default_location_src_id.id,
#             "location_dest_id": self.picking_type_id.default_location_dest_id.id,
#             "product_uom": product_id.uom_id and product_id.uom_id.id or False,
#             "name": product_id.name or False,
#             "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
#             "sale_line_id": sale_line_id and sale_line_id.id or False,
#             "partner_id": self.partner_id.id,
#             'price_unit': price_unit
#         })
#         op_id = {
#             'product_id': product_id.id,
#             "picking_id": self.id,
#             'name': product_id.name,
#             'product_uom_id': product_id.uom_id and product_id.uom_id.id or False,
#             'qty_done': 1,
#             'product_qty': 1,
#             "location_id": self.picking_type_id.default_location_src_id.id,
#             "location_dest_id": self.picking_type_id.default_location_dest_id.id,
#         }
#         op_id = rebate_op_obj.create(op_id)
#         link_obj.create(dict(move_id=move_id.id,
#                              operation_id=op_id.id,
#                              qty=1))
#
# class stock_move(models.Model):
#     _inherit = 'stock.move'
#
#     product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
#     product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True)
#
#     @api.multi
#     def line_rebate_confirm(self,state='draft'):
#         self.action_res_done()
#         self.action_account_statement_done()
#         self.write(dict(state=state))