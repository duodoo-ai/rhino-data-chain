# -*- encoding: utf-8 -*-

import time
from odoo import models, api, fields, _
from odoo.addons import base_cw
from odoo import tools
# import sys
#import odoo.addons.decimal_precision as dp

# reload(sys)
# sys.setdefaultencoding('utf-8')


class account_shipment_statement_invoice(models.Model):
    _name = "account.shipment.statement.invoice"
    _description = '出货对账开票查询'
    _auto = False

    def _compute_read_users_ids(self):
        list = []
        users_ids = self.env['res.users']
        if self.partner_id:
            list = base_cw.public.get_user_by_partner(self, self.partner_id.id)
        else:
            list = [self.env.user.id]
        for user in self.env['res.users'].search([('id', 'in', list)]):
            users_ids |= user
        self.read_users_ids = users_ids

    partner_id = fields.Many2one('res.partner', '客户')
    partner_code = fields.Char('客户编码')

    partner_name = fields.Char('客户名称')
    # spec = fields.Char('规格')
    user_id = fields.Many2one('res.users', '客户经理')

    order_id = fields.Many2one('sale.order', '订单编号')

    product_id = fields.Many2one('product.product', '产品')
    product_tmpl_id = fields.Many2one('product.template', '品名')
    delivery_no = fields.Char('出货明细单号')
    delivery_date = fields.Date('出货日期')
    product_qty = fields.Float('出货数量', digits='Product Unit of Measure', aggregator="sum")
    net_weight = fields.Float('出货重量', digits='Stock Weight', aggregator="sum")
    product_uom = fields.Many2one('uom.uom', '单位', required=False, )

    currency_id = fields.Many2one('res.currency', '币别' )
    price_unit = fields.Float(string='单价', digits='Product Price', aggregator="avg")
    delivery_amount = fields.Float('出货金额', digits='Product Price', aggregator="sum")
    checked_amount = fields.Float('对账金额',  digits='Product Price', aggregator="sum")
    local_checked_amount = fields.Float('本币对帐金额',  digits='Product Price', aggregator="sum")
    adjust_amount = fields.Float('对账调整金额',  digits='Product Price', aggregator="sum")
    unchecked_amount = fields.Float('未对账金额',  digits='Product Price', aggregator="sum")
    invoiced_amount = fields.Float('已开票金额', digits='Product Price', aggregator="sum")
    uninvoiced_amount = fields.Float('未开票金额',  digits='Product Price',)
    due_invoice_date = fields.Date('应开票日期')
    overdue_invoice_days = fields.Float('逾开天数', digits=(16, 0))
    last_invoice_date = fields.Date('末次开票日期')
    is_invoiced_done = fields.Text('已全部开票')

    read_users_ids = fields.Many2many('res.users', compute="_compute_read_users_ids", string='读取用户',
                                      search='_search_user_id', required=False)
    product_name = fields.Char(related="product_id.name", string='品名', default=False)
    # model = fields.Char(related='product_id.model', string='型号', readonly=True)
    # color_id = fields.Many2one('color.color', related='product_id.color_id', string='颜色',
    #                            readonly=True)
    # brand_id = fields.Many2one('product.brand', related='product_id.product_brand_id', string='品牌',
    #                            readonly=True)
    categ_id = fields.Many2one('product.category', related='product_id.categ_id', string='产品分类')

    def _search_user_id(self, operation, value):
        order = []
        if not value:
            return [('id', '=', False)]
        list = base_cw.public.get_partner_by_user(self, value)
        if list:
            self._cr.execute("""select id from account_shipment_statement_invoice where partner_id in %s""",
                             (tuple(list),))
            order = filter(None, map(lambda x: x[0], self._cr.fetchall()))
        return [('id', 'in', order)]

    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_shipment_statement_invoice')
        self._cr.execute("""create or replace view account_shipment_statement_invoice as (
                    select a.id,b.partner_id,d.code as partner_code,d.name as partner_name,
                           a.product_id,e.product_tmpl_id,h.partner_currency_id as currency_id,a.product_uom,--h.payment_mode_id,
                           to_date(to_char(b.date_done,'yyyy-mm-dd'),'yyyy-mm-dd') as delivery_date,b.name as delivery_no,a.product_qty,a.net_weight,
                           a.last_invoice_date,a.invoiced_amount,g.order_id,a.price_unit,h.user_id,--h.execution_user_id,
                           (case when coalesce(a.invoiced_amount,0)<coalesce(a.amount*c.effect_statement,0)+coalesce(a.adjust_amount,0) then
                            coalesce(a.amount*c.effect_statement,0)-coalesce(a.invoiced_amount,0)+coalesce(a.adjust_amount,0) else 0 end) as uninvoiced_amount,
                           (case when i.is_monthly='f' then b.date_done + (COALESCE(i.invoice_days,0) || ' day')::interval else
                            (to_date(to_char(now()+interval '1 month','yyyy-mm-01'),'yyyy-mm-dd')-1) end) as due_invoice_date,
                           (case when now()> (case when i.is_monthly='f' then b.date_done + (COALESCE(i.invoice_days,0) || ' day')::interval else
                                             (to_date(to_char(now()+interval '1 month','yyyy-mm-01'),'yyyy-mm-dd')-1) end ) then
                            date_part('day',now() - (case when i.is_monthly='f' then b.date_done + (COALESCE(i.invoice_days,0) || ' day')::interval else
                                                    (to_date(to_char(now()+interval '1 month','yyyy-mm-01'),'yyyy-mm-dd')-1) end )::timestamp) else 0 end) as overdue_invoice_days,
                           coalesce(amount*c.effect_statement,0) as delivery_amount,
                           a.checked_amount,a.unchecked_amount,a.local_checked_amount,a.local_unchecked_amount,a.adjust_amount,
                           case when coalesce(amount*c.effect_statement,0)-coalesce(a.invoiced_amount,0)=0 then 't' else 'f' end as is_invoiced_done--,d.sales_orientation

                      from stock_move a left join stock_picking b on a.picking_id=b.id
                                        left join stock_picking_type c on a.picking_type_id=c.id
                                        left join res_partner d on b.partner_id=d.id
                                        left join product_product e on a.product_id=e.id
                                        left join product_template f on e.product_tmpl_id=f.id
                                        left join sale_order_line g on a.sale_line_id=g.id
                                        left join sale_order h on g.order_id=h.id
                                        left join account_payment_term i on i.id=h.payment_term_id
                     where c.table_name in ('stock_delivery','sale_return_storage')
                       and b.state='done' and a.price_unit > 0
              )
        """)
