# -*- coding: utf-8 -*-

from odoo import api,fields,models,tools
from odoo.addons import base_cw

class AccountPurchaseInvoiceDeliveryReport(models.Model):
    _name = 'account.purchase.invoice.delivery.report'
    _description = '采购开票查询'
    _auto = False

    move_id = fields.Many2one('stock.move', '出入库明细')
    picking_type_id = fields.Many2one('stock.picking.type', '交易类型')
    name = fields.Char('出入库单号')
    origin = fields.Char('暂收单号')
    delivery_no = fields.Char('采购单号')
    date = fields.Datetime('交易日期')
    # order_line_id = fields.Many2one('sale.order.line', '订单明细')
    purchase_order_id = fields.Many2one('purchase.order', '采购单')
    purchase_line_id = fields.Many2one('purchase.order.line', '采购单明细')
    product_id = fields.Many2one('product.product', '货品编码')
    product_code = fields.Char(related='product_id.default_code', string='编码', readonly=True)
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True)
    # product_model = fields.Char(related='product_id.model', string='型号', readonly=True)
    # product_color_id = fields.Many2one('color.color',related='product_id.color_id', string='颜色', readonly=True)
    # product_brand_id = fields.Many2one('product.brand',related='product_id.product_brand_id', string='品牌', readonly=True)

    product_uom = fields.Many2one('uom.uom', '库存单位',related='move_id.product_uom')
    product_uos = fields.Many2one('uom.uom', '采购单位', related='purchase_line_id.product_uom')

    price_unit = fields.Float('单价', digits='Product Price', help='库存单位单价')
    price_unit_uos = fields.Float('采购单价', digits='Product Price')

    product_qty = fields.Float('交易数量', digits='Product Unit of Measure', help='出入库数(库存单位)')
    to_check_qty = fields.Float('对帐数量', digits='Product Unit of Measure', help='出入库数(采购单位)')
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure', help='未对帐数量(采购单位)')
    unchecked_amount = fields.Float('金额',  digits='Product Price',)
    net_weight = fields.Float('重量', digits='Stock Weight')

    # statement_source = fields.Selection([('A', '货款'),
    #                                      ('B', '运费'), ],
    #                                     '对帐对象', related='master_id.statement_source', readonly=True)
    currency_id = fields.Many2one('res.currency', '币别', help='订单的币别汇率')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0, help='订单的币别汇率')
    # picking_wizard_id = fields.Many2one('account.statement.receive.wizard.picking', string='入库单号合计查询')
    # product_wizard_id = fields.Many2one('account.statement.receive.wizard.product.line', string='产品合计')
    partner_id = fields.Many2one('res.partner', string='合作伙伴')
    invoice_no = fields.Char('发票编号')
    invoiced_qty = fields.Char('开票数量')
    invoiced_amount = fields.Float('开票金额',digits='Product Price')
    last_invoice_date = fields.Date('末次开票日期')
    category_id = fields.Many2one('product.category', string='产品分类')

    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_purchase_invoice_delivery_report')
        self._cr.execute("""create or replace view account_purchase_invoice_delivery_report as (
                 select a.id,a.id as move_id,to_char(a.date,'yyyy-mm-dd') as date,
                   a.purchase_line_id,
                   d.id as purchase_order_id,
                   a.product_id,
                   a.invoice_no,
                   a.invoiced_qty,
                   a.invoiced_amount,
                   a.last_invoice_date,
                   b.name,a.origin,b.origin as delivery_no,a.picking_type_id,
                   a.product_uom,d.currency_id,d.exchange_rate,
                   a.net_weight,
                   a.price_unit,
                   b.partner_id,
                   f.categ_id as category_id,
                   CASE 
                        WHEN (g.table_name='purchase_rebate' or purchase_line_id is null)  then a.price_unit
                        WHEN (a.product_id <> c.product_id)  then a.price_unit                          
                        ELSE c.price_unit 
                   END as price_unit_uos,
                   a.product_qty*g.effect_statement as product_qty,
                   a.to_check_qty, COALESCE(a.unchecked_qty,a.product_qty*g.effect_statement) as unchecked_qty,
                   COALESCE(a.unchecked_amount,a.product_qty*g.effect_statement*a.price_unit) as unchecked_amount
             from stock_move a left join stock_picking b on a.picking_id=b.id
                               left join purchase_order_line c on a.purchase_line_id=c.id
                               left join purchase_order d on c.order_id=d.id
                               left join product_product e on a.product_id=e.id
                               left join product_template f on e.product_tmpl_id=f.id
                               left join stock_picking_type g on g.id=a.picking_type_id
            where b.state='done' and a.product_qty<>0 and a.id>0
                    and COALESCE(a.is_gift,'f')='f'
                  and g.table_name in ('purchase_storage','purchase_storage_return','purchase_rebate','outsourcing_in'))
        """)