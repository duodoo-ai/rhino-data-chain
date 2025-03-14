# -*- encoding: utf-8 -*-
import time
# from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import except_orm
from odoo.exceptions import UserError
#import odoo.addons.decimal_precision as dp

class purchase_rebate_add_line(models.TransientModel):
    _name = 'purchase.rebate.add.line'

    is_check = fields.Boolean('选择', required=False, default=False)
    wizard_id = fields.Many2one('purchase.rebate.add', '主档', required=False, ondelete='cascade')
    move_id = fields.Many2one('stock.move', '入库明细', required=False, readonly=True)
    purchase_order = fields.Char(string='采购单号', required=False, readonly=True)
    purchase_storage = fields.Char(string='入库单号', required=False, readonly=True)
    product_id = fields.Many2one('product.product', string='产品编码', readonly=True, copy=False)
    product_name = fields.Char(related='product_id.name', string='产品名称', readonly=True, copy=False)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True, copy=False)

    product_qty = fields.Float(string='折让数量', readonly=True, copy=False, default=1)
    product_uom = fields.Many2one('uom.uom', string='单位', readonly=True, copy=False)


class purchase_rebate_add(models.TransientModel):
    _name = 'purchase.rebate.add'

    purchase_rebate_id = fields.Many2one('purchase.rebate', '采购折让', required=False, )
    partner_id = fields.Many2one('res.partner', string='厂商', related='purchase_rebate_id.partner_id',
                                 store=False, readonly=True, copy=False)
    is_all_check = fields.Boolean('全选', required=False, default=False)
    wizard_ids = fields.One2many('purchase.rebate.add.line', 'wizard_id', '明细', required=False)
    product_id = fields.Many2one('product.product', '退货产品', required=False, )
    product_name = fields.Char('品名', required=False, default=False)
    purchase_order = fields.Char(string='采购单号', required=False)

    @api.model
    def default_get(self, fields):
        if self._context is None: self._context = {}
        res = super(purchase_rebate_add, self).default_get(fields)
        purchase_rebate_ids = self._context.get('active_ids', [])
        active_model = self._context.get('active_model')

        if not purchase_rebate_ids or len(purchase_rebate_ids) != 1:
            return res
        assert active_model in ('purchase.rebate'), '不是正确的来源对象！'
        purchase_rebate_id, = purchase_rebate_ids
        res.update(purchase_rebate_id=purchase_rebate_id)
        items = []
        res.update(wizard_ids=items)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    # 查询可退货明细
    def action_purchase_rebate_query(self):
        for line in self:
            items = []
            if line.partner_id:
                return_sql = """select t1.id,t1.product_id,1 as product_qty,
                                t1.product_uom,t3.name||'-'||t1.sequence as purchase_storage,t7.name||'-'||t6.sequence as purchase_order
                                from stock_move t1
                                left join stock_picking t3 on t1.picking_id=t3.id
                                left join stock_picking_type t4 on t4.id=t3.picking_type_id
                                left join purchase_order_line t6 on t1.purchase_line_id=t6.id
                                left join purchase_order t7 on t6.order_id=t7.id
                                left join product_product t8 on t1.product_id=t8.id
                                where t1.state='done' and t4.table_name in ('purchase_half_storage',
                                                                            'purchase_product_storage',
                                                                            'purchase_storage',
                                                                            'purchase_wire_storage',
                                                                            'purchase_outsourcing_storage')
                                and t3.partner_id=%d
                """ % line.partner_id.id
                move_ids = self.purchase_rebate_id.line_ids.mapped('rebate_move_id.id')
                if len(move_ids) == 1:
                    return_sql += """  and t1.id <> %s""" % move_ids[0]
                elif len(move_ids) > 1:
                    return_sql += """  and t1.id not in %s """ % (tuple(move_ids),)
                if line.product_id:
                    return_sql += " and t1.product_id=%d" % line.product_id.id
                if line.product_name:
                    return_sql += " and t8.name_template like '%%%s%%'" % line.product_name
                if line.purchase_order:
                    return_sql += " and t7.name like '%s'" % line.purchase_order
                return_sql += " order by t1.id desc"
                self._cr.execute(return_sql)
                for id, product_id,  product_qty, product_uom, purchase_storage, purchase_order in self._cr.fetchall():
                    item = {
                        'move_id': id,
                        'product_id': product_id,

                        'product_qty': product_qty,
                        'product_uom': product_uom,
                        'purchase_storage': purchase_storage,
                        'purchase_order': purchase_order
                    }
                    items.append(item)
            line.wizard_ids.unlink()
            line.wizard_ids = items
        if self and self[0]:
            return self[0].wizard_view()

    # 将选中的明细添加到退货明细中
    def do_purchase_rebate_line(self):
        self.ensure_one()
        lines = [l for l in self.wizard_ids if l.is_check is True]
        if len(lines) <= 0:
            raise UserError(_('系统提示!请选择折让明细!'))
        rebate_line_obj = self.env['purchase.rebate.line']
        for line in lines:
            item = {
                'master_id': self.purchase_rebate_id.id,
                'sequence': 1,
                'origin': line.move_id.origin,
                'rebate_move_id': line.move_id.id,
                'purchase_line_id': line.move_id.purchase_line_id and line.move_id.purchase_line_id.id or False,
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
        view = self.env.ref('cncw_statement.view_purchase_rebate_add_form')

        return {
            'name': _('添加采购折让明细'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'purchase.rebate.add',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }
