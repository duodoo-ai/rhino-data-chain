# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round, float_is_zero

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    
    @api.depends('order_line.cncw_invoice_lines.move_id')
    def _compute_cncw_invoice(self):
        for order in self:
            invoices = order.mapped('order_line.cncw_invoice_lines.move_id')
            order.cncw_invoice_ids = invoices
            order.cncw_invoice_count = len(invoices)
            
    @api.depends('state', 'order_line.cncw_qty_to_invoice')
    def _get_cncw_invoiced(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.cncw_invoice_status = 'no'
                continue

            if any(
                not float_is_zero(line.cncw_qty_to_invoice, precision_digits=precision)
                for line in order.order_line.filtered(lambda l: not l.display_type)
            ):
                order.cncw_invoice_status = 'to invoice'
            elif (
                all(
                    float_is_zero(line.cncw_qty_to_invoice, precision_digits=precision)
                    for line in order.order_line.filtered(lambda l: not l.display_type)
                )
                and order.cncw_invoice_ids
            ):
                order.cncw_invoice_status = 'invoiced'
            else:
                order.cncw_invoice_status = 'no'

    advance_payment_apply_ids = fields.Many2many('advance.payment.apply', 'advance_payment_apply_purchase_rel',
                                                 'purchase_id', 'advance_id',
                                                 domain=[('state', '!=', 'cancel')], string='预付/付款申请明细')
    apply_amount_total = fields.Float("已申请金额", digits='Product Price', store=True,
                                      compute='_compute_advance_payment_apply_lines'
                                      )
    wait_apply_amount_total = fields.Float("剩余可申请金额", digits='Product Price', store=True,
                                           compute='_compute_advance_payment_apply_lines')
    advance_payment_apply_lines = fields.One2many(comodel_name='advance.payment.apply.line',
                                                  inverse_name='purchase_order_id', string='已锁定金额')
    cncw_invoice_count = fields.Integer(compute="_compute_cncw_invoice", string='发票数', copy=False, default=0, store=True)
    cncw_invoice_ids = fields.Many2many('cncw.invoice.move', compute="_compute_cncw_invoice", string='发票', copy=False, store=True)
    cncw_invoice_status = fields.Selection([
        ('no', '无'),
        ('to invoice', '等待开票'),
        ('invoiced', '已开票'),
    ], string='开票状态', compute='_get_cncw_invoiced', store=True, readonly=True, copy=False, default='no')

    @api.depends('state','wait_apply_amount_total')
    def update_wait_apply_amount_total(self):
        for record in self:
            if record.state == 'done' and record.wait_apply_amount_total ==0:
                record._compute_advance_payment_apply_lines()

    @api.depends('advance_payment_apply_lines', 'advance_payment_apply_lines.lock_amount')
    def _compute_advance_payment_apply_lines(self):
        for record in self:
            # 已申请金额
            apply_amount_total = sum(record.advance_payment_apply_lines.filtered(
                lambda l: record.id == l.purchase_order_id.id).mapped('lock_amount'))
            record.apply_amount_total = apply_amount_total
            # 可申请金额
            record.wait_apply_amount_total = record.amount_total - apply_amount_total

    def action_create_advance_payment_apply(self):
        """创建预付申请"""
        for record in self:
            if record.wait_apply_amount_total > 0:
                line_value = {'purchase_order_id': record.id}
                payment_value = {
                    'purchase_order_ids': [record.id],
                    'partner_id': record.partner_id.id,
                    'order_type': 'B',
                    'advance_payment_apply_ids': [(0, 0, line_value)]
                }
                payment_apply = self.env['advance.payment.apply'].create(payment_value)
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "advance.payment.apply",
                    'view_mode': 'form',
                    # 'view_id': master.id,
                    "res_id": payment_apply.id,
                    "name": "预付款/付款申请单",
                    # "target": 'new'
                }
            else:
                raise UserError('您可申请的金额不足！')

    def action_create_payment_apply(self):
        """创建付付款申请"""
        for record in self:
            if record.wait_apply_amount_total > 0:
                line_value = {'purchase_order_id': record.id}
                payment_value = {
                    'purchase_order_ids': [record.id],
                    'partner_id': record.partner_id.id,
                    'account_move_purchase_ids': [(6, 0, record.cncw_invoice_ids.ids)],
                    'order_type': 'A',
                    'advance_payment_apply_ids': [(0, 0, line_value)]
                }
                payment_apply = self.env['advance.payment.apply'].create(payment_value)
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "advance.payment.apply",
                    'view_mode': 'form',
                    # 'view_id': master.id,
                    "res_id": payment_apply.id,
                    "name": "预付款/付款申请单",
                    # "target": 'new'
                }
            else:
                raise UserError('您可申请的金额不足！')

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    cncw_invoice_lines = fields.One2many('cncw.invoice.move.line', 'purchase_line_id', string="发票行", readonly=True, copy=False)
    cncw_qty_to_invoice = fields.Float(compute='_compute_qty_cncw_invoiced', string='开票数', store=True, readonly=True,
                                  digits='Product Unit of Measure')
    cncw_qty_invoiced = fields.Float(compute='_compute_qty_cncw_invoiced', string="已开票数", digits='Product Unit of Measure',
                                store=True)
    
    @api.depends('cncw_invoice_lines.move_id.state', 'cncw_invoice_lines.quantity', 'qty_received', 'product_uom_qty', 'order_id.state')
    def _compute_qty_cncw_invoiced(self):
        for line in self:
            # compute qty_invoiced
            qty = 0.0
            for inv_line in line.cncw_invoice_lines:
                if inv_line.move_id.state not in ['cancel']:
                    if inv_line.move_id.move_type == 'in_invoice':
                        qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.move_id.move_type == 'in_refund':
                        qty -= inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.cncw_qty_invoiced = qty

            # compute qty_to_invoice
            if line.order_id.state in ['purchase', 'done']:
                if line.product_id.purchase_method == 'purchase':
                    line.cncw_qty_to_invoice = line.product_qty - line.cncw_qty_invoiced
                else:
                    line.cncw_qty_to_invoice = line.qty_received - line.cncw_qty_invoiced
            else:
                line.cncw_qty_to_invoice = 0