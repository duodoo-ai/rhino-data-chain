# -*- encoding: utf-8 -*-
from odoo import models, fields, api
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.translate import _
"""
purchase_storage  {"en_US": "采购入库单", "zh_CN": "采购入库单"}
purchase_storage_return  {"en_US": "采购退货单", "zh_CN": "采购退货单"}
purchase_rebate  
outsourcing_in  
outsourcing_return  
"""

class AccountStatementReceiveWizard(models.TransientModel):
    _name = 'account.statement.receive.wizard'
    _description = "对账单向导"

    master_id = fields.Many2one('account.statement', '对帐单', )
    statement_type = fields.Selection(base_cw.public.STATEMENT_TYPE, string='对帐类型', readonly=True,
                                      related='master_id.statement_type')
    partner_id = fields.Many2one('res.partner', string='合作伙伴')
    picking_type_id = fields.Many2many('stock.picking.type', string='出入库类型', required=False,
                                       domain=[('table_name', 'in', ("purchase_storage",
                                                                     "purchase_storage_return",
                                                                     'purchase_rebate',
                                                                     'outsourcing_in',
                                                                     'outsourcing_return'
                                                                     ))])
    start_date = fields.Date('对帐起日', required=True)
    end_date = fields.Date('对帐迄日', required=True)
    statement_source = fields.Selection([('A', '货款'),
                                         ('B', '运费'), ], '对帐对象', readonly=True, required=True, default='A')
    picking_name = fields.Char('出入库单号')
    so_name = fields.Char('订单编号')
    po_name = fields.Char('采购单号')
    product_name = fields.Char('货品编码')
    receive_name = fields.Char('委外单号')
    delivery_no = fields.Char('收货单号')
    is_all_check = fields.Boolean('全选', default=False)
    note = fields.Char('说明', required=False, readonly=True)
    line_ids = fields.One2many('account.statement.receive.wizard.line', 'master_id', '明细', )
    product_wizard_ids = fields.One2many('account.statement.receive.wizard.product.line', 'master_id')
    picking_wizard_ids = fields.One2many('account.statement.receive.wizard.picking', 'wizard_main_id')

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(AccountStatementReceiveWizard, self).default_get(fields)
        master_id = self._context.get('active_id', False)
        if not master_id:
            return res
        assert self._context.get('active_model') in ('account.statement',), '不是正确的来源对象！'
        obj = self.env['account.statement'].browse(master_id)
        if obj:
            res.update(start_date=obj.start_date)
            res.update(end_date=obj.end_date)
        res.update(statement_source=self._context.get('statement_source', 'A'))

        res.update(master_id=master_id)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.line_ids:
            line.is_check = self.is_all_check

    def set_is_all_check(self):
        self.is_all_check = True
        self.onchange_is_all_check()

        if self.statement_source == 'B':
            return self.freight_wizard_view()
        else:
            return self.wizard_view()

    def action_query(self):
        self.ensure_one()
        # 类型默认所有采购库位和退货库位的
        if self.picking_type_id:
            picking_type_ids = tuple(self.picking_type_id.ids)
        else:
            raise UserError(_(u"提示!请选择 出入库类型！"))
        # 判断搜索到的库位有几个，若为1则不用tuple
        if len(picking_type_ids) == 1:
            picking_type_ids = "(%s)" % picking_type_ids[0]
        line_sql = """
            select a.id as move_id,to_char(a.date,'yyyy-mm-dd') as date,
                   a.purchase_line_id,
                   a.product_id,
                   b.name,a.origin,b.origin as delivery_no,a.picking_type_id,
                   a.product_uom,d.currency_id,d.exchange_rate,
                   a.net_weight,
                   a.price_unit,
                   b.partner_id,
                   a.local_price as price_unit_uos,
                   a.product_qty*g.effect_statement as product_qty,
                   COALESCE(a.to_check_qty,0) AS to_check_qty, 
                   COALESCE(COALESCE(a.unchecked_qty,NULL),a.product_qty*g.effect_statement) as unchecked_qty,
                   COALESCE(COALESCE(a.unchecked_amount,NULL),a.product_qty*g.effect_statement*a.price_unit) as unchecked_amount
             from stock_move a 
             left join stock_picking b on a.picking_id=b.id
            left join purchase_order_line c on a.purchase_line_id=c.id
            left join purchase_order d on c.order_id=d.id
            left join product_product e on a.product_id=e.id
            left join product_template f on e.product_tmpl_id=f.id
            left join stock_picking_type g on g.id=a.picking_type_id
            where b.state='done' and a.product_qty<>0 and a.id>0
            and COALESCE(a.is_gift,'f')='f'
            and to_char(b.date_done,'yyyy-mm-dd')>='%s'
            and to_char(b.date_done,'yyyy-mm-dd')<='%s'
        """ % (self.start_date, self.end_date)
        if self.statement_source == 'A':
            line_sql += " and COALESCE (a.statement_state,'N') in ('N','P')"
        if picking_type_ids:
            line_sql += """ and a.picking_type_id IN  %s""" % (picking_type_ids,)
        if self.partner_id:
            line_sql += """ and b.partner_id = %s""" % (self.partner_id.id,)
        if self.picking_name:
            line_sql += """ and b.name ilike '%%%s%%' """ % (self.picking_name,)
        if self.po_name:
            line_sql += """ and d.name ilike '%%%s%%' """ % (self.po_name,)
        if self.receive_name:
            line_sql += """ and a.origin ilike '%%%s%%' """ % (self.receive_name,)
        if self.delivery_no:
            line_sql += """ and b.origin ilike '%%%s%%' """ % (self.delivery_no,)
        if self.product_name:
            line_sql += """ and (e.default_code ilike '%%%s%%' or f.name ilike '%%%s%%' or e.spec ilike '%%%s%%')""" % (
                self.product_name, self.product_name, self.product_name,)
        items = []
        self._cr.execute(line_sql)
        result = self._cr.dictfetchall()
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
        if self.statement_source == 'B':
            return self.freight_wizard_view()
        else:
            return self.wizard_view()

    def create_wizard_picking(self, line_ids):
        """创建入库单号合计查询"""
        if self.picking_wizard_ids:
            self.picking_wizard_ids.unlink()
        picking_list = line_ids.mapped('move_id').mapped('picking_id')
        for picking in picking_list:
            wizard_line_ids = line_ids.filtered(lambda x: x.move_id.picking_id.id == picking.id)
            picking_wizard = self.env['account.statement.receive.wizard.picking'].create({
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
            price_unit = line_list.mapped('price_unit')[0]
            price_unit_uos = line_list.mapped('price_unit_uos')[0]
            product_qty = sum(line_list.mapped('product_qty'))
            to_check_qty = sum(line_list.mapped('to_check_qty'))
            unchecked_qty = sum(line_list.mapped('unchecked_qty'))
            unchecked_amount = sum(line_list.mapped('unchecked_amount'))
            net_weight = line_list.mapped('net_weight')[0]
            currency_id = line_list.mapped('currency_id')[0].id if line_list.mapped('currency_id') else False
            exchange_rate = line_list.mapped('exchange_rate')[0]
            product_wizard = self.env['account.statement.receive.wizard.product.line'].create({
                'product_id': product.id,
                'price_unit': price_unit,
                'price_unit_uos': price_unit_uos,
                'product_qty': product_qty,
                'to_check_qty': to_check_qty,
                'unchecked_qty': unchecked_qty,
                'unchecked_amount': unchecked_amount,
                'net_weight': net_weight,
                'currency_id': currency_id,
                'exchange_rate': exchange_rate,
                'master_id': self.id,

            })
            line_list.write({'product_wizard_id': product_wizard.id})

    @api.model
    def update_product_uos_qty(self, line=None):
        """
        功能 已移到move 仓库确认时计算
        """
        product_uos_qty = line['product_qty']
        move_id = self.env['stock.move'].browse(line['move_id'])
        move_id.product_qty = product_uos_qty
        move_id.compute_checked_qty()
        line['unchecked_qty'] = move_id.unchecked_qty

    def action_confirm(self):
        self.ensure_one()
        selects = self.line_ids.filtered('is_check')
        if not selects:
            raise UserError(_(u"提示!请先选择明细！"))
        items = []
        for line in selects:
            # 对帐币别单价
            price_unit = base_cw.public.compute_amount(self, line.currency_id,
                                                       self.master_id.currency_id,
                                                       line.price_unit_uos,
                                                       from_currency_rate=line.exchange_rate,
                                                       to_currency_rate=self.master_id.exchange_rate,
                                                       round=False)
            unchecked_amount = self.master_id.currency_id.round(line.unchecked_qty * abs(price_unit))
            unchecked_qty = line.unchecked_qty
            product_id = line.product_id
            product_uos = line.product_uom.id
            product_uom = line.product_uom.id
            qty = line.unchecked_qty
            if self.statement_source == 'B':  # 运费
                product_id = self.env.ref('cncw_statement.product_product_freight')
                price_unit = 0.0
                unchecked_amount = 0.0
                product_uos = False
                product_uom = False
                unchecked_qty = 1
                qty = 1
            adjust_reason = False

            item = dict(statement_source=self.statement_source,
                        currency_id=self.master_id.currency_id and self.master_id.currency_id.id or False,
                        exchange_rate=self.master_id.exchange_rate,
                        origin=line.origin,
                        name=line.name,
                        delivery_no=line.delivery_no,
                        date=line.date,
                        stock_move_id=line.move_id and line.move_id.id or False,
                        purchase_line_id=line.purchase_line_id and line.purchase_line_id.id or False,
                        product_id=product_id.id,
                        product_uom=product_uom and product_uom or False,
                        unchecked_qty=unchecked_qty,
                        unchecked_amount=unchecked_amount,
                        # 未对帐金额
                        qty=qty,  # 对帐数量
                        price_unit=abs(price_unit),  # 对帐币别单价
                        # 对帐金额
                        amount=unchecked_amount if self.statement_source == 'A' else 0,
                        product_uos=product_uos and product_uos or False,
                        # 以下可以做参考
                        product_uos_qty=line.to_check_qty,
                        product_uos_amount=float_round(line.to_check_qty * line.price_unit_uos, precision_digits=1),
                        price_unit_uos=line.price_unit_uos,
                        adjust_reason=adjust_reason
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
        view = self.env.ref('cncw_statement.form_account_statement_receive_wizard')
        return {
            'name': _('采购进货对帐 向导'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.statement.receive.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }

    def freight_wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_statement_receive_freight_wizard')
        return {
            'name': _('采购运费对帐 向导'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.statement.receive.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class AccountStatementReceiveWizardLine(models.TransientModel):
    _name = 'account.statement.receive.wizard.line'

    is_check = fields.Boolean('选择', default=False)
    master_id = fields.Many2one('account.statement.receive.wizard', '主档', ondelete="cascade")
    move_id = fields.Many2one('stock.move', '出入库明细')
    picking_type_id = fields.Many2one('stock.picking.type', '交易类型')
    name = fields.Char('出入库单号')
    origin = fields.Char('暂收单号')
    delivery_no = fields.Char('收货单号')
    date = fields.Datetime('交易日期')
    purchase_line_id = fields.Many2one('purchase.order.line', '采购单号')
    product_id = fields.Many2one('product.product', '货品编码')
    product_code = fields.Char(related='product_id.default_code', string='编码', readonly=True)
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)

    product_uom = fields.Many2one('uom.uom', '库存单位', )
    product_uos = fields.Many2one('uom.uom', '采购单位')

    price_unit = fields.Float('单价', digits='Product Price', help='库存单位单价')
    price_unit_uos = fields.Float('采购单价', digits='Product Price')

    product_qty = fields.Float('交易数量', digits='Product Unit of Measure', help='出入库数(库存单位)')
    to_check_qty = fields.Float('对帐数量', digits='Product Unit of Measure', help='出入库数(采购单位)')
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure', help='未对帐数量(采购单位)')
    unchecked_amount = fields.Float('金额', digits='Product Price', )
    net_weight = fields.Float('重量', digits='Stock Weight')

    statement_source = fields.Selection([('A', '货款'),
                                         ('B', '运费'), ],
                                        '对帐对象', related='master_id.statement_source', readonly=True)
    currency_id = fields.Many2one('res.currency', '币别', help='订单的币别汇率')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0, help='订单的币别汇率')
    picking_wizard_id = fields.Many2one('account.statement.receive.wizard.picking', string='入库单号合计查询')
    product_wizard_id = fields.Many2one('account.statement.receive.wizard.product.line', string='产品合计')
    partner_id = fields.Many2one('res.partner', string='合作伙伴')


class AccountStatementReceiveWizardProductLine(models.TransientModel):
    _name = "account.statement.receive.wizard.product.line"
    _description = '产品合计'

    is_check = fields.Boolean('选择', default=False)
    master_id = fields.Many2one('account.statement.receive.wizard', '主档', ondelete="cascade")
    product_id = fields.Many2one('product.product', string='产品')
    default_code = fields.Char(string='产品编号', related='product_id.default_code')
    price_unit = fields.Float('单价', digits='Product Price', help='库存单位单价')
    price_unit_uos = fields.Float('采购单价', digits='Product Price')

    product_qty = fields.Float('交易数量', digits='Product Unit of Measure', help='出入库数(库存单位)')
    to_check_qty = fields.Float('对帐数量', digits='Product Unit of Measure', help='出入库数(采购单位)')
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure', help='未对帐数量(采购单位)')
    unchecked_amount = fields.Float('金额', digits='Product Price', )
    net_weight = fields.Float('重量', digits='Stock Weight')

    statement_source = fields.Selection([('A', '货款'),
                                         ('B', '运费'), ],
                                        '对帐对象', related='master_id.statement_source', readonly=True)
    currency_id = fields.Many2one('res.currency', '币别', help='订单的币别汇率')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0, help='订单的币别汇率')
    line_ids = fields.One2many('account.statement.receive.wizard.line', 'product_wizard_id')

    def toggle_undo_flag(self):
        for record in self:
            if not record.is_check:
                record.is_check = True
                record.line_ids.write({'is_check': True})
            else:
                record.is_check = False
                record.line_ids.write({'is_check': False})
            return {"type": "ir.actions.act_reload_current_view"}


class AccountStatementReceiveWizardPurchaseOrder(models.TransientModel):
    _name = 'account.statement.receive.wizard.picking'
    _description = '入库单号合计查询'

    is_check = fields.Boolean('选择', default=False)
    wizard_main_id = fields.Many2one('account.statement.receive.wizard')
    picking_id = fields.Many2one('stock.picking', string='采购收货单')
    partner_id = fields.Many2one('res.partner', string='供应商', related='picking_id.partner_id')
    wizard_line_ids = fields.One2many('account.statement.receive.wizard.line', 'picking_wizard_id')
    min_date = fields.Datetime('安排日期', related='picking_id.scheduled_date', store=True)
    location_id = fields.Many2one('stock.location', string='源库位', related='picking_id.location_id', store=True)
    location_dest_id = fields.Many2one('stock.location', string='目的库位', related='picking_id.location_dest_id',
                                       store=True)

    def toggle_undo_flag(self):
        for record in self:
            if not record.is_check:
                record.is_check = True
                record.wizard_line_ids.write({'is_check': True})
            else:
                record.is_check = False
                record.wizard_line_ids.write({'is_check': False})
            return {"type": "ir.actions.act_reload_current_view"}
