# -*- encoding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from .. import public

_logger = logging.getLogger(__name__)

TABLE_NAME_TYPE = [('none', '内部调拨'), ('purchase_storage', '采购入库单'), ('purchase_storage_return', '采购退货单'),
                   ('purchase_rebate', '采购折扣单'),
                   ('purchase_receive', '采购收货单'), ('purchase_receive', '采购收货单'), ('purchase_quality', '采购质检'),
                   ('stock_allot', '仓库调拨单'), ('sale_return_storage', '销售退货单'), ('customer_support_policy', '销售费用政策'),
                   ('sale_rebate', '销售折扣单'),
                   ('stock_delivery', '销售出库单'), ('stock_inventory', '盘点单'), ('mrp_in', '生产入库单'),
                   ('mrp_material', '生产投料单'),
                   ('rework_material', '重工/超领料单'), ('rework_in', '重工入库单'), ('sale_fandian', '销售返点'),
                   ('outsourcing_in', '外协入库单'), ('outsourcing_material', '外协发料单'), ('outsourcing_return', '外协退料单'),
                   ('in_other', '其他入库单'), ('out_other', '其他出库单'),
                   ]


class stock_picking_type(models.Model):
    _inherit = 'stock.picking.type'
    _description = '库存作业类型'

    table_name = fields.Selection(TABLE_NAME_TYPE, '作业类型编号',
                                  help='此栏位用于记录作业类型的表名，目的是作为库存单据基类调用方法的参数使用')
    note = fields.Text('说明', )
    effect_qty = fields.Integer('对库存数量影响', default=0, help=u"退货为减项-1 其它为加 1")
    effect_statement = fields.Integer('对财务对帐影响', default=0, help='退货为减项-1,不参与对帐为0,采购入库销售出货１')
    cost_mode = fields.Selection([('A1', '参与成本入库'),
                                  ('A2', '参与成本出库'),
                                  ('B1', '不参与成本入库'),
                                  ('B2', '不参与成本出库'),
                                  ], '成本模型', )

class StockPickingType(models.Model):
    _inherit = 'stock.picking'

    def action_res_update_price(self):
        for record in self:
            if record.move_ids_without_package:
                move = record.move_ids_without_package
                move.action_res_done()


class StockMove(models.Model):
    _inherit = 'stock.move'
    _description = '库存异动明细'

    sequence = fields.Integer('项次')
    net_weight = fields.Float('重量', digits='Stock Weight')

    amount = fields.Float('金额', digits='Account',
                          help=u"由采购(外协)入库确认时，从入库申请单local_amout 写入")
    amount_untaxed = fields.Float('未税金额', digits='Account', )
    amount_total = fields.Float('总金额', digits='Account', )

    local_price = fields.Float('成本单价', digits='Product Price')
    local_price_untaxed = fields.Float('对账不含税单价', digits='Product Price',
                                       help=u"本币未税单价，在采购(外协)入库和销货出库时计算此栏位值,在仓库确认时写入 用于成本计算")
    local_amount = fields.Float(string='金额', digits='Account',
                                help=u"本币金额=local_price*product_qty")

    local_amount_untaxed = fields.Float(string='金额', digits='Account',
                                        help=u"本币未税金额=local_price_untaxed*product_qty")
    local_amount_total = fields.Float('本币总金额', digits='Account', )

    sale_line_id = fields.Many2one('sale.order.line', '销售订单明细',
                                   copy=False)  # , compute="_comput_sale_line_id", store=True
    is_gift = fields.Boolean('为赠品', default=False)
    tax_id = fields.Many2one('account.tax', '税别')
    currency_id = fields.Many2one('res.currency', '币别')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0)
    amount_tax = fields.Float(string='税', store=True, readonly=True, compute='_compute_amount', digits=(16, 6))
    local_amount_tax = fields.Float('本币税额',  digits='Product Price', compute='_compute_local_amount',
                                    store=True)

    @api.depends('price_unit', 'product_uom_qty', 'tax_id')
    def _compute_amount(self):
        """
        计算 金额、税额、总额
        :return:
        """
        for line in self:
            # 计算销售订单明细成本
            if line.picking_type_id.table_name in (
                    'stock_delivery', 'sale_return_storage', 'sale_rebate',
                    'customer_support_policy') and line.sale_line_id:
                line.tax_id = line.sale_line_id.order_id.tax_id and line.sale_line_id.order_id.tax_id.id or False
                line.currency_id = line.sale_line_id.order_id.partner_currency_id and line.sale_line_id.order_id.partner_currency_id.id or self.env.user.company_id.currency_id.id
                line.exchange_rate = line.currency_id.rate
                partner_id = line.sale_line_id.order_id.partner_id
            # 计算采购订单明细成本
            elif line.picking_type_id.table_name in ('purchase_storage', 'purchase_receive', 'purchase_storage_return',
                                                   'purchase_rebate') and line.purchase_line_id:
                if line.product_id == line.purchase_line_id.product_id:
                    line.price_unit = line.purchase_line_id.price_unit

                line.tax_id = line.purchase_line_id.order_id.tax_id and line.purchase_line_id.order_id.tax_id.id or False
                line.currency_id = line.purchase_line_id.order_id.currency_id and line.purchase_line_id.order_id.currency_id.id or self.env.user.company_id.currency_id.id
                line.exchange_rate = line.currency_id.rate
                partner_id = line.purchase_line_id.order_id.partner_id
            else:
                partner_id = line.picking_id.partner_id
            line.amount = line.currency_id.round(line.price_unit * line.product_uom_qty) if line.currency_id else 0
            vals = line.tax_id.compute_all(price_unit=line.price_unit, currency=line.currency_id,
                                           quantity=line.product_uom_qty, product=line.product_id,
                                           partner=partner_id)
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
            # _logger.info('===计算成本价格2====')
            if line.picking_type_id.table_name in ('stock_delivery', 'sale_return_storage', 'sale_rebate',
                                                   'purchase_storage', 'purchase_receive', 'purchase_storage_return',
                                                   'purchase_rebate','outsourcing_in') and (line.sale_line_id or line.purchase_line_id):
                vals_price = line.tax_id.compute_all(price_unit=line.price_unit,
                                                     currency=line.picking_id.company_id.currency_id,
                                                     quantity=1,
                                                     product=line.product_id,
                                                     partner=line.picking_id.partner_id)
                # 本币不含税单价 用于成本计算
                # line.local_price_untaxed = vals_price['total_excluded'] * line.exchange_rate
                # 本币不含税单价 用于成本计算
                line.local_price_untaxed = vals_price['total_excluded'] / line.exchange_rate
                # 本币单价(含不含税 要看税别)
                # local_price = line.price_unit * line.exchange_rate
                local_price = line.price_unit / line.exchange_rate
                line.local_price = local_price
                line.local_amount = line.local_price * line.product_uom_qty
                vals = line.tax_id.compute_all(price_unit=local_price,
                                               currency=line.picking_id.company_id.currency_id,
                                               quantity=line.product_uom_qty,
                                               product=line.product_id,
                                               partner=line.picking_id.partner_id)
                if vals:
                    line.local_amount_untaxed = vals['total_excluded']
                    line.local_amount_tax = vals['total_included'] - vals['total_excluded']
                    line.local_amount_total = vals['total_included']

    def _action_done(self, cancel_backorder=False):
        res = super(StockMove, self)._action_done(cancel_backorder)
        self.action_res_done()
        return res

    def create_sale_rate_line(self, sale_line_id, product_id, price_unit):
        """
        在对帐模组复写
        @return:
        """
        pass

    def action_account_statement_done(self):
        """
        在对帐模组复写
        @return:
        """
        pass

    def action_res_done(self):
        for x in self.filtered(lambda v: v.picking_type_id.effect_statement):  # 1 or -1 需对帐的交易
            x._compute_amount()
            x._compute_local_amount()


class StockIncoterms(models.Model):
    _name = 'stock.incoterms'
    _inherit = ['mail.thread']
    _description = '价格条款'

    active = fields.Boolean(
        'Active', default=True,
        help="By unchecking the active field, you may hide an INCOTERM you will not use.")

    code = fields.Char('编码', size=12, default=False, tracking=True)
    name = fields.Char('名称', default=False, tracking=True)
    name_en = fields.Char('英文名', required=False, )
    name_cn = fields.Char('中文名', required=False, )
    note = fields.Text('备注')

    def create(self, values):
        public.check_unique(self, [0], values)
        res_id = super(StockIncoterms, self).create(values)
        return res_id

    def copy(self, default=None):
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(StockIncoterms, self).copy(default)

    def write(self, vals):
        self.ensure_one()
        public.check_unique(self, [0], vals)
        res = super(StockIncoterms, self).write(vals)
        return res


class TransportMode(models.Model):
    _name = 'transport.mode'
    _inherit = 'mail.thread'
    _description = '货运方式'

    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for event in self:
            name = event.code and event.code + " - " or ""
            name += event.name and event.name or ""
            result.append((event.id, name))
        return result

    code = fields.Char('编码', required=True, copy=False, tracking=True)
    name = fields.Char('名称', required=True, copy=False, tracking=True)
    note = fields.Text('备注', required=False, default=False)
    active = fields.Boolean('启用', required=False, default=True)
    _sql_constraints = [('code_unique', 'unique (code)', '货运方式的编码不能重复!'),
                        ('name_unique', 'unique (name)', '货运方式的名称不能重复!'), ]

    def create(self, values):
        public.check_unique(self, [0], values)
        res_id = super(TransportMode, self).create(values)
        return res_id

    def copy(self, default=None):
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(TransportMode, self).copy(default)

    def write(self, vals):
        public.check_unique(self, [0], vals)
        res = super(TransportMode, self).write(vals)
        return res
