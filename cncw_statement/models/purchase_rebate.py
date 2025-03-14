# -*- encoding: utf-8 -*-

import time, datetime
from odoo import models, fields, api, _
from odoo.exceptions import except_orm
#import odoo.addons.decimal_precision as dp
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.exceptions import UserError


class purchase_rebate(models.Model):
    _name = 'purchase.rebate'
    _inherit = 'stock.voucher'
    _description = '采购折让单'

    @api.depends("line_ids.amount", "line_ids.amount_tax", "line_ids.amount_total",
                 "line_ids.local_amount", "line_ids.local_amount_tax",
                 "line_ids.local_amount_total")
    def _compute_amout(self):
        for vc in self:
            vc.amount = sum(vc.line_ids.mapped('amount_untaxed'))
            vc.amount_tax = sum(x.amount_tax for x in vc.line_ids)
            vc.amount_total = sum(x.amount_total for x in vc.line_ids)
            vc.local_amount = sum(x.local_amount_untaxed for x in vc.line_ids)
            vc.local_amount_tax = sum(x.local_amount_tax for x in vc.line_ids)
            vc.local_amount_total = sum(x.local_amount_total for x in vc.line_ids)

    @api.depends("op_ids", "op_ids.product_qty")
    def _compute_total_qty(self):
        for res in self:
            res.total_qty = sum(op.product_qty for op in res.op_ids)

    partner_id = fields.Many2one('res.partner', '供应商', required=True, )
    line_ids = fields.One2many('purchase.rebate.line', 'master_id', '申请明细', required=False)
    op_ids = fields.One2many('purchase.rebate.operation', 'master_id', '作业明细', required=False)
    # 扩展栏位建立在下方
    total_qty = fields.Float('折让数量', digits='Product Unit of Measure', compute='_compute_total_qty',
                             store=True)
    amount = fields.Float('未税金额', digits='Product Price', compute='_compute_amout', store=True)
    amount_tax = fields.Float('税额', digits='Product Price', compute='_compute_amout', store=True)
    amount_total = fields.Float('合计', digits='Product Price', compute='_compute_amout', store=True)
    local_amount = fields.Float('本币未税金额', digits='Product Price', compute='_compute_amout', store=True)
    local_amount_tax = fields.Float('本币税额', digits='Product Price', compute='_compute_amout', store=True)
    local_amount_total = fields.Float('本币合计', digits='Product Price', compute='_compute_amout', store=True)
    tax_id = fields.Many2one('account.tax', '税别')
    currency_id = fields.Many2one('res.currency', '币别')
    exchange_rate = fields.Float('汇率', igits='Product Unit of Measure', default=1.0)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('purchase.rebate') or 'New'
        return super(purchase_rebate, self).create(vals)

    def copy(self, default=None):
        raise UserError(_('系统提示!不提供复制功能!'))
        res_id = super(purchase_rebate, self).copy(default)
        return res_id

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.currency_id = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.id or False
            self.tax_id = self.partner_id.account_tax_id and self.partner_id.account_tax_id.id or False
            self.exchange_rate = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.rate

    @api.model
    def prepare_purchase_rebate_op(self):
        rebate_op_obj = self.env['purchase.rebate.operation']
        for line in self.line_ids:
            line.product_qty = 1
            op_id = {
                'master_id': self.id,
                'voucher_line_id': line.id,
                'sequence': 1,
                'product_id': line.product_id.id,

                'name': line.product_name,
                'product_uom': line.product_uom and line.product_uom.id or False,
                'product_uom_qty': 1,
                'product_qty': 1,
                'location_id': line.location_dest_id.id,
                'location_dest_id': line.location_id.id,
            }
            rebate_op_obj.create(op_id)

    # 申请确认
    def action_confirm(self):
        '''
        1.首先产生picking,move,op明细
        2.调用原生的库存确认功能
        3.根据明细来判断是否走检验，不走检验的直接产生入库单，走检验的则产生检验的。判断的标记是根据is_ok来决定
          在产生资料的时候如果此货品检验则is_ok是false,否则是true
        :return:
        '''
        for pur_rebate in self:
            if not pur_rebate.line_ids:
                raise UserError(_('系统提示!折让明细不可以为空!'))
            if len(pur_rebate.line_ids.filtered(lambda y: y.price_unit == 0)) > 0:
                raise UserError(_('系统提示!折让金额不能为0!'))
            # 产生OP
            pur_rebate.prepare_purchase_rebate_op()
            self._cr.commit()
            sql = """ select create_stock_transfer_picking('%s',%s,%s,%s)""" % (
                self._table, pur_rebate.id, pur_rebate.picking_type_id.id, self.env.user.id)
            self._cr.execute(sql)
            sql1 = """ select cancel_reservation_stock_quant('%s',%s)""" % (self._table, pur_rebate.id)
            self._cr.execute(sql1)
            state = 'done'
            pur_rebate.write({"confirm_user_id": self._uid,
                              "confirm_date": fields.datetime.now(),
                              "done_user_id": self.env.user.id,
                              "done_date": fields.datetime.now(),
                              "state": state
                              })
            pur_rebate.line_ids.write(dict(state='done'))
            self._cr.commit()
            self.invalidate_cache()
            if pur_rebate.picking_id:
                pur_rebate.picking_id.write(dict(state='done'))
            for r in pur_rebate.line_ids:
                if r.move_id:
                    r.move_id.state = 'done'
                    for x in r.move_id.filtered(lambda v: v.picking_type_id.effect_statement):  # 1 or -1 需对帐的交易
                        x.statement_state = 'N'
                        x.freight_statement_state = 'N'
                        if x.amount > 0:
                            x.unchecked_qty = x.to_check_qty = x.product_qty * int(x.picking_type_id.effect_statement)
                        else:
                            x.unchecked_qty = x.to_check_qty = x.product_qty
                        if x.purchase_line_id and x.purchase_line_id.product_uos != x.product_uom:
                            qty = base_cw.public.get_converted_qty(self, x.product_id, x.product_uom, x.product_qty,
                                                                   x.purchase_line_id.product_uos)
                            if x.amount < 0:
                                x.unchecked_qty = x.to_check_qty = abs(qty)
                            else:
                                x.unchecked_qty = x.to_check_qty = qty * int(x.picking_type_id.effect_statement)
                        x.compute_unchecked_amount()

    # 取消申请
    def action_cancel_confirm(self):
        for pur_rebate in self:
            results = [x.move_id for x in pur_rebate.line_ids if x.move_id and x.move_id.statement_state != 'N']
            if results:
                raise UserError(_('系统提示!已有对帐不能取消申请!'))
            if pur_rebate.picking_id:
                sql = """ select delete_stock_transfer_picking('%s',%s,%s)""" % (
                self._table, pur_rebate.id, pur_rebate.picking_id.id)
                self._cr.execute(sql)
                sql1 = """ select cancel_reservation_stock_quant('%s',%s)""" % (self._table, pur_rebate.id)
                self._cr.execute(sql1)
            state = 'draft'
            pur_rebate.write({"confirm_user_id": self._uid,
                              "confirm_date": fields.datetime.now(),
                              "done_user_id": self.env.user.id,
                              "done_date": fields.datetime.now(),
                              "state": state
                              })
            pur_rebate.line_ids.write(dict(state='draft'))
            self._cr.commit()

    # 作废单据
    def action_cancel(self):
        super(purchase_rebate, self).action_cancel()
        self._cr.commit()

    @api.model
    def update_line_state(self, state='draft'):
        self.line_ids.write({"state": state})

    # 开启添加采购折让明细向导
    def action_purchase_rebate_add(self):
        context = {}
        context.update({'active_model': self._name,
                        'active_ids': self.ids,
                        'active_id': len(self.ids) and self.ids[0] or False,
                        })
        self.env.context = context
        self._cr.execute('delete from purchase_rebate_add where create_uid=%s', (self.env.user.id,))
        wizard_id = self.env['purchase.rebate.add'].create(
            {'purchase_rebate_id': len(self.ids) and self.ids[0] or False})
        return wizard_id.wizard_view()


# ===============================================================================
# # 类名:purchase_rebate_line
# # Copyright(c): Hailun
# # 功能描述: 采购退货单明细
# # 创 建 人: Jacky
# # 创建日期: 2016/3/18
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class purchase_rebate_line(models.Model):
    _name = 'purchase.rebate.line'
    _inherit = 'stock.voucher.line'
    _description = '采购退货单明细'

    @api.depends('master_id', 'sequence')
    def name_get(self):
        res = []
        for record in self:
            name = "%s - %s" % (record.master_id.name, record.sequence)
            res.append((record.id, name))
        return res

    @api.depends('price_unit', 'product_uom_qty', 'tax_id')
    def _compute_amount(self):
        """
        计算 金额、税额、总额
        :return:
        """
        for line in self:
            line.amount = line.currency_id.round(line.price_unit * line.product_uom_qty)
            vals = line.tax_id.compute_all(price_unit=line.price_unit, currency=line.currency_id,
                                           quantity=line.product_uom_qty, product=line.product_id,
                                           partner=line.master_id.partner_id)
            if vals:
                line.amount_untaxed = vals['total_excluded']
                line.amount_tax = vals['total_included'] - vals['total_excluded']
                line.amount_total = vals['total_included']

    @api.depends('price_unit', 'product_uom_qty', 'currency_id', 'exchange_rate', 'tax_id')
    def _compute_local_amount(self):
        """
        计算 本币单价、本币金额、本币税额、本币总额
        :return:
        """
        for line in self:
            vals_price = line.tax_id.compute_all(price_unit=line.price_unit, currency=line.currency_id,
                                                 quantity=1, product=line.product_id,
                                                 partner=line.master_id.partner_id)
            # 本币不含税单价
            line.local_price_untaxed = vals_price['total_excluded'] * line.exchange_rate
            # 本币单价(含不含税 要看税别)
            local_price = line.price_unit * line.exchange_rate
            line.local_price = local_price
            line.local_amount = line.currency_id.round(line.local_price * line.product_uom_qty)
            vals = line.tax_id.compute_all(price_unit=local_price, currency=line.master_id.company_id.currency_id,
                                           quantity=line.product_uom_qty, product=line.product_id,
                                           partner=line.master_id.partner_id)
            if vals:
                line.local_amount_untaxed = vals['total_excluded']
                line.local_amount_tax = vals['total_included'] - vals['total_excluded']
                line.local_amount_total = vals['total_included']

    @api.depends("purchase_line_id", 'master_id')
    def _compute_related_field(self):
        if self.purchase_line_id:
            self.tax_id = self.purchase_line_id.taxes_id.id
            self.currency_id = self.purchase_line_id.currency_id.id
            self.exchange_rate = self.purchase_line_id.order_id and self.purchase_line_id.order_id.exchange_rate or 1.0
        elif self.master_id:
            self.tax_id = self.master_id.tax_id and self.master_id.tax_id.id or False
            self.currency_id = self.master_id.currency_id and self.master_id.currency_id.id or False
            self.exchange_rate = self.master_id.exchange_rate or 1.0

    @api.depends("op_ids", "op_ids.net_weight")
    def _compute_op_net_weight(self):
        if self.op_ids:
            self.net_weight = sum(self.op_ids.mapped('net_weight'))

    @api.depends("op_ids", "op_ids.product_qty")
    def _compute_op_qty(self):
        self.product_uom_qty = self.product_qty = 1

    product_qty = fields.Float(compute="_compute_op_qty", store=True)
    product_uom_qty = fields.Float(compute="_compute_op_qty", store=True)
    master_id = fields.Many2one('purchase.rebate', '采购折让单', required=False, )
    op_ids = fields.One2many('purchase.rebate.operation', 'voucher_line_id', '作业明细', required=False)
    # 扩展栏位建立在下方
    rebate_move_id = fields.Many2one('stock.move', '入库明细', required=False, )
    statement_state = fields.Selection(base_cw.public.STATEMENT_STATE, related="move_id.statement_state",
                                       string='对帐状态', readonly=True, )
    purchase_line_id = fields.Many2one('purchase.order.line', string='采购明细',
                                       related='rebate_move_id.purchase_line_id', store=True, readonly=True, copy=False)
    net_weight = fields.Float('净量', digits=(16, 3), compute="_compute_op_net_weight", readonly=True, store=True)
    amount = fields.Float('金额',  digits='Product Price', compute='_compute_amount', store=True)
    amount_untaxed = fields.Float('不含税金额',  digits='Product Price', compute='_compute_amount', store=True)
    amount_tax = fields.Float('税额',  digits='Product Price', compute='_compute_amount', store=True)
    amount_total = fields.Float('总金额',  digits='Product Price', compute='_compute_amount', store=True)

    local_price = fields.Float('本币单价',  digits='Product Price', compute='_compute_local_amount', store=True)
    local_price_untaxed = fields.Float('本币不含税单价',  digits='Product Price', compute='_compute_local_amount',
                                       store=True)
    local_amount = fields.Float('本币金额',  digits='Product Price', compute='_compute_local_amount', store=True)
    local_amount_untaxed = fields.Float('本币不含税金额',  digits='Product Price', compute='_compute_local_amount',
                                        store=True)
    local_amount_tax = fields.Float('本币税额',  digits='Product Price', compute='_compute_local_amount',
                                    store=True)
    local_amount_total = fields.Float('本币总金额',  digits='Product Price', compute='_compute_local_amount',
                                      store=True)
    tax_id = fields.Many2one('account.tax', '税别', compute="_compute_related_field", store=True, )
    currency_id = fields.Many2one('res.currency', '币别', compute="_compute_related_field", store=True, )
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', compute="_compute_related_field",
                                 store=True, )

    def refresh_state(self):
        self.ensure_one()
        if len(self.op_ids) == 0:
            self.state = 'draft'

    @api.model
    def create(self, vals):
        self._cr.execute('select max(sequence) from purchase_rebate_line' +
                         ' where master_id=%s', (vals['master_id'],))
        seq = self._cr.fetchone()[0]
        vals['sequence'] = seq and seq + 1 or 1
        return super(purchase_rebate_line, self).create(vals)

    # 生成折让明细
    def prepare_voucher_line_operation(self, line_id, return_id, location_id, product_qty, lot_id, package_id):
        self = self.with_context(no_recompute=True)
        operation_obj = self.env['purchase.rebate.operation']
        newdate = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())),
        # 创建数据交易明细数据
        new_op_ids = line_id.prepare_stock_voucher_operation(return_id, product_qty, lot_id,
                                                             date=newdate,
                                                             package_id=package_id)
        op_id = operation_obj.create(new_op_ids)
        self = self.with_context(no_recompute=False)
        sum_qty = sum([r.product_qty for r in line_id.op_ids])
        if sum_qty > line_id.product_uom_qty:
            line_id.product_uom_qty = sum_qty
        if line_id.state != 'in_progress':
            line_id.write({'state': 'in_progress'})
        return_id.refresh_state()
        self._cr.commit()
        return True


# ===============================================================================
# # 类名:purchase_rebate_operation
# # Copyright(c): Hailun
# # 功能描述: 采购折让单OP明细
# # 创 建 人: Jacky
# # 创建日期: 2016/8/31
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class purchase_rebate_operation(models.Model):
    _name = 'purchase.rebate.operation'
    _inherit = 'stock.voucher.operation'
    _description = '采购折让单OP明细'

    master_id = fields.Many2one('purchase.rebate', '采购折让单', required=False, ondelete="cascade")
    voucher_line_id = fields.Many2one('purchase.rebate.line', '采购折让单明细', required=False, ondelete="cascade")

    # 扩展栏位建立在下方

    def unlink(self):
        res = super(purchase_rebate_operation, self).unlink()
        return res

    @api.model
    def create(self, vals):
        self._cr.execute('select max(sequence) from purchase_rebate_operation' +
                         ' where master_id=%s', (vals['master_id'],))
        seq = self._cr.fetchone()[0]
        vals['sequence'] = seq and seq + 1 or 1
        return super(purchase_rebate_operation, self).create(vals)
