# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, time
import logging
_logger = logging.getLogger(__name__)

class PurchaseChangeOrder(models.Model):
    _name="purchase.change"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description=u"采购变更单"
    _order="create_date desc"
    
    @api.depends('order_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })
            
    name = fields.Char('变更单号', required=True, index=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='供应商')
    partner_ref = fields.Char('供应商参考')
    currency_id = fields.Many2one('res.currency', string='币种',default=lambda self: self.env.company.currency_id.id)
    date_order = fields.Datetime(string='单据日期', required=True, copy=False, default=fields.Datetime.now)
    old_order_id=fields.Many2one('purchase.order',string='源采购订单',domain="""[
                ('state','in',['purchase','done']),'|',
                ('company_id', '=', False),
                ('company_id', '=', company_id)]""",
        check_company=True,required=True)
    date_planned = fields.Datetime(string='接受日期')
    change_date_planned=fields.Datetime(string='变更接受日期')
    user_id = fields.Many2one('res.users', string='采购员')
    change_user_id = fields.Many2one(
        'res.users', string='变更人', index=True, tracking=True,
        default=lambda self: self.env.user, check_company=True)
    state = fields.Selection([('draft','草稿'),('submit','已提交'),('done','完成')],string='状态',default="draft")
    order_line=fields.One2many('purchase.change.line','order_id',string='明细')
    currency_rate = fields.Float("Currency Rate",related='old_order_id.currency_rate',store=True)
    amount_untaxed = fields.Float(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=True, digits=(16, 6))
    amount_tax = fields.Float(string='税率设置', store=True, readonly=True, compute='_amount_all', digits=(16, 6))
    amount_total = fields.Float(string='合计', store=True, readonly=True, compute='_amount_all', digits=(16, 6))

    def create(self,vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].with_context(force_company=self.env.user.company_id.id).next_by_code(
                'purchase.change') or '/'
        return super(PurchaseChangeOrder, self).create(vals)
    
    @api.onchange('old_order_id')
    def onchange_old_order_id(self):
        if self.old_order_id:
            self.order_line=False
            self.partner_id=self.old_order_id.partner_id.id
            self.partner_ref=self.old_order_id.partner_ref
            self.currency_id=self.old_order_id.currency_id.id
            self.company_id=self.old_order_id.company_id.id
            self.date_planned=self.old_order_id.date_planned
            self.change_date_planned=self.old_order_id.date_planned
            self.user_id=self.old_order_id.user_id.id
    
            order_lines = []
            for line in self.old_order_id.order_line:
                vals={
                    'old_line_id':line.id,
                    'name': line.name or '',
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_po_id.id,
                    'product_qty': line.product_qty,
                    'change_product_qty':line.product_qty,
                    'price_unit': line.price_unit,
                    'change_price_unit': line.price_unit,
                    'taxes_id': [(6, 0, line.taxes_id.ids)],
                    'date_planned': line.date_planned,
                }
                order_lines.append((0, 0, vals))
            self.order_line = order_lines
    
    def button_submit(self):
        self.state='submit'

    def button_change_done(self):
        for line in self.order_line:
            if  line.change_product_qty<line.old_line_id.qty_received:
                raise UserError(_('变更后数量不能小于已接收数量！'))
            if line.change_product_qty>0 and line.old_line_id.product_qty== line.old_line_id.qty_received:
                raise UserError(_('产品%s 已接收完！')%line.product_id.name)
            
            #验证暂收数量
            move_obj=self.env['stock.move'].search([('purchase_line_id','=',line.old_line_id.id),('state','=','done')])
            temporarily_qty=0
            for move in move_obj:
                if move.picking_id.picking_type_id.is_temporarily:
                    temporarily_qty+=move.quantity_done or 0
            if line.change_product_qty<temporarily_qty:
                raise UserError(_('变更后数量不能小于已暂收数量！'))
            
        for line in self.order_line:
            line.old_line_id.product_qty=line.change_product_qty
            line.old_line_id.price_unit=line.change_price_unit
#                 picking_obj=self.env['stock.picking'].search([('purchase_id','=',self.old_order_id.id),('state','!=','done')])
            move_obj=self.env['stock.move'].search([('purchase_line_id','=',line.old_line_id.id),('state','=','done')])
            temporarily_qty=0
            for move in move_obj:
                if move.picking_id.picking_type_id.is_temporarily:
                    temporarily_qty+=move.quantity_done or 0
        self.old_order_id.date_planned=self.change_date_planned
        self.old_order_id.user_id=self.change_user_id
        self.state='done'
            
    def button_change_draft(self):
        self.state='draft'
        
class PurchaseChangeLine(models.Model):
    _name="purchase.change.line"
    _description="采购变更明细"
    
    @api.depends('product_qty','change_product_qty','change_price_unit', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.taxes_id.compute_all(
                vals['price_unit'],
                vals['currency_id'],
                vals['product_qty'],
                vals['product'],
                vals['partner'])
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    order_id = fields.Many2one('purchase.change', string='采购变更', index=True, required=True, ondelete='cascade')

    sequence = fields.Integer(string='序号', default=10)
    old_line_id=fields.Many2one('purchase.order.line',string='源明细')
    product_id = fields.Many2one('product.product', string='产品')
    name = fields.Text(string='说明', required=True)
    product_qty = fields.Float(string='原数量', digits='Product Unit of Measure')
    change_product_qty=fields.Float(string='变更后数量', digits='Product Unit of Measure')
    product_uom = fields.Many2one('uom.uom', string='单位', domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    taxes_id = fields.Many2many('account.tax', string='税率', domain=['|', ('active', '=', False), ('active', '=', True)])
    
    price_unit = fields.Float(string='原单价', digits=(16, 6))
    change_price_unit=fields.Float(string='变更后单价', digits=(16, 6))
    qty_received = fields.Float(string=u"已接收", related="old_line_id.qty_received", digits='Product Unit of Measure')
    price_subtotal = fields.Float(compute='_compute_amount', string='小计', store=True, digits=(16, 6))
    price_total = fields.Float(compute='_compute_amount', string='总计', store=True, digits=(16, 6))
    price_tax = fields.Float(compute='_compute_amount', string='税', store=True, digits=(16, 6))
    company_id = fields.Many2one('res.company', related='order_id.company_id', string='公司', store=True, readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', depends=['order_id'], store=True, string='币种')
    date_planned = fields.Datetime(string='计划日期', index=True)

    def _prepare_compute_all_values(self):
        self.ensure_one()
        return {
            'price_unit': self.change_price_unit,
            'currency_id': self.order_id.currency_id,
            'product_qty': self.change_product_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }
        
    def _create_stock_picking(self,qty):
        move_vals={
                 'product_id': self.product_id.id,
                 'name': self.name,
                 'picking_type_id': self.order_id.old_order_id.picking_type_id.id,
                 'purchase_line_id': self.old_line_id.id,
                 'product_uom_qty': qty,
                 'product_uom': self.product_uom.id,
                 'location_dest_id': self.order_id.old_order_id._get_destination_location(),
                 'location_id': self.order_id.partner_id.property_stock_supplier.id,
                 'price_unit':self.price_unit or 0,
                 }
        values = {
            'name': '/',
            'origin': self.order_id.name,
            'purchase_id':self.order_id.old_order_id.id,
            'partner_id': self.order_id.partner_id.id,
            'picking_type_id': self.order_id.old_order_id.picking_type_id.id,
            'location_dest_id': self.order_id.old_order_id._get_destination_location(),
            'location_id': self.order_id.partner_id.property_stock_supplier.id,
            'move_ids_without_package': [(0, 0, move_vals)]
        }
        picking_id = self.env["stock.picking"].create(values)
        picking_id.action_confirm()
        picking_id.action_assign()


class StockPickingTypeInherit(models.Model):
    _inherit = "stock.picking.type"

    is_temporarily = fields.Boolean(string='暂收类型')
