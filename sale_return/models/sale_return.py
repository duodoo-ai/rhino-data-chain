# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class SaleReturn(models.Model):
    _name = "sale.return"
    _description="""销售退货"""
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order="create_date desc"
    _check_company_auto = True
    
    @api.model
    def _default_picking_type(self):
        return self._get_picking_type(self.env.context.get('company_id') or self.env.company.id)
    
    @api.model
    def _get_picking_type(self, company_id):
        return_sequence=self.env['ir.sequence'].search([('name','=','销售退货')],limit=1)
        return_picking_type = self.env['stock.picking.type'].search([('sequence_id', '=', return_sequence.id), '|',('warehouse_id', '=', False),('warehouse_id.company_id', '=', company_id)])
        return return_picking_type[:1]
    
    @api.depends('lines.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    name=fields.Char(string='退货编号',default='/',copy=False)
    partner_id = fields.Many2one(
        'res.partner', string='客户', readonly=True,
        required=True, change_default=True, index=True, tracking=1,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    return_date=fields.Date(string='退货日期',required=True, default=lambda self: fields.date.today())
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True, default=lambda self: self.env.company.id)

    currency_id = fields.Many2one('res.currency', string='币种', required=True,
        default=lambda self: self.env.company.currency_id.id)
    user_id = fields.Many2one(
        'res.users', string='业务人员', index=True,
        default=lambda self: self.env.user, check_company=True)
    department_id = fields.Many2one('hr.department', string='部门')
    sale_id=fields.Many2one('sale.order',string='原销售订单',domain="""[
                ('state','in',['sale','done']),'|',
                ('company_id', '=', False),
                ('company_id', '=', company_id)]""",
        check_company=True)
    team_id = fields.Many2one('crm.team', string='销售团队', related="sale_id.team_id",store=True)
    note=fields.Text(string='退货说明')
    currency_rate = fields.Float("Currency Rate",related='sale_id.currency_rate',store=True)
    
    amount_untaxed = fields.Monetary(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='税率设置', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='合计', store=True, readonly=True, compute='_amount_all')
    state=fields.Selection([('draft','草稿'),('unexamine','待审核'),('pass','通过'),('unpass','不通过'),('cancel','取消')],string=u"状态",default="draft")
    lines=fields.One2many('sale.return.line','order_id',string='退货明细')
    
    picking_type_id = fields.Many2one('stock.picking.type', string='作业类别', required=True, default=_default_picking_type, domain="['|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)]",)

    def create(self,vals):
        if vals.get('name','/')=='/':
            vals['name'] = self.env['ir.sequence'].with_context(force_company=self.env.user.company_id.id).next_by_code(
                'sale.return') or '/'
        return super(SaleReturn, self).create(vals)
    
    def unlink(self):
        for record in self:
            if record.state=='done':
                raise UserError(_("不能删除已完成的单据！"))
            pickings=self.env['stock.picking'].search([('sale_return_id','=',record.id)])
            if pickings:
                for picking in pickings:
                    if picking.state=='done':
                        raise UserError(_("存在已完成的退货单，不能删除！"))
                pickings.unlink()
                
        return super(SaleReturn, self).unlink()
    
    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            employee_id=self.env['hr.employee'].search([('user_id','=',self.user_id.id)],limit=1)
            if employee_id:
                self.department_id=employee_id.department_id.id
                
    @api.onchange('sale_id')
    def onchange_sale_id(self):
        if self.sale_id:
            self.partner_id=self.sale_id.partner_id.id
            self.currency_id=self.sale_id.currency_id.id
            self.company_id=self.sale_id.company_id.id
            self.lines=False

    def button_select(self):
        self.env['return.sale.select'].search([]).unlink()
        return_select_obj=self.env['return.sale.select'].create({'sale_id':self.sale_id.id,'sale_return_id':self.id})
        context = dict(self.env.context or {})
        view = self.env.ref('sale_return.view_return_sale_select_form')
        return {
            'name': _('销售退货查询'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'return.sale.select',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id':return_select_obj.id,
            'context': context,  
        }
        
    def button_confirm(self):
        if not self.lines:
            raise UserError(_('请查询先添加明细！'))
        for line in self.lines:
            if line.return_qty<=0:
                raise UserError(_('明细%s退货数量必须大于0！')%line.name)
            if line.qty_delivered<=0:
                raise UserError(_('明细%s已接收数量必须大于0！')%line.name)
            if line.return_qty>line.qty_delivered:
                raise UserError(_('明细%s退货数量不能大于已接收数量！')%line.name)
        self.state='unexamine'
        
    def button_pass(self):
        self.create_return_picking_val()
        self.state='pass'
        
    def button_unpass(self):
        self.state='unpass'
        
    def button_cancel(self):
        pickings=self.env['stock.picking'].search([('sale_return_id','=',self.id)])
        if pickings:
            for picking in pickings:
                if picking.state=='done':
                    raise UserError(_("存在已完成的退货入库单，不能取消销售退货！"))
            pickings.unlink()
        self.state='draft'
        
    def create_return_picking_val(self):
        picking = self.env['stock.picking']
        location_src_id, vendorloc = self.env['stock.warehouse']._get_partner_locations()
        picking_values = {
            'partner_id': self.partner_id.id,
            'picking_type_id': self.picking_type_id.id,
            'move_type': 'direct',
            'location_id': location_src_id.id,
            'location_dest_id': self.picking_type_id.default_location_dest_id.id,
            'scheduled_date': datetime.now(),
            'origin': self.name,
            'sale_return_id':self.id
        }
        picking_id = picking.create(picking_values)
        for line in self.lines:
            move_values = {
                'picking_id': picking_id.id,
                'name': line.name,
                'company_id': self.company_id.id,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.return_qty,
                'partner_id': self.partner_id.id,
                'location_id': location_src_id.id,
                'location_dest_id': self.picking_type_id.default_location_dest_id.id,
                'origin': self.name,
                'picking_type_id': self.picking_type_id.id,
                'warehouse_id': self.picking_type_id.warehouse_id.id,
                'date': datetime.now(),
                # 'date_expected': datetime.now(),
                'to_refund':True,
                'price_unit':line.price_unit,
                'sale_id': self.sale_id.id,
                'sale_line_id': line.sale_line_id.id,
                # 'tax_id':self.sale_id.tax_id.id,
            }
            self.env['stock.move'].sudo().create(move_values)
        picking_id.action_confirm()
        picking_id.action_assign()
    
    
class SaleReturnLine(models.Model):
    _name="sale.return.line"
    _description="""销售退货明细"""
    
    @api.depends('return_qty', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.tax_id.compute_all(
                vals['price_unit'],
                vals['currency_id'],
                vals['return_qty'],
                vals['product'],
                vals['partner'])
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })
    
    order_id=fields.Many2one('sale.return',string='采购退货')
    sequence=fields.Integer(string='序号')
    sale_line_id=fields.Many2one('sale.order.line',string='源明细',required=True)
    product_id=fields.Many2one('product.product',string='产品')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    name=fields.Text(string='说明')
    qty_delivered=fields.Float(string='已送货',related="sale_line_id.qty_delivered")
    return_qty=fields.Float(string='退货数量')
    product_uom = fields.Many2one('uom.uom', string='单位')
    price_unit=fields.Float(string='单价')
    tax_id = fields.Many2many('account.tax', string='税率')
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='币种', readonly=True)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='小计', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='总计', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='税额', store=True)
    company_id=fields.Many2one('res.company',related="order_id.company_id",string='公司')
    
    @api.onchange('sale_line_id')
    def onchange_sale_line_id(self):
        if self.sale_line_id:
            self.product_id=self.sale_line_id.product_id.id
            self.name=self.sale_line_id.name
            self.product_uom=self.sale_line_id.product_uom.id
            self.price_unit=self.sale_line_id.price_unit
            self.tax_id=self.sale_line_id.tax_id.ids
    
    def _prepare_compute_all_values(self):
        self.ensure_one()
        return {
            'price_unit': self.price_unit,
            'currency_id': self.order_id.currency_id,
            'return_qty': self.return_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }
