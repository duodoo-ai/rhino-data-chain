# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.tools import float_compare, float_round


class stock_move(models.Model):
    _inherit = 'stock.move'
    _description = '库存异动明细'

    @api.depends('picking_id', 'sequence')
    def name_get(self):
        res = []
        for record in self:
            name = "%s - %s" % (record.picking_id.name, record.sequence)
            res.append((record.id, name))
        return res

    @api.depends('picking_type_id', 'checked_amount')
    def compute_checked_amount2(self):
         if self.picking_type_id:
             self.checked_amount2=self.picking_type_id.effect_statement*self.checked_amount

    def get_default_to_check_qty(self):

        return

    to_check_qty = fields.Float('对帐数量', digits='Product Unit of Measure',
                                help='用于对帐,采购对帐时为采购单位数量，销售出货则与交易单位数量相同')
    statement_ids = fields.One2many('account.statement.line', 'stock_move_id', '对帐明细')
    statement_name = fields.Char('对账单号', required=False, default=False)
    statement_date = fields.Date('最近对账日')
    checked_qty = fields.Float('对帐数量', digits='Product Unit of Measure')
    # canceled_qty = fields.Float('取消对帐数量', digits='Product Unit of Measure')
    checked_amount = fields.Float('对帐金额',  digits='Product Price',)
    checked_amount2 = fields.Float('对帐金额2',  digits='Product Price',compute='compute_checked_amount2')
    # canceled_amount = fields.Float('取消对帐金额',  digits='Product Price',)
    adjust_qty = fields.Float('调整数量', digits='Product Unit of Measure')
    adjust_amount = fields.Float('调整金额',  digits='Product Price',)
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure', )
    unchecked_amount = fields.Float('未对帐金额',  digits='Product Price',)
    statement_state = fields.Selection(base_cw.public.STATEMENT_STATE, '对帐状态', default='N')
    # 运费是只能对帐一次
    freight_amount = fields.Float('运费金额',  digits='Product Price',)
    freight_statement_state = fields.Selection(base_cw.public.STATEMENT_STATE, '运费对帐状态', default='N')

    # 本位币begin
    # local_amount = fields.Float('本币对帐金额', digits=(16, 2)) 在stock_ex已定义
    local_checked_amount = fields.Float('本币对帐金额',  digits='Product Price',)
    local_freight_amount = fields.Float('本币运费金额',  digits='Product Price',)
    local_adjust_amount = fields.Float('本币调整金额',  digits='Product Price', help='用于成本计算')
    local_total_amount = fields.Float('本币总金额',  digits='Product Price',)
    local_unchecked_amount = fields.Float('未对帐金额',  digits='Product Price',)
    # 本位币 end
    invoice_no = fields.Char('发票号码', default=False)
    invoiced_qty = fields.Float('开票数量', digits='Product Unit of Measure')
    invoiced_amount = fields.Float('已开票金额',  digits='Product Price', default=0)
    invoiced_freight_amount = fields.Float('已开票运费金额',  digits='Product Price',)
    last_invoice_date = fields.Date('最近开票日期')

    amount_discount = fields.Float(string='折扣金额',help=u"发票折扣金额")
    amount_discount_signed = fields.Float(string='本币折扣金额',help=u"发票折扣金额")

    @api.depends('amount', 'checked_amount', 'adjust_amount')
    def compute_unchecked_amount(self):
        """
        这里会有一个问题 如果 交易币别与对帐币别不一致时，这里的金额是错的 也只能看 本币未对帐金额，
        :return:
        """
        self.unchecked_amount = self.unchecked_qty*self.price_unit
        self.local_unchecked_amount = self.local_total_amount - self.local_checked_amount - self.local_adjust_amount
    def _action_done(self, cancel_backorder=False):
        """odoo10中是action_done,odoo13验证调用_action_done"""
        res = super(stock_move, self)._action_done(cancel_backorder)
        for record in self:
            record.action_account_statement_done()
        return res

    def action_account_statement_done(self):
        for record in self:
            for x in record.filtered(lambda v: v.picking_type_id.effect_statement):  # 1 or -1 需对帐的交易
                x.statement_state = 'N'
                x.freight_statement_state = 'N'
                x.unchecked_qty = x.to_check_qty = x.product_qty * int(x.picking_type_id.effect_statement)
                if x.picking_type_id.table_name in ('purchase_rebate', 'sale_fandian', 'sale_rebate','customer_support_policy') and x.amount < 0:
                    qty = x.unchecked_qty
                    x.unchecked_qty = x.to_check_qty = abs(qty)
                x.compute_unchecked_amount()

    @api.depends('product_qty', 'checked_qty', 'adjust_qty')
    def compute_unchecked_qty(self):
        # self.to_check_qty = self.product_qty * int(self.picking_type_id.effect_statement)-self.checked_qty or 0
        self.unchecked_qty = self.to_check_qty - self.checked_qty + self.adjust_qty

    @api.model
    def compute_statement_state(self, statement_source='A'):
        if statement_source == 'B':  # 运费
            if float_round(self.freight_amount, precision_rounding=0.01) > 0.00 and self.freight_statement_state != 'A':
                # 已对帐完毕
                freight_statement_state = 'A'
            elif self.statement_ids.filtered(lambda x: x.state in ('draft',) and x.statement_source == 'B'):
                # 对帐中
                freight_statement_state = 'R'
            else:
                # 标记为未对帐
                freight_statement_state = 'N'
            self.write(dict(freight_statement_state=freight_statement_state))
        else:
            statement_state = 'N'
            self.compute_unchecked_qty()
            if self.unchecked_qty == 0.0 and self.statement_state != 'A':
                # 已对帐完毕
                statement_state = 'A'
            elif 0.0 < abs(self.unchecked_qty) < abs(self.to_check_qty) and self.statement_state != 'P':
                # 部分对帐
                statement_state = 'P'
            elif self.unchecked_qty == self.to_check_qty and self.statement_state != 'N':
                # 未对帐
                statement_state = 'N'
            if self.statement_ids.filtered(lambda x: x.state in ('draft',) and x.statement_source == 'A'):
                # 对帐中
                statement_state = 'R'
            self.write({'statement_state':statement_state})

    @api.model
    def compute_checked_qty(self, statement_source='A'):
        results = self.statement_ids.filtered(lambda x: x.state in ('confirmed', 'done'))
        if results:
            # 发票作废金额&数量
            invalid_qty = sum(results.filtered(lambda s: s.statement_source != 'B').mapped('invalid_qty'))
            invalid_amount = sum(results.filtered(lambda s: s.statement_source != 'B').mapped('invalid_amount'))
            statement_name = max(results.mapped('master_id.name'))
            statement_date = max(results.mapped('master_id.date'))
            checked_qty = sum(results.filtered(lambda s: s.statement_source != 'B').mapped('qty')) + invalid_qty
            checked_amount = sum( results.filtered(lambda s: s.statement_source != 'B').mapped('amount')) + invalid_amount
            adjust_qty = sum(results.mapped('adjust_qty'))
            adjust_amount = sum(results.mapped('adjust_amount'))
            freight_amount = sum(results.filtered(lambda s: s.statement_source == 'B').mapped('amount'))
            local_checked_amount = sum(results.filtered(lambda s: s.statement_source != 'B').mapped('local_checked_amount'))
            local_freight_amount = sum(results.filtered(lambda s: s.statement_source == 'B').mapped('local_total_amount'))
            local_adjust_amount = sum(results.mapped('local_adjust_amount'))
            local_total_amount = sum(results.filtered(lambda s: s.statement_source != 'B').mapped('local_total_amount'))
        else:
            statement_name = False
            statement_date = False
            checked_qty = 0
            checked_amount = 0
            adjust_qty = 0
            adjust_amount = 0
            freight_amount = 0
            local_checked_amount = 0
            local_freight_amount = 0
            local_adjust_amount = 0
            local_total_amount = 0
        self.write(dict(statement_name=statement_name,
                        statement_date=statement_date,
                        checked_qty=checked_qty,
                        checked_amount=checked_amount,
                        adjust_qty=adjust_qty,
                        adjust_amount=adjust_amount,
                        freight_amount=freight_amount,
                        local_checked_amount=local_checked_amount,
                        local_freight_amount=local_freight_amount,
                        local_adjust_amount=local_adjust_amount,
                        local_total_amount=local_total_amount,
        ))
        self.compute_unchecked_qty()
        self.compute_unchecked_amount()
        self.compute_statement_state(statement_source=statement_source)

    @api.model
    def update_move_invoiced_amount_date(self):
        results = self.env['cncw.invoice.move.line'].search([('stock_move_id', '=', self.id), ('state', 'not in', ('cancel',))],
                                                          order='invoice_date')
        invoiced_amount = sum(results.mapped('total_amount'))
        invoice_no = results and results[-1].move_id.invoice_no or None
        last_invoice_date = results and results[-1].move_id.date_invoice or None
        invoiced_qty = sum(results.filtered(lambda s: s.account_statement_line_id.statement_source != 'B').mapped('quantity'))
        invoiced_freight_amount = sum(results.filtered(lambda s: s.account_statement_line_id.statement_source == 'B').mapped('total_amount'))
        amount_discount = sum(results.mapped('amount_discount'))
        amount_discount_signed = sum(results.mapped('amount_discount_signed'))
        self.write(dict(invoiced_amount=invoiced_amount,
                        invoice_no=invoice_no,
                        last_invoice_date=last_invoice_date,
                        invoiced_qty=invoiced_qty,
                        invoiced_freight_amount=invoiced_freight_amount,
                        amount_discount=amount_discount,
                        amount_discount_signed=amount_discount_signed,
        ))


class purchase_order(models.Model):
    _inherit = 'purchase.order'
    _description = '库存异动明细'

    def update_statement_invoice_state(self):
        pass

    def _update_statement_invoice_state(self):
        pass


class purchase_orde_line(models.Model):
    _inherit = 'purchase.order.line'
    _description = '库存异动明细'


    @api.model
    def compute_statement_state(self):
         pass
