# -*- encoding: utf-8 -*-
import time

from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import UserError


class sale_rebate_wizard(models.TransientModel):
    _name = 'sale.rebate.wizard'

    picking_id = fields.Many2one('stock.picking', '退货单主档', )
    partner_id = fields.Many2one('res.partner', related='picking_id.partner_id', string='供应商')
    wizard_ids = fields.One2many('sale.rebate.wizard.line', 'wizard_id', '明细')
    product_id = fields.Many2one('product.product', '产品', )
    sale_order_no = fields.Char(string='订单单号', )
    product_name = fields.Char(string='品名', )

    def action_query(self):
        for line in self:
            items = []
            if line.partner_id:
                str_move = """select t1.id,t1.product_id,0 as price_unit,
                                       t1.product_uom,t3.name as picking_name,t7.name as sale_order_name,t1.sale_line_id
                                from stock_move t1 left join stock_picking_type t2 on t1.picking_type_id=t2.id
                                                    left join stock_picking t3 on t1.picking_id=t3.id
                                                    left join sale_order_line t6 on t1.sale_line_id=t6.id
                                                    left join sale_order t7 on t6.order_id=t7.id
                                                    left join product_product t8 on t1.product_id=t8.id
                                where t1.state='done'
                                  and t2.table_name='stock_delivery'
                                  and coalesce(t1.product_uom_qty,0) > 0
                                  and t3.partner_id=%d""" % line.partner_id.id
                if line.product_id:
                    str_move += " and t1.product_id=%d" % line.product_id.id
                if line.sale_order_no:
                    str_move += " and t7.name like '%s'" % ("%%" + line.sale_order_no + "%%")

                if line.product_name:
                    str_move += " and t8.name_template like '%s'" % ("%%" + line.product_name + "%%")
                str_move += " order by t1.id desc"
                self._cr.execute(str_move)
                for id, product_id, price_unit, product_uom, picking_name, sale_order_name, sale_line_id in self._cr.fetchall():
                    item = {
                        'move_id': id,
                        'product_id': product_id,

                        'price_unit': price_unit,
                        'uom_id': product_uom,
                        'picking_name': picking_name,
                        'sale_order_name': sale_order_name,
                        'sale_line_id': sale_line_id,
                    }
                    items.append(item)
            line.wizard_ids.unlink()
            line.wizard_ids = items
        return self.wizard_view()

    def action_confirm(self):
        lines = [l for l in self.wizard_ids if l.is_check is True]
        if len(lines) <= 0:
            raise UserError(_('警告!请选择!'))

        for line in lines:
            self.picking_id.create_sale_rate_line(line.sale_line_id,line.product_id,line.price_unit)
        return {'type': 'ir.actions.act_window_close'}



    # @api.model
    # def prepare_sale_rebate_op(self):
    #     rebate_op_obj = self.env['stock.quant.pack']
    #     for line in self.line_ids:
    #         line.product_qty = 1
    #         op_id = {
    #             'sequence': 1,
    #             'product_id': line.product_id.id,
    #             "picking_id": self.picking_id.id,
    #             'name': line.product_name,
    #             'product_uom_id': line.product_uom and line.product_uom.id or False,
    #             'qty_done': 1,
    #             'product_qty': 1,
    #             'location_id': line.location_dest_id.id,
    #             'location_dest_id': line.location_id.id,
    #         }
    #         rebate_op_obj.create(op_id)

    def wizard_view(self):
        view = self.env.ref('cncw_statement.view_sale_rebate_wizard_form')
        return {
            'name': _('采购退货'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.rebate.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class sale_rebate_wizard_line(models.TransientModel):
    _name = 'sale.rebate.wizard.line'

    wizard_id = fields.Many2one('sale.rebate.wizard', '主档', ondelete='cascade')
    move_id = fields.Many2one('stock.move', '入库明细', readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', string='订单明细', )
    sale_order_name = fields.Char(string=u"订单编号", readonly=True)
    picking_name = fields.Char(string='出库单号', readonly=True)
    product_id = fields.Many2one('product.product', string='产品编码', readonly=True, copy=False)

    product_name = fields.Char(related='product_id.name', string='产品名称', readonly=True, copy=False)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True, copy=False)
    price_unit = fields.Float('折扣金额', digits=(16, 2))
    uom_id = fields.Many2one('uom.uom', string='单位', readonly=True, copy=False)
    is_check = fields.Boolean('选择', required=False, default=False)
