# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from odoo import api, fields, models, _
# from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleDelivery(models.Model):
    _name = "sale.delivery"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "发货通知单"
    _order = "create_date desc"
    _check_company_auto = True

    @api.model
    def _default_picking_type(self):
        return self._get_picking_type(self.env.context.get('company_id') or self.env.company.id)

    @api.model
    def _get_picking_type(self, company_id):
        delivery_picking_type = self.env['stock.picking.type'].search(
            [('code', '=', 'outgoing'), '|', ('warehouse_id', '=', False),
             ('warehouse_id.company_id', '=', company_id)])
        return delivery_picking_type[:1]

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

    name = fields.Char(string='编号', default='/', copy=False)
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company.id)
    currency_id = fields.Many2one("res.currency", related='sale_id.currency_id', string=u"币种", readonly=True)
    sale_id = fields.Many2one('sale.order', string='销售订单', domain="""[
                ('state','in',['sale','done']),'|',
                ('company_id', '=', False),
                ('company_id', '=', company_id)]""",
                              check_company=True, required=True)
    user_id = fields.Many2one('res.users', string='业务员', index=True, tracking=2, default=lambda self: self.env.user)
    team_id = fields.Many2one('crm.team', string='销售团队', related="sale_id.team_id", store=True)
    partner_id = fields.Many2one('res.partner', string='客户', related="sale_id.partner_id", store=True)
    partner_invoice_id = fields.Many2one('res.partner', string='开票地址', related="sale_id.partner_invoice_id",
                                         store=True)
    delivery_address = fields.Char(string='交货地址')
    receiver = fields.Many2one('res.partner', string='收货人')
    phone = fields.Char(string='联系电话')
    partner_shipping_id = fields.Many2one('res.partner', string='交货地', related="sale_id.partner_shipping_id",
                                          store=True)
    date_order = fields.Datetime(string='单据日期', required=True, readonly=True, index=True, copy=False,
                                 default=fields.Datetime.now)
    commitment_date = fields.Datetime(string='交付日期',
                                      copy=False,
                                      readonly=True,
                                      related="sale_id.commitment_date",
                                      store=True)
    state = fields.Selection(
        [('draft', '草稿'), ('submit', '已提交'), ('doing', '发货中'), ('done', '已完成'), ('cancel', '取消')], string=u"状态",
        default="draft")
    order_line = fields.One2many('sale.delivery.line', 'order_id', string='明细')

    amount_untaxed = fields.Monetary(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=True)
    amount_tax = fields.Monetary(string='税率设置', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='合计', store=True, readonly=True, compute='_amount_all')
    currency_rate = fields.Float("汇率", related='sale_id.currency_rate', store=True)
    picking_type_id = fields.Many2one('stock.picking.type', string='作业类别', required=True,
                                      default=_default_picking_type,
                                      domain="['|', ('warehouse_id', '=', False), ('warehouse_id.company_id', '=', company_id)]", )
    note = fields.Text(string='备注')
    is_manual_picking = fields.Boolean('手动发货', default=True)
    is_quto_picking = fields.Boolean('手动发货', default=False)
    contacts_id = fields.Many2one('res.partner.contacts', string='联系人')
    contacts_name = fields.Char(string='联系人姓名')
    city_id = fields.Many2one('city.city', string='联系人所在城市')
    street = fields.Text(string='详细地址')
    delivered = fields.Boolean(string='已创建发货', default=False)
    delivered_state = fields.Boolean(string='发货状态', compute='_compute_delivered_state')

    def create(self, vals):
        '''创建'''
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.delivery') or '/'
        return super(SaleDelivery, self).create(vals)

    def unlink(self):
        for record in self:
            if record.state == 'done':
                raise UserError(_("不能删除已完成的单据！"))
            pickings = self.env['stock.picking'].search([('sale_delivery_id', '=', record.id)])
            if pickings:
                for picking in pickings:
                    if picking.state == 'done':
                        raise UserError(_("存在已完成的发货单，不能删除！"))
                pickings.unlink()

        return super(SaleDelivery, self).unlink()

    @api.onchange('sale_id')
    def onchange_sale_id(self):
        if self.sale_id:
            self.order_line = False
            order_lines = []
            for line in self.sale_id.order_line:
                vals = {
                    'sale_line_id': line.id,
                    'delivery_qty': line.product_uom_qty - line.qty_delivered
                }
                order_lines.append((0, 0, vals))
            self.order_line = order_lines

    @api.onchange('receiver')
    def onchange_receiver(self):
        if self.receiver:
            receiver = self.receiver
            delivery_address = (receiver.state_id.name or '') + (receiver.city or '') + (receiver.street or '') + (
                        receiver.street2 or '')
            self.delivery_address = delivery_address
            self.phone = receiver.phone

    def action_submit(self):
        # 验证发货数量与已发数量
        for line in self.order_line:
            if line.delivery_qty + line.order_qty_delivered > line.product_uom_qty:
                raise UserError(_("发货数量加已发数量不能大于订单数！"))
            if line.delivery_qty <= 0:
                raise UserError(_('明细%s发货数量必须大于0！') % line.name)
        self.state = "submit"

    def action_flow(self):
        for line in self.order_line:
            if line.delivery_qty + line.order_qty_delivered > line.product_uom_qty:
                raise UserError(_("发货数量加已发数量不能大于订单数！"))
            if line.delivery_qty <= 0:
                raise UserError(_('明细%s发货数量必须大于0！') % line.name)
        self.send_delivery_products()
        # 创建出货质检
        self.state = 'doing'

    def action_cancel(self):
        pickings = self.env['stock.picking'].search([('sale_delivery_id', '=', self.id)])
        if pickings:
            for picking in pickings:
                if picking.state == 'done':
                    raise UserError(_("存在已完成的发货单，不能取消发货通知单"))
        pickings.unlink()
        self.state = 'cancel'

    def action_draft(self):
        self.state = 'draft'

    def send_delivery_products(self):
        picking = self.env['stock.picking']
        customerloc, location_dest_id = self.env['stock.warehouse']._get_partner_locations()
        picking_values = {
            'partner_id': self.partner_id.id,
            'picking_type_id': self.picking_type_id.id,
            'move_type': 'direct',
            'location_id': self.picking_type_id.default_location_src_id.id,
            'location_dest_id': customerloc.id,
            'scheduled_date': self.commitment_date or datetime.now(),
            'origin': self.name,
            'sale_id': self.sale_id.id,
            'sale_delivery_id': self.id,
            'note': self.note,
            # 'project_code':self.project_code
        }
        picking_id = picking.create(picking_values)
        for line in self.order_line:
            move_values = {
                'picking_id': picking_id.id,
                'name': line.name,
                'company_id': self.company_id.id,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'product_uom_qty': line.delivery_qty,
                'partner_id': self.partner_id.id,
                'location_id': self.picking_type_id.default_location_src_id.id,
                'location_dest_id': customerloc.id,
                'origin': self.name,
                'picking_type_id': self.picking_type_id.id,
                'warehouse_id': self.picking_type_id.warehouse_id.id,
                'date': datetime.now(),
                'sale_line_id': line.sale_line_id.id,
                'sale_delivery_line_id': line.id,
                'price_unit': line.price_unit,
                # 'tax_id': line.tax_id.id,
                # 'amount': line.price_total or 0,
                # 'currency_id': line.currency_id.id,
                # 'unchecked_qty': line.product_uom_qty,
                # 'unchecked_amount': line.price_total
            }
            self.env['stock.move'].sudo().create(move_values)
        picking_id.action_confirm()
        picking_id.action_assign()


class SaleDeliveryLine(models.Model):
    _name = "sale.delivery.line"
    _description = "发货通知单明细"

    @api.depends('delivery_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.delivery_qty,
                                            product=line.product_id, partner=line.order_id.partner_shipping_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    # @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    # def _compute_qty_delivered(self):
    #     for line in self:  # TODO: maybe one day, this should be done in SQL for performance sake
    #         qty = 0.0
    #         outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
    #         for move in outgoing_moves:
    #             if move.state != 'done':
    #                 continue
    #             qty += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom,
    #                                                       rounding_method='HALF-UP')
    #         for move in incoming_moves:
    #             if move.state != 'done':
    #                 continue
    #             qty -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom,
    #                                                       rounding_method='HALF-UP')
    #         line.qty_delivered = qty

    order_id = fields.Many2one('sale.delivery', string='发货通知', required=True, ondelete='cascade', index=True,
                               copy=False)
    sale_line_id = fields.Many2one('sale.order.line', string='销售订单明细')
    sequence = fields.Integer(string='序号', default=10)
    name = fields.Text(string='说明', related="sale_line_id.name", store=True)

    delivery_qty = fields.Float(string='发货数量', digits='Product Unit of Measure')
    price_unit = fields.Float(related="sale_line_id.price_unit", string='单价', digits='Product Price', store=True)
    discount = fields.Float(related="sale_line_id.discount", string='折扣 (%)', digits='Discount', store=True)
    tax_id = fields.Many2many('account.tax', string='税率', related="sale_line_id.tax_id")

    product_id = fields.Many2one('product.product', related="sale_line_id.product_id", string='产品',
                                 store=True)  # Unrequired company
    product_template_id = fields.Many2one(
        'product.template', string='产品模板',
        related="product_id.product_tmpl_id", domain=[('sale_ok', '=', True)])
    product_uom_qty = fields.Float(related="sale_line_id.product_uom_qty", string='订单数量',
                                   digits='Product Unit of Measure', store=True)
    product_uom = fields.Many2one('uom.uom', related="sale_line_id.product_uom", string='单位', store=True)
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)

    qty_invoiced = fields.Float(related="sale_line_id.qty_invoiced", string='已开票', digits='Product Unit of Measure',
                                store=True)
    order_qty_delivered = fields.Float(related="sale_line_id.qty_delivered", string='已送货',
                                       digits='Product Unit of Measure', store=True)
    qty_delivered = fields.Float(string='已送货', copy=False, compute='_compute_qty_delivered', compute_sudo=True,
                                 store=True, digits='Product Unit of Measure', default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='小计', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='税额', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='总计', readonly=True, store=True)

    salesman_id = fields.Many2one(related='order_id.user_id', store=True, string='销售人员', readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', depends=['order_id'], store=True, string='币种',
                                  readonly=True)
    company_id = fields.Many2one(related='order_id.company_id', string='公司', store=True, readonly=True, index=True)
    order_partner_id = fields.Many2one(related='order_id.partner_id', store=True, string='客户', readonly=False)
    move_ids = fields.One2many('stock.move', 'sale_delivery_line_id', string='库存移动')

    def _get_outgoing_incoming_moves(self):
        outgoing_moves = self.env['stock.move']
        incoming_moves = self.env['stock.move']

        for move in self.move_ids.filtered(
                lambda r: r.state != 'cancel' and not r.scrapped and self.product_id == r.product_id):
            if move.location_dest_id.usage == "customer":
                if not move.origin_returned_move_id or (move.origin_returned_move_id and move.to_refund):
                    outgoing_moves |= move
            elif move.location_dest_id.usage != "customer" and move.to_refund:
                incoming_moves |= move

        return outgoing_moves, incoming_moves
