# -*- encoding: utf-8 -*-
import time
# from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import except_orm
from odoo.exceptions import UserError
#import odoo.addons.decimal_precision as dp

# ===============================================================================
# # 类名:purchase_return_add_line
# # Copyright(c): Hailun
# # 功能描述: 添加销售折让明细向导
# # 创 建 人: Jacky
# # 创建日期: 2016/8/31
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class sale_rebate_add_line(models.TransientModel):
    _name = 'sale.rebate.add.line'

    is_check = fields.Boolean('选择', required=False, default=False)
    wizard_id = fields.Many2one('sale.rebate.add', '主档', required=False, ondelete='cascade')
    move_id = fields.Many2one('stock.move', '入库明细', required=False, readonly=True)
    sale_order = fields.Char(string='销售单号', required=False, readonly=True)
    sale_delivery = fields.Char(string='出货单号', required=False, readonly=True)
    product_id = fields.Many2one('product.product', string='货品编码', readonly=True, copy=False)
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True, copy=False)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True, copy=False)

    product_qty = fields.Float(string='折让数量', readonly=True, copy=False, default=1)
    product_uom = fields.Many2one('uom.uom', string='单位', readonly=True, copy=False)

# ===============================================================================
# # 类名:sale_return_add
# # Copyright(c): Hailun
# # 功能描述: 添加销售折让明细向导
# # 创 建 人: Jacky
# # 创建日期: 2016/8/31
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class sale_rebate_add(models.TransientModel):
    _name = 'sale.rebate.add'

    sale_rebate_id = fields.Many2one('sale.rebate', '销售折让', required=False, )
    partner_id = fields.Many2one('res.partner', string='客户', related='sale_rebate_id.partner_id',
                                 store=False, readonly=True, copy=False)
    is_all_check = fields.Boolean('全选', required=False, default=False)
    wizard_ids = fields.One2many('sale.rebate.add.line', 'wizard_id', '明细', required=False)
    product_id = fields.Many2one('product.product', '货品编码', required=False,)
    product_name = fields.Char('品名', required=False, default=False)
    sale_order = fields.Char(string='订单单号', required=False)
    sale_delivery = fields.Char(string='出货单号', required=False)

    @api.model
    def default_get(self, fields):
        if self._context is None: self._context = {}
        res = super(sale_rebate_add, self).default_get(fields)
        sale_rebate_ids = self._context.get('active_ids', [])
        active_model = self._context.get('active_model')

        if not sale_rebate_ids or len(sale_rebate_ids) != 1:
            return res
        assert active_model in ('sale.rebate'), '不是正确的来源对象！'
        sale_rebate_id, = sale_rebate_ids
        res.update(sale_rebate_id=sale_rebate_id)
        items = []
        res.update(wizard_ids=items)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    # 查询可退货明细
    def action_sale_rebate_query(self):
        for line in self:
            items = []
            if line.partner_id:
                return_sql = """select t1.id,t1.product_id,1 as product_qty,
                                t1.product_uom,t3.name||'-'||t1.sequence as sale_delivery,t7.name||'-'||t6.sequence as sale_order
                                from stock_move t1
                                left join stock_picking t3 on t1.picking_id=t3.id
                                left join stock_picking_type t4 on t4.id=t3.picking_type_id
                                left join sale_order_line t6 on t1.sale_line_id=t6.id
                                left join sale_order t7 on t6.order_id=t7.id
                                where t1.state='done' and t4.table_name in ('stock_delivery') and t1.product_qty>0
                                and t3.partner_id=%d
                """ % line.partner_id.id
                if line.product_id:
                    return_sql += " and t1.product_id=%d" % line.product_id.id
                if line.sale_order:
                    return_sql += " and t7.name like '%s'" % ('%%' + line.sale_order + '%%')
                if line.sale_delivery:
                    return_sql += " and t3.name like '%s'" % ('%%' + line.sale_delivery + '%%')
                return_sql += " order by t1.id desc"
                self._cr.execute(return_sql)
                for id, product_id,  product_qty, product_uom, sale_delivery, sale_order in self._cr.fetchall():
                    item = {
                        'move_id': id,
                        'product_id': product_id,

                        'product_qty': product_qty,
                        'product_uom': product_uom,
                        'sale_delivery': sale_delivery,
                        'sale_order': sale_order
                    }
                    items.append(item)
            line.wizard_ids.unlink()
            line.wizard_ids = items
        if self and self[0]:
            return self[0].wizard_view()

    # 将选中的明细添加到退货明细中
    def do_sale_rebate_line(self):
        self.ensure_one()
        lines = [l for l in self.wizard_ids if l.is_check is True]
        rebate_line_obj = self.env['sale.rebate.line']
        for line in lines:
            item = {
                'master_id': self.sale_rebate_id.id,
                'sequence': 1,
                'origin': line.move_id.origin,
                'rebate_move_id': line.move_id.id,
                'sale_line_id': line.move_id.sale_line_id and line.move_id.sale_line_id.id or False,
                'product_id': line.product_id.id,

                'name': line.product_name,
                'product_uom': line.product_uom and line.product_uom.id or False,
                'product_uom_qty': 1,
                'product_qty': 1,
                'price_unit': line.move_id.price_unit,
                'amount': line.move_id.price_unit,
            }
            rebate_line_obj.create(item)
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.view_sale_rebate_add_form')

        return {
            'name': _('对账明细表'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.rebate.add',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }
