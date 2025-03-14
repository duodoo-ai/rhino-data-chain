# -*- encoding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.translate import _
_logger = logging.getLogger(__name__)


class AccountStatementDeliveryWizard(models.TransientModel):
    _name = 'account.statement.delivery.wizard'

    master_id = fields.Many2one('account.statement', '对帐单', )
    statement_type = fields.Selection(base_cw.public.STATEMENT_TYPE, string='对帐类型', readonly=True,
                                      related='master_id.statement_type')
    partner_id = fields.Many2one('res.partner', string='合作伙伴', related='master_id.partner_id', readonly=True)
    picking_type_id = fields.Many2many('stock.picking.type', string='出入库类型',
                                       domain=[('table_name', 'in', ('stock_delivery',
                                                                     'sale_return_storage',
                                                                     'sale_rebate',
                                                                     'sale_fandian',
                                                                     'customer_support_policy'))])
    start_date = fields.Date('对帐起日')
    end_date = fields.Date('对帐迄日')
    statement_source = fields.Selection(base_cw.public.STATEMENT_SOURCE, '对帐对象', default='A')
    picking_name = fields.Char('出入库单号')
    so_name = fields.Char('订单编号')
    product_name = fields.Char('产品信息')
    is_all_check = fields.Boolean('全选', default=False)
    note = fields.Char('说明', required=False, readonly=True)
    categ_id = fields.Many2one('product.category', '货品分类')
    line_ids = fields.One2many('account.statement.delivery.wizard.line', 'master_id', '明细', )
    product_wizard_ids = fields.One2many('account.statement.receive.wizard.product.line', 'master_id')
    picking_wizard_ids = fields.One2many('account.statement.receive.wizard.picking', 'wizard_main_id')

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(AccountStatementDeliveryWizard, self).default_get(fields)
        master_id = self._context.get('active_id', False)
        if not master_id:
            return res
        assert self._context.get('active_model') in ('account.statement'), '不是正确的来源对象！'
        obj = self.env['account.statement'].browse(master_id)
        if obj:
            res.update(start_date=obj.start_date)
            res.update(end_date=obj.end_date)
        res.update(statement_source=self._context.get('statement_source', 'A'))
        # type_obj = self.env.ref('stock_delivery.stock_picking_type_Stock_delivery')
        # res.update(picking_type_id=type_obj.id)
        res.update(master_id=master_id)
        return res

    def action_query(self):
        self.ensure_one()
        if self.picking_type_id:
            picking_type_ids = tuple(self.picking_type_id.ids)
        else:
            raise UserError(_(u"提示!请选择 出入库类型！"))
            # 判断搜索到的库位有几个，若为1则不用tuple
        if len(picking_type_ids) == 1:
            picking_type_ids = "(%s)" % picking_type_ids[0]
        sql = """
               select a.id as move_id,to_char(a.date,'yyyy-mm-dd') as date,
                      a.sale_line_id,a.product_id,
                      b.name,a.origin,a.picking_type_id,
                      a.product_uom,k.currency_id,d.exchange_rate,
                      a.net_weight,CASE WHEN (l.table_name in ('sale_rebate') or a.sale_line_id is null)
                                        then a.price_unit  else c.real_price end as price_unit,
                      a.product_qty,a.to_check_qty,a.unchecked_qty,a.unchecked_amount
                 from stock_move a 
                    left join stock_picking b on a.picking_id=b.id
                    left join sale_order_line c on a.sale_line_id=c.id
                    left join sale_order d on c.order_id=d.id
                    left join product_product e on a.product_id=e.id
                    left join product_template f on e.product_tmpl_id=f.id
                    left join product_pricelist k on d.pricelist_id=k.id
                    left join stock_picking_type l on l.id=a.picking_type_id
                where b.state='done' and a.product_qty>0
                  and COALESCE(a.is_gift,'f')='f'
                  and to_char(b.date_done,'yyyy-mm-dd')>='%s'
                  and to_char(b.date_done,'yyyy-mm-dd')<='%s'
                  and b.partner_id in (select id from res_partner where id = %s or parent_id = %s)
        """ % (self.start_date, self.end_date, self.partner_id.id, self.partner_id.id,)
        if self.picking_type_id:
            sql += """ and a.picking_type_id in %s """ % (picking_type_ids,)
        if self.categ_id:
            sql += """ and f.categ_id=%s """ % (self.categ_id.id,)
        if self.statement_source == 'A':
            sql += " and COALESCE (a.statement_state,'N') in ('N','P')"
        elif self.statement_source == 'B':
            sql += " and e.product_type='G' and COALESCE (a.freight_statement_state,'N') in ('N','P')"
        if self.picking_name:
            sql += """ and b.name ilike '%%%s%%' """ % (self.picking_name,)
        if self.so_name:
            sql += """ and d.name ilike '%%%s%%' """ % (self.so_name,)
        if self.product_name:
            sql += """ and (e.default_code ilike '%%%s%%' or f.name ilike '%%%s%%' or f.spec ilike '%%%s%%')""" % (
                self.product_name, self.product_name, self.product_name,)
        items = []
        self._cr.execute(sql)
        result = self._cr.dictfetchall()
        _logger.info(f"返回对账单：{result}")
        for line in result:
            for k, v in line.items():
                if not v:
                    line[k] = False
            items.append((0, 0, line))
        self.line_ids = False
        self.is_all_check = False
        if items:
            self.line_ids = items
            self.create_wizard_product(self.line_ids)
            self.create_wizard_picking(self.line_ids)
        return self.wizard_view()

    def create_wizard_picking(self, line_ids):
        """创建入库单号合计查询"""
        if self.picking_wizard_ids:
            self.picking_wizard_ids.unlink()
        picking_list = line_ids.mapped('move_id').mapped('picking_id')
        for picking in picking_list:
            wizard_line_ids = line_ids.filtered(lambda x: x.move_id.picking_id.id == picking.id)
            picking_wizard = self.env['account.statement.delivery.wizard.picking'].create({
                'wizard_main_id': self.id,
                'picking_id': picking.id,
            })
            wizard_line_ids.write({'picking_wizard_id': picking_wizard.id})

    def create_wizard_product(self, line_ids):
        """创建产品合计"""
        if self.product_wizard_ids:
            self.product_wizard_ids.unlink()
        product_list = line_ids.mapped('product_id')
        for product in product_list:
            line_list = line_ids.filtered(lambda x: x.product_id.id == product.id)
            price_unit_old = line_list.mapped('price_unit')[0]
            price_unit_uos = line_list.mapped('price_unit_uos')[0]
            product_qty = sum(line_list.mapped('product_qty'))
            to_check_qty = sum(line_list.mapped('to_check_qty'))
            unchecked_qty = sum(line_list.mapped('unchecked_qty'))
            currency_oid = line_list.mapped('currency_id')[0]
            exchange_rate_old = sum(line_list.mapped('exchange_rate'))
            net_weight = line_list.mapped('net_weight')[0]
            currency_id = self.master_id.currency_id
            exchange_rate = self.master_id.exchange_rate
            price_unit = base_cw.public.compute_amount(self, currency_oid, self.master_id.currency_id,
                                                       price_unit_old,
                                                       from_currency_rate=exchange_rate_old,
                                                       to_currency_rate=self.master_id.exchange_rate,
                                                       round=2)
            unchecked_amount = self.master_id.currency_id.round(unchecked_qty * abs(price_unit))
            product_wizard = self.env['account.statement.delivery.wizard.product.line'].create({
                'product_id': product.id,
                'price_unit': price_unit,
                'price_unit_uos': price_unit_uos,
                'product_qty': product_qty,
                'to_check_qty': to_check_qty,
                'unchecked_qty': unchecked_qty,
                'unchecked_amount': unchecked_amount,
                'net_weight': net_weight,
                'currency_id': currency_id.id,
                'exchange_rate': exchange_rate,
                'master_id': self.id,
            })
            line_list.write({'product_wizard_id': product_wizard.id})

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.line_ids:
            line.is_check = self.is_all_check

    def action_confirm(self):
        self.ensure_one()
        selects = self.line_ids.filtered('is_check')
        if not selects:
            raise UserError(_(u"提示!请先选择明细！"))
        items = []
        for line in selects:
            # 对帐币别单价
            price_unit = base_cw.public.compute_amount(self, line.currency_id, self.master_id.currency_id,
                                                       line.price_unit,
                                                       from_currency_rate=line.exchange_rate,
                                                       to_currency_rate=self.master_id.exchange_rate,
                                                       round=False)
            unchecked_amount = self.master_id.currency_id.round(line.unchecked_qty * abs(price_unit))
            item = dict(statement_source=self.statement_source,
                        currency_id=self.master_id.currency_id and self.master_id.currency_id.id or False,
                        exchange_rate=self.master_id.exchange_rate,
                        origin=line.origin,
                        name=line.name,
                        date=line.date,
                        stock_move_id=line.move_id and line.move_id.id or False,
                        sale_line_id=line.sale_line_id and line.sale_line_id.id or False,
                        product_id=line.product_id.id,
                        product_uom=line.product_uom.id,
                        # product_qty=line.move_id.product_qty,库存单位 交易数量
                        unchecked_qty=line.unchecked_qty,
                        unchecked_amount=unchecked_amount,  # 未对帐金额
                        qty=line.unchecked_qty,  # 对帐数量
                        price_unit=price_unit,  # 对帐币别单价
                        # 对帐金额
                        amount=unchecked_amount,
                        product_uos=line.product_uom.id,
                        # 以下可以做参考
                        product_uos_qty=line.to_check_qty,
                        product_uos_amount=float_round(line.to_check_qty * line.price_unit, precision_digits=4),
                        price_unit_uos=line.price_unit,
                        )
            items.append((0, 0, item))
            if line.statement_source == 'B':  # 运费
                line.move_id.freight_statement_state = 'R'  # 对帐中
            else:
                line.move_id.statement_state = 'R'
        if items:
            self.master_id.write(dict(line_ids=items))
            self.master_id.line_ids._lot_compute_local_amount()
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_statement_delivery_wizard')
        return {
            'name': _('销售货款对帐 向导'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.statement.delivery.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class account_statement_delivery_wizard_line(models.TransientModel):
    _name = 'account.statement.delivery.wizard.line'

    is_check = fields.Boolean('选择', default=False)
    master_id = fields.Many2one('account.statement.delivery.wizard', '主档', ondelete="cascade")
    move_id = fields.Many2one('stock.move', '出入库明细')
    name = fields.Char('出入库单号')
    origin = fields.Char('暂收单号')
    date = fields.Datetime('交易日期')
    sale_line_id = fields.Many2one('sale.order.line', '订单明细')
    customer_product_code = fields.Char(string='客户产品编码', readonly=True)
    product_id = fields.Many2one('product.product', '货品编码')
    categ_id = fields.Many2one('product.category', '货品分类', related='product_id.categ_id', readonly=True)
    product_code = fields.Char(related='product_id.default_code', string='编码', readonly=True)
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True)

    product_qty = fields.Float('交易数量', digits='Product Unit of Measure', help='出入库数(库存单位)')
    to_check_qty = fields.Float('对帐数量', digits='Product Unit of Measure', help='出入库数(对于销售出货来讲 应与 交易数量 相同，)')
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure', help='未对帐数量(库存单位)')
    product_uom = fields.Many2one('uom.uom', '库存单位', )
    price_unit = fields.Float('单价', digits=(16, 4), help='库存单位单价')
    unchecked_amount = fields.Float('金额', digits='Product Price', )
    net_weight = fields.Float('重量', digits='Stock Weight')
    statement_source = fields.Selection(base_cw.public.STATEMENT_SOURCE, '对帐类型',
                                        default='A', readonly=True, )
    currency_id = fields.Many2one('res.currency', '币别', help='订单的币别汇率')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0, help='订单的币别汇率')
    picking_type_id = fields.Many2one('stock.picking.type', '出入库类型',
                                      domain=[('table_name', 'in', ('stock_delivery',
                                                                    'sale_return_storage',
                                                                    'sale_rebate',
                                                                    'sale_fandian',
                                                                    'customer_support_policy'))])
    product_uos = fields.Many2one('uom.uom', '采购单位')
    product_uos_qty = fields.Float('采购数量', digits='Product Unit of Measure')
    product_uos_amount = fields.Float('采购金额', digits='Product Price', )
    price_unit_uos = fields.Float('采购单价', digits='Product Price')
    picking_wizard_id = fields.Many2one('account.statement.delivery.wizard.picking', string='入库单号合计查询')
    product_wizard_id = fields.Many2one('account.statement.delivery.wizard.product.line', string='产品合计')


class account_statement_delivery_wizard_product_line(models.TransientModel):
    _name = "account.statement.delivery.wizard.product.line"
    _inherit = 'account.statement.receive.wizard.product.line'
    _description = '产品合计'

    master_id = fields.Many2one('account.statement.delivery.wizard', '主档', ondelete="cascade")


class account_statement_delivery_wizard_purchase_order(models.TransientModel):
    _name = 'account.statement.delivery.wizard.picking'
    _inherit = 'account.statement.receive.wizard.picking'
    _description = '入库单号合计查询'

    wizard_main_id = fields.Many2one('account.statement.delivery.wizard')
    # is_check = fields.Boolean('选择', default=False)
    # wizard_main_id = fields.Many2one('account.statement.receive.wizard')
    # picking_id = fields.Many2one('stock.picking', string='采购收货单')
    # # purchase_user_id = fields.Many2one('res.users', string='采购人员', related='picking_id.purchase_user_id')
    # # check_user_id = fields.Many2one('res.users', string='审核人员', related='picking_id.check_user_id')
    # partner_id = fields.Many2one('res.partner', string='供应商', related='picking_id.partner_id')
    wizard_line_ids = fields.One2many('account.statement.delivery.wizard.line', 'picking_wizard_id')
    # min_date = fields.Datetime('安排日期', related='picking_id.min_date')
    # location_id = fields.Many2one('stock.location', string='源库位', related='picking_id.location_id')
    # location_dest_id = fields.Many2one('stock.location', string='目的库位', related='picking_id.location_dest_id')
    #
    # @api.multi
    # def toggle_undo_flag(self):
    #     for record in self:
    #         if record.is_check == False:
    #             record.is_check = True
    #             record.wizard_line_ids.write({'is_check': True})
    #         else:
    #             record.is_check = False
    #             record.wizard_line_ids.write({'is_check': False})
    #         return record.wizard_main_id.wizard_view()
