# -*- encoding: utf-8 -*-

from odoo import models, fields
from odoo import tools
from odoo.addons import base_cw


# reload(sys)
# sys.setdefaultencoding('utf-8')


class account_sale_invoice_delivery(models.Model):
    _name = "account.sale.invoice.delivery"
    _description = '销售开票出货查询'
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
    # short_name = fields.Char('客户简称')
    partner_name = fields.Char('客户全称')
    date_invoice = fields.Date('开票日期')
    amount_invoice = fields.Float('开票原币金额', digits='Product Price', )
    price_subtotal = fields.Float('开票金额', digits='Product Price', aggregator="sum")
    total_amount_signed = fields.Float('本币金额', digits='Product Price', )
    delivery_date = fields.Date('出货日期')
    net_weight = fields.Float('出货重量', digits='Stock Weight', aggregator="sum")
    delivery_amount = fields.Float('出货金额', digits='Product Price', aggregator="sum")
    order_id = fields.Many2one('sale.order', '订单编号')
    # product_pool_id = fields.Many2one('sale.customer.product.pool', '客户产品编码')
    product_id = fields.Many2one('product.product', '产品')
    product_name = fields.Char('品名')
    # spec = fields.Char('规格')
    shipment_no = fields.Char('出货单号')
    shipment_date = fields.Date('出货日期')
    state = fields.Char('出库状态')

    delivery_price = fields.Float(string='出货单价', digits=(16, 4), aggregator="avg")
    price_unit = fields.Float(string='开票单价', digits=(16, 4), aggregator="avg")
    qty = fields.Float('开票数量', digits=(16, 3))
    invoice_weight = fields.Float('开票重量', digits=(16, 3))
    currency_id = fields.Many2one('res.currency', string='开票币别')
    invoice_no = fields.Char('发票号码')
    payment_term_id = fields.Many2one('account.payment.term', '付款条件')
    note = fields.Text('备注')
    product_uom = fields.Many2one('uom.uom', '单位')
    payment_mode_id = fields.Many2one('payment.mode', '付款方式')
    adjust_amount = fields.Float('对帐调整金额', digits='Product Price', )
    read_users_ids = fields.Many2many('res.users', compute="_compute_read_users_ids", string='读取用户',
                                      search='_search_user_id', )

    # model = fields.Char(related='product_id.model', string='型号', readonly=True)
    # color_id = fields.Many2one('color.color', related='product_id.color_id', string='颜色',
    #                                    readonly=True)
    # brand_id = fields.Many2one('product.brand', related='product_id.product_brand_id', string='品牌',
    #                                    readonly=True)
    categ_id = fields.Many2one('product.category', related='product_id.categ_id', string='产品分类')

    def _search_user_id(self, operation, value):
        order = []
        if not value:
            return [('id', '=', False)]
        list = base_cw.public.get_partner_by_user(self, value)
        if list:
            self._cr.execute("""select id from account_sale_invoice_delivery where partner_id in %s""", (tuple(list),))
            order = filter(None, map(lambda x: x[0], self._cr.fetchall()))
        return [('id', 'in', order)]

    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_sale_invoice_delivery')
        self._cr.execute("""create or replace view account_sale_invoice_delivery as (

                   select DISTINCT a.id,b.partner_id,g.code  as partner_code,g.name as partner_name,
                           b.date_invoice,
                           a.total_amount-Coalesce(a.invalid_amount,0) price_subtotal,
                           a.total_amount-Coalesce(a.invalid_amount,0) as amount_invoice,
                           a.total_amount_signed,to_date(to_char(d.date,'yyyy-mm-dd'),'yyyy-mm-dd') as shipment_date,
                           to_date(to_char(d.date_done,'yyyy-mm-dd'),'yyyy-mm-dd') as delivery_date,c.net_weight,
                           cast(a.quantity*c.price_unit*l.effect_statement as numeric) as delivery_amount,e.order_id,
                           c.product_id,k.name as product_name,
                           f.name as shipment_no,
                           d.state,
                                    c.price_unit as delivery_price,
                           a.price_unit,a.quantity as qty,a.quantity*h.weight as invoice_weight,b.currency_id,b.payment_term_id,
                           f.note,c.product_uom,b.payment_mode_id,z.adjust_amount,b.invoice_no
                     from cncw_invoice_move_line a left join cncw_invoice_move b on a.move_id=b.id
                                                 left join stock_move c on a.stock_move_id=c.id
                                                 left join stock_picking d on c.picking_id=d.id
                                                 left join sale_order_line e on c.sale_line_id=e.id
                                                 left join sale_order f on e.order_id=f.id
                                                 left join res_partner g on b.partner_id=g.id

                                                 left join product_product h on c.product_id=h.id
                                                 left join product_template pt on h.product_tmpl_id = pt.id
                                                 left join product_template k on h.product_tmpl_id=k.id
                                                 left join stock_picking_type l on d.picking_type_id=l.id

                                                 left join account_statement_line z on z.id=a.account_statement_line_id
                    where b.move_type in ('out_invoice','out_refunt') and a.price_unit > 0
                      and b.state not in ('cancel')
                )
        """)
