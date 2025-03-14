# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PurchaseReturn(models.Model):
    _name = "purchase.return"
    _description = """采购退货"""
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = "create_date desc"
    _check_company_auto = True

    @api.model
    def _default_picking_type(self):
        return self._get_picking_type(self.env.context.get('company_id') or self.env.company.id)

    @api.model
    def _get_picking_type(self, company_id):
        return_sequence = self.env['ir.sequence'].search([('name', '=', '采购退货')], limit=1)
        return_picking_type = self.env['stock.picking.type'].search(
            [('sequence_id', '=', return_sequence.id), '|', ('warehouse_id', '=', False),
             ('warehouse_id.company_id', '=', company_id)])
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

    #     @api.depends('lines.move_ids.returned_move_ids',
    #                  'lines.move_ids.state',
    #                  'lines.move_ids.picking_id')
    #     def _compute_picking(self):
    #         for order in self:
    #             pickings = self.env['stock.picking']
    #             for line in order.lines:
    #                 moves = line.move_ids | line.move_ids.mapped('returned_move_ids')
    #                 pickings |= moves.mapped('picking_id')
    #             order.picking_ids = pickings
    #             order.picking_count = len(pickings)

    name = fields.Char(string='退货编号', default='/', copy=False)
    partner_id = fields.Many2one('res.partner', string='供应商', change_default=True, tracking=True,
                                 domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                 help="You can find a vendor by its Name, TIN, Email or Internal Reference.")
    return_date = fields.Date(string='退货日期', required=True, default=lambda self: fields.date.today())
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True,
                                 default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', string='币种', required=True,
                                  default=lambda self: self.env.company.currency_id.id)
    user_id = fields.Many2one(
        'res.users', string='人员', index=True,
        default=lambda self: self.env.user, check_company=True)
    department_id = fields.Many2one('hr.department', string='部门')
    purchase_id = fields.Many2one('purchase.order', string='原采购订单', domain="""[
                ('state','in',['purchase','done']),'|',
                ('company_id', '=', False),
                ('company_id', '=', company_id)]""",
                                  check_company=True)
    note = fields.Text(string='退货说明')
    amount_untaxed = fields.Monetary(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='税率设置', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='合计', store=True, readonly=True, compute='_amount_all')
    state = fields.Selection(
        [('draft', '草稿'), ('unexamine', '待审核'), ('pass', '通过'), ('unpass', '不通过'), ('cancel', '取消')], string=u"状态",
        default="draft")
    lines = fields.One2many('purchase.return.line', 'order_id', string='退货明细')
    currency_rate = fields.Float("Currency Rate", related='purchase_id.currency_rate', store=True)

    #     picking_count = fields.Integer(compute='_compute_picking', string='单数', default=0, store=True)
    #     picking_ids = fields.Many2many('stock.picking', compute='_compute_picking', string='入库单', copy=False, store=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='作业类别', required=True,
                                      default=_default_picking_type,
                                      domain="['|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)]", )
    picking_id = fields.Many2one('stock.picking', string='出库单号', copy=False)

    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].with_context(force_company=self.env.user.company_id.id).next_by_code(
                'purchase.return') or '/'
        return super(PurchaseReturn, self).create(vals)

    def unlink(self):
        for order in self:
            if order.state != "draft":
                raise UserError(_('只有草稿状态的订单才可以删除！'))
        return super(PurchaseReturn, self).unlink()

    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            employee_id = self.env['hr.employee'].search([('user_id', '=', self.user_id.id)], limit=1)
            if employee_id:
                self.department_id = employee_id.department_id.id

    @api.onchange('purchase_id')
    def onchange_purchase_id(self):
        if self.purchase_id:
            self.partner_id = self.purchase_id.partner_id.id
            self.currency_id = self.purchase_id.currency_id.id
            self.company_id = self.purchase_id.company_id.id
            self.lines = False

    #             self.picking_type_id=self.old_order_id.picking_type_id.id

    def button_select(self):
        self.env['return.select'].search([]).unlink()
        return_select_obj = self.env['return.select'].create(
            {'purchase_id': self.purchase_id.id, 'purchase_return_id': self.id})
        context = dict(self.env.context or {})
        view = self.env.ref('purchase_return.view_return_select_form')
        return {
            'name': _('采购退货查询'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'return.select',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': return_select_obj.id,
            'context': context,
        }

    def button_confirm(self):
        if not self.lines:
            raise UserError(_('请查询先添加明细！'))
        for line in self.lines:
            if line.return_qty <= 0:
                raise UserError(_('明细%s退货数量必须大于0！') % line.name)
            if line.qty_received <= 0:
                raise UserError(_('明细%s已接收数量必须大于0！') % line.name)
            if line.return_qty > line.qty_received:
                raise UserError(_('明细%s退货数量不能大于已接收数量！') % line.name)
        self.state = 'unexamine'

    def button_pass(self):
        self.send_return_products()
        self.state = 'pass'

    def button_unpass(self):
        self.state = 'unpass'

    def button_cancel(self):
        self.state = 'draft'

    def send_return_products(self):
        if not self.picking_id:
            picking = self.env['stock.picking']
            customerloc, location_dest_id = self.env['stock.warehouse']._get_partner_locations()
            picking_values = {
                'partner_id': self.partner_id.id,
                'picking_type_id': self.picking_type_id.id,
                'move_type': 'direct',
                'location_id': self.picking_type_id.default_location_src_id.id,
                'location_dest_id': location_dest_id.id,
                'scheduled_date': datetime.now(),
                'origin': self.name,
            }
            picking_id = picking.create(picking_values)
            self.write({'picking_id': picking_id.id})
            for line in self.lines:
                move_values = {
                    'picking_id': picking_id.id,
                    'purchase_line_id': line.purchase_line_id.id,
                    'name': line.name,
                    'company_id': self.company_id.id,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_uom.id,
                    'product_uom_qty': line.return_qty,
                    'partner_id': self.partner_id.id,
                    'location_id': self.picking_type_id.default_location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                    'origin': self.name,
                    'picking_type_id': self.picking_type_id.id,
                    'warehouse_id': self.picking_type_id.warehouse_id.id,
                    'date': datetime.now(),
                    'price_unit': line.price_unit
                }
                self.env['stock.move'].sudo().create(move_values)
            picking_id.action_confirm()
            picking_id.action_assign()


class PurchaseReturnLine(models.Model):
    _name = "purchase.return.line"
    _description = """采购退货明细"""
    _check_company_auto = True

    @api.depends('return_qty', 'price_unit', 'taxes_id')
    def _compute_amount(self):
        for line in self:
            vals = line._prepare_compute_all_values()
            taxes = line.taxes_id.compute_all(
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

    order_id = fields.Many2one('purchase.return', string='采购退货')
    sequence = fields.Integer(string='序号')
    purchase_line_id = fields.Many2one('purchase.order.line', string='源明细', required=True)
    product_id = fields.Many2one('product.product', string='产品', related="purchase_line_id.product_id", store=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    name = fields.Text(string='说明', related="purchase_line_id.name", store=True)
    qty_received = fields.Float(string='已接收', related="purchase_line_id.qty_received")
    return_qty = fields.Float(string='退货数量')
    product_uom = fields.Many2one('uom.uom', string='单位', related="purchase_line_id.product_uom", store=True)
    price_unit = fields.Float(string='单价', related="purchase_line_id.price_unit", store=True)
    taxes_id = fields.Many2many('account.tax', string='税率', related="purchase_line_id.taxes_id")
    currency_id = fields.Many2one(related='order_id.currency_id', store=True, string='币种', readonly=True)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='小计', store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='总计', store=True)
    price_tax = fields.Float(compute='_compute_amount', string='税', store=True)
    company_id = fields.Many2one('res.company', related="order_id.company_id", string='公司')

    #     move_ids = fields.One2many('stock.move', 'purchase_line_id', string='Reservation', readonly=True, ondelete='set null', copy=False)

    @api.constrains('qty_received', 'return_qty')
    def default_qty_uniq(self):
        if self.return_qty <= 0:
            raise UserError(_('明细%s退货数量必须大于0！') % self.name)
        if self.qty_received <= 0:
            raise UserError(_('明细%s已接收数量必须大于0！') % self.name)
        if self.return_qty > self.qty_received:
            raise UserError(_('明细%s退货数量不能大于已接收数量！') % self.name)

    def _prepare_compute_all_values(self):
        self.ensure_one()
        return {
            'price_unit': self.price_unit,
            'currency_id': self.order_id.currency_id,
            'return_qty': self.return_qty,
            'product': self.product_id,
            'partner': self.order_id.partner_id,
        }
