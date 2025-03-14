# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models


class PurchaseChangeReport(models.Model):
    _name = "purchase.change.report"
    _description = """采购变更单"""
    _auto = False
    _rec_name = 'date'
    _order = 'date desc'

    name = fields.Char(string='单号', readonly=True)
    date = fields.Datetime(string='日期', readonly=True)
    product_id = fields.Many2one('product.product', string='产品变体', readonly=True)
    product_uom = fields.Many2one('uom.uom', string='单位', readonly=True)
    product_qty = fields.Float(string='原数量', readonly=True)
    change_product_qty = fields.Float(string='变更后数量', readonly=True)
    
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
        ('draft','草稿'),('submit','已提交'),('done','完成')
        ], string='状态', readonly=True)
    
    order_id = fields.Many2one('purchase.change', string='采购变更单', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            min(l.id) as id,
            l.product_id as product_id,
            t.uom_id as product_uom,
            sum(l.product_qty / u.factor * u2.factor) as product_qty,
            sum(l.change_product_qty / u.factor * u2.factor) as change_product_qty,
            sum(l.price_total / CASE COALESCE(pc.currency_rate, 0) WHEN 0 THEN 1.0 ELSE pc.currency_rate END) as price_total,
            sum(l.price_subtotal / CASE COALESCE(pc.currency_rate, 0) WHEN 0 THEN 1.0 ELSE pc.currency_rate END) as price_subtotal,
            count(*) as nbr,
            pc.name as name,
            pc.date_order as date,
            pc.state as state,
            pc.partner_id as partner_id,
            pc.user_id as user_id,
            pc.company_id as company_id,
            extract(epoch from avg(date_trunc('day',pc.date_order)-date_trunc('day',pc.create_date)))/(24*60*60)::decimal(16,2) as delay,
            t.categ_id as categ_id,
            p.product_tmpl_id,
            partner.country_id as country_id,
            pc.id as order_id
        """

        for field in fields.values():
            select_ += field

        from_ = """
                purchase_change_line l
                      join purchase_change pc on (l.order_id=pc.id)
                      join res_partner partner on pc.partner_id = partner.id
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
            pc.name,
            pc.date_order,
            pc.partner_id,
            pc.user_id,
            pc.state,
            pc.company_id,
            p.product_tmpl_id,
            partner.country_id,
            pc.id %s
        """ % (groupby)

        return '%s (SELECT %s FROM %s WHERE l.product_id IS NOT NULL GROUP BY %s)' % (with_, select_, from_, groupby_)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))


