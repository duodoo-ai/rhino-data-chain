# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models


class PurchaseReturnReport(models.Model):
    _name = "purchase.return.report"
    _description = """采购退货单"""
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    name = fields.Char(string='单号', readonly=True)
    date = fields.Datetime(string='日期', readonly=True)
    product_id = fields.Many2one('product.product', string='产品变体', readonly=True)
    product_uom = fields.Many2one('uom.uom', string='单位', readonly=True)
    return_qty = fields.Float(string='退货数量', readonly=True)
    partner_id = fields.Many2one('res.partner', string='供应商', readonly=True)
    company_id = fields.Many2one('res.company', string='公司', readonly=True)
    user_id = fields.Many2one('res.users', string='人员', readonly=True)
    price_total = fields.Float(string='总计', readonly=True)
    price_subtotal = fields.Float(string='小计', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='产品', readonly=True)
    categ_id = fields.Many2one('product.category', string='产品类别', readonly=True)
    nbr = fields.Integer(string='#明细行', readonly=True)
    country_id = fields.Many2one('res.country', string='供应商国家', readonly=True)
    state = fields.Selection([
        ('draft','草稿'),('unexamine','待审核'),('pass','通过'),('unpass','不通过'),('cancel','取消')
        ], string='状态', readonly=True)
    
    order_id = fields.Many2one('purchase.return', string='采购退货单', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            min(l.id) as id,
            l.product_id as product_id,
            t.uom_id as product_uom,
            sum(l.return_qty / u.factor * u2.factor) as return_qty,
            sum(l.price_total / CASE COALESCE(po.currency_rate, 0) WHEN 0 THEN 1.0 ELSE po.currency_rate END) as price_total,
            sum(l.price_subtotal / CASE COALESCE(po.currency_rate, 0) WHEN 0 THEN 1.0 ELSE po.currency_rate END) as price_subtotal,
            count(*) as nbr,
            po.name as name,
            po.return_date as date,
            po.state as state,
            po.partner_id as partner_id,
            po.user_id as user_id,
            po.company_id as company_id,
            extract(epoch from avg(date_trunc('day',po.return_date)-date_trunc('day',po.create_date)))/(24*60*60)::decimal(16,2) as delay,
            t.categ_id as categ_id,
            p.product_tmpl_id,
            partner.country_id as country_id,
            po.id as order_id
        """

        for field in fields.values():
            select_ += field

        from_ = """
                purchase_return_line l
                      join purchase_return po on (l.order_id=po.id)
                      join res_partner partner on po.partner_id = partner.id
                        left join product_product p on (l.product_id=p.id)
                            left join product_template t on (p.product_tmpl_id=t.id)
                    left join uom_uom u on (u.id=l.product_uom)
                    left join uom_uom u2 on (u2.id=t.uom_id)
                %s
        """ % from_clause

        groupby_ = """
            l.product_id,
            l.order_id,
            t.uom_id,
            t.categ_id,
            po.name,
            po.return_date,
            po.partner_id,
            po.user_id,
            po.state,
            po.company_id,
            p.product_tmpl_id,
            partner.country_id,
            po.id %s
        """ % (groupby)

        return '%s (SELECT %s FROM %s WHERE l.product_id IS NOT NULL GROUP BY %s)' % (with_, select_, from_, groupby_)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))


