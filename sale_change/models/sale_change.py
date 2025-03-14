# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, time
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class SaleChange(models.Model):
    _name = "sale.change"
    _description="销售变更单"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order="create_date desc"
    _check_company_auto = True
    
    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })
            
    name = fields.Char(string='编码', required=True, copy=False,
                       readonly=True,
                       index=True,
                       default=lambda self: _('New'))
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="币种")
    partner_id = fields.Many2one(
        'res.partner', string='客户', readonly=True,
        required=True, change_default=True, index=True, tracking=1,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    partner_invoice_id = fields.Many2one(
        'res.partner', string='开票地址',
        readonly=True, required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    partner_shipping_id = fields.Many2one(
        'res.partner', string='交货地址', readonly=True, required=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    date_order = fields.Datetime(string='单据日期', required=True, readonly=True, index=True, default=fields.Datetime.now)
    old_order_id=fields.Many2one('sale.order',string='源销售订单',domain="""[
                ('state','in',['sale','done']),'|',
                ('company_id', '=', False),
                ('company_id', '=', company_id)]""",
        check_company=True)
    commitment_date = fields.Datetime(string='原交货日期')
    change_commitment_date = fields.Datetime(string='变更交货日期')
    user_id = fields.Many2one('res.users', string='销售员')
    team_id=fields.Many2one('crm.team',string='销售团队')
    change_user_id = fields.Many2one(
        'res.users', string='变更人', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string='源更付款条款', check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    change_payment_term_id = fields.Many2one(
        'account.payment.term', string='变更付款条款', check_company=True,  # Unrequired company
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    
    state = fields.Selection([('draft','草稿'),('submit','已提交'),('done','完成')],string='状态',default="draft")
    order_line = fields.One2many('sale.change.line','order_id',string='明细')
    currency_rate = fields.Float("Currency Rate",related='old_order_id.currency_rate',store=True)
    amount_untaxed = fields.Monetary(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=5)
    amount_tax = fields.Monetary(string='税率设置', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='合计', store=True, readonly=True, compute='_amount_all', tracking=4)
    note=fields.Text(string='变更说明')
    
    def create(self,vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].with_context(force_company=self.env.user.company_id.id).next_by_code(
                'sale.change') or '/'
        return super(SaleChange, self).create(vals)

    def unlink(self):
        for record in self:
            if record.state!='draft':
                raise UserError(_("只有草稿状态可以删除！"))
        return super(SaleChange, self).unlink()
                
    @api.onchange('old_order_id')
    def onchange_old_order_id(self):
        if self.old_order_id:
            self.order_line=False
            self.partner_id=self.old_order_id.partner_id.id
            self.currency_id=self.old_order_id.currency_id.id
            self.partner_invoice_id=self.old_order_id.partner_invoice_id
            self.partner_shipping_id=self.old_order_id.partner_shipping_id
            self.company_id=self.old_order_id.company_id.id
            self.commitment_date=self.old_order_id.commitment_date
            self.change_commitment_date=self.old_order_id.commitment_date
            self.user_id=self.old_order_id.user_id.id
            self.team_id=self.old_order_id.team_id.id
            self.payment_term_id=self.old_order_id.payment_term_id
            self.change_payment_term_id=self.old_order_id.payment_term_id
             
            order_lines = []
            for line in self.old_order_id.order_line:
                vals={
                    'old_line_id':line.id,
                    'name':line.name,
                    'sequence':line.sequence,
                    'price_unit':line.price_unit,
                    'change_price_unit':line.price_unit,
                    'tax_id':line.tax_id.ids,
                    'change_tax_id':line.tax_id.ids,
                    'discount':line.discount,
                    'product_id':line.product_id.id,
                    'product_uom_qty':line.product_uom_qty,
                    'change_product_uom_qty':line.product_uom_qty,
                    'product_uom':line.product_uom.id,
                    }
                order_lines.append((0, 0, vals))
            self.order_line = order_lines
            
    
    def button_change_done(self):
        for line in self.order_line:
            if line.change_product_uom_qty<=0:
                raise UserError(_('变更后数量不能小于已发货数量！'))
            if line.change_product_uom_qty<line.old_line_id.qty_delivered:
                raise UserError(_('变更后数量不能小于已发货数量！'))
            if line.change_product_uom_qty>0 and line.old_line_id.product_uom_qty== line.old_line_id.qty_delivered:
                raise UserError(_('产品%s 已发完！')%line.product_id.name)
            #验证已审核发货通知单的发货数量
            sale_delivery_lines=self.env['sale.delivery.line'].search([('sale_line_id','=',line.old_line_id.id),('order_id.state','in',['doing','done'])])
            confirm_qty=sum(delivery_line.delivery_qty for delivery_line in sale_delivery_lines)
            if line.change_product_uom_qty<confirm_qty:
                raise UserError(_('变更后数量不能小于发货通知单已审核发货数量！'))
        #锁定状态的订单先解锁
        if self.env.user.has_group('sale.group_auto_done_setting') and self.old_order_id.state=='done':
            self.old_order_id.action_unlock()
            
        for line in self.order_line:
            line.old_line_id.product_uom_qty=line.change_product_uom_qty
            line.old_line_id.price_unit=line.change_price_unit
            line.old_line_id.tax_id=line.change_tax_id.ids
            sale_delivery_lines=self.env['sale.delivery.line'].search([('sale_line_id','=',line.old_line_id.id),('order_id.state','in',['draft','submit'])])
            for delivery_line in sale_delivery_lines:
                delivery_line.delivery_qty=delivery_line.product_uom_qty-delivery_line.order_qty_delivered
        self.old_order_id.commitment_date=self.change_commitment_date
        self.old_order_id.user_id=self.change_user_id
        self.old_order_id.payment_term_id=self.change_payment_term_id
        self.state='done'

    def button_submit(self):
        for line in self.order_line:
            if line.change_product_uom_qty<=0:
                raise UserError(_('变更后数量不能小于已发货数量！'))
            if line.change_product_uom_qty<line.old_line_id.qty_delivered:
                raise UserError(_('变更后数量不能小于已发货数量！'))
            if line.change_product_uom_qty>0 and line.old_line_id.product_uom_qty== line.old_line_id.qty_delivered:
                raise UserError(_('产品%s 已发完！')%line.product_id.name)
            #验证已审核发货通知单的发货数量
            sale_delivery_lines=self.env['sale.delivery.line'].search([('sale_line_id','=',line.old_line_id.id),('order_id.state','in',['doing','done'])])
            confirm_qty=sum(delivery_line.delivery_qty for delivery_line in sale_delivery_lines)
            if line.change_product_uom_qty<confirm_qty:
                raise UserError(_('变更后数量不能小于发货通知单已审核发货数量！'))
        self.state='submit'

    def button_change_draft(self):
        self.state='draft'
    
class SaleChangeLine(models.Model):
    _name="sale.change.line"
    _description="销售变更明细"
    
    @api.depends('change_product_uom_qty','change_price_unit', 'change_price_unit', 'change_tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.change_price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.change_tax_id.compute_all(price, line.order_id.currency_id, line.change_product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    change_product_uom_qty=fields.Float(string='变更后数量')
    change_price_unit=fields.Float(string='变更后单价')
    change_tax_id=fields.Many2many("account.tax",'change_line_tax_rel','change_line_id','tax_id',string='变更后税率', domain=['|', ('active', '=', False), ('active', '=', True)])
    
    old_line_id=fields.Many2one('sale.order.line',string='源明细')
    
    order_id = fields.Many2one('sale.change', string='销售变更', required=True, ondelete='cascade', index=True, copy=False)
    name = fields.Text(string='说明', required=True)
    sequence = fields.Integer(string='序号', default=1)
    price_unit = fields.Float(string='单价', digits='Product Price',default=1.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='小计', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='税额', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='总计', readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='税率', domain=['|', ('active', '=', False), ('active', '=', True)])
    discount = fields.Float(string='折扣 (%)', digits='Discount')
    product_id = fields.Many2one(
        'product.product', string='产品',
        change_default=True, ondelete='restrict')  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='产品',
        related="product_id.product_tmpl_id")
    product_uom_qty = fields.Float(string='原数量', digits='Product Unit of Measure')
    product_uom = fields.Many2one('uom.uom', string='单位')

    qty_delivered = fields.Float(related="old_line_id.qty_delivered",string='已发货', digits='Product Unit of Measure')
    qty_invoiced = fields.Float(related="old_line_id.qty_invoiced",string='已开票', digits='Product Unit of Measure')
    currency_id = fields.Many2one(related='order_id.currency_id', depends=['order_id'], store=True, string='币种')
    company_id = fields.Many2one(related='order_id.company_id', string='公司', store=True, readonly=True, index=True)


