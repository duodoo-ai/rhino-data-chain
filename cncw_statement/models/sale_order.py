# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round, float_is_zero


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('order_line.cncw_invoice_lines')
    def _get_cncw_invoiced(self):
        # The invoice_ids are obtained thanks to the invoice lines of the SO
        # lines, and we also search for possible refunds created directly from
        # existing invoices. This is necessary since such a refund is not
        # directly linked to the SO.
        for order in self:
            invoices = order.order_line.cncw_invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
            order.cncw_invoice_ids = invoices
            order.cncw_invoice_count = len(invoices)

    @api.depends('state', 'order_line.cncw_invoice_status')
    def _get_cncw_invoice_status(self):
        """
        Compute the invoice status of a SO. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also the default value if the conditions of no other status is met.
        - to invoice: if any SO line is 'to invoice', the whole SO is 'to invoice'
        - invoiced: if all SO lines are invoiced, the SO is invoiced.
        - upselling: if all SO lines are invoiced or upselling, the status is upselling.
        """
        unconfirmed_orders = self.filtered(lambda so: so.state not in ['sale', 'done'])
        unconfirmed_orders.cncw_invoice_status = 'no'
        confirmed_orders = self - unconfirmed_orders
        if not confirmed_orders:
            return
        line_invoice_status_all = [
            (d['order_id'][0], d['cncw_invoice_status'])
            for d in self.env['sale.order.line'].read_group([
                    ('order_id', 'in', confirmed_orders.ids),
                    ('is_downpayment', '=', False),
                    ('display_type', '=', False),
                ],
                ['order_id', 'cncw_invoice_status'],
                ['order_id', 'cncw_invoice_status'], lazy=False)]
        for order in confirmed_orders:
            line_invoice_status = [d[1] for d in line_invoice_status_all if d[0] == order.id]
            if order.state not in ('sale', 'done'):
                order.cncw_invoice_status = 'no'
            elif any(invoice_status == 'to invoice' for invoice_status in line_invoice_status):
                order.cncw_invoice_status = 'to invoice'
            elif line_invoice_status and all(invoice_status == 'invoiced' for invoice_status in line_invoice_status):
                order.cncw_invoice_status = 'invoiced'
            elif line_invoice_status and all(invoice_status in ('invoiced', 'upselling') for invoice_status in line_invoice_status):
                order.cncw_invoice_status = 'upselling'
            else:
                order.cncw_invoice_status = 'no'
                
    def _search_cncw_invoice_ids(self, operator, value):
        if operator == 'in' and value:
            self.env.cr.execute("""
                SELECT array_agg(so.id)
                    FROM sale_order so
                    JOIN sale_order_line sol ON sol.order_id = so.id
                    JOIN sale_order_line_cncw_invoice_rel soli_rel ON soli_rel.order_line_id = sol.id
                    JOIN cncw_invoice_line aml ON aml.id = soli_rel.invoice_line_id
                    JOIN cncw_invoice am ON am.id = aml.move_id
                WHERE
                    am.move_type in ('out_invoice', 'out_refund') AND
                    am.id = ANY(%s)
            """, (list(value),))
            so_ids = self.env.cr.fetchone()[0] or []
            return [('id', 'in', so_ids)]
        return ['&', ('order_line.cncw_invoice_lines.move_id.move_type', 'in', ('out_invoice', 'out_refund')), ('order_line.cncw_invoice_lines.move_id', operator, value)]
    
    cncw_invoice_count = fields.Integer(string='发票数', compute='_get_cncw_invoiced', readonly=True)
    cncw_invoice_ids = fields.Many2many("cncw.invoice.move", string='发票', compute="_get_cncw_invoiced", readonly=True, copy=False, search="_search_cncw_invoice_ids")
    cncw_invoice_status = fields.Selection([
        ('upselling', '到期'),
        ('invoiced', '已开票'),
        ('to invoice', '待开票'),
        ('no', '无发票')
        ], string='开票状态', compute='_get_cncw_invoice_status', store=True, readonly=True)
    advance_receive_apply_ids = fields.Many2many('advance.receive.apply', 'advance_receive_apply_sale_rel', 'sale_id',
                                                 'advance_id', string='预收申请/收款申请',
                                                 domain=[('state', '!=', 'cancel')])
    apply_amount_total = fields.Float("已申请金额", digits='Product Price', store=True,
                                      compute='_compute_advance_receive_apply_lines')
    wait_apply_amount_total = fields.Float("可申请金额", digits='Product Price', store=True,
                                           compute='_compute_advance_receive_apply_lines')
    advance_receive_apply_lines = fields.One2many(comodel_name='advance.receive.apply.line',
                                                  inverse_name='sale_order_id', string='已锁定金额')

    # @api.depends('state','advance_receive_apply_lines.lock_amount')
    def update_wait_apply_amount_total(self):
        for record in self:
            # if record.state == 'done' and record.wait_apply_amount_total ==0:
            self._compute_advance_receive_apply_lines()

    @api.depends('state', 'amount_total','advance_receive_apply_lines.lock_amount')
    def _compute_advance_receive_apply_lines(self):
        for record in self:
            # 已申请金额
            apply_amount_total = sum(record.advance_receive_apply_lines.filtered(
                lambda l: record.id == l.sale_order_id.id).mapped('lock_amount'))
            record.apply_amount_total = apply_amount_total
            # 可申请金额
            record.wait_apply_amount_total = record.amount_total - apply_amount_total

    def action_create_advance_receive_apply(self):
        """创建预收申请"""
        for record in self:
            if record.wait_apply_amount_total > 0:

                line_value = {'sale_order_id': record.id}
                receive_value = {'sale_order_ids': [record.id],
                                 'partner_id': record.partner_id.id,
                                 'team_id': record.team_id.id,
                                 'order_type': 'B', 'line_ids': [(0, 0, line_value)]}
                receive_apply = self.env['advance.receive.apply'].create(receive_value)
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "advance.receive.apply",
                    'view_mode': 'form',
                    # 'view_id': master.id,
                    "res_id": receive_apply.id,
                    "name": "预收款/收款申请单",
                    # "target": 'new'
                }
            else:
                raise UserError('您可申请的金额不足！')

    def action_create_receive_apply(self):
        """创建收款申请"""
        for record in self:
            if record.wait_apply_amount_total > 0:
                line_value = {'sale_order_id': record.id}
                receive_value = {'sale_order_ids': [record.id],
                                 'partner_id': record.partner_id.id,
                                 'account_move_sale_ids': [(6, 0, record.invoice_ids.ids)],
                                 'order_type': 'A',
                                 'team_id': record.team_id.id,
                                 'line_ids': [(0, 0, line_value)]}
                receive_apply = self.env['advance.receive.apply'].create(receive_value)
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "advance.receive.apply",
                    'view_mode': 'form',
                    # 'view_id': master.id,
                    "res_id": receive_apply.id,
                    "name": "预收款/收款申请单",
                    # "target": 'new'
                }
            else:
                raise UserError('您可申请的金额不足！')

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('state', 'product_uom_qty', 'qty_delivered', 'cncw_qty_to_invoice', 'cncw_qty_invoiced')
    def _compute_cncw_invoice_status(self):
        """
        Compute the invoice status of a SO line. Possible statuses:
        - no: if the SO is not in status 'sale' or 'done', we consider that there is nothing to
          invoice. This is also hte default value if the conditions of no other status is met.
        - to invoice: we refer to the quantity to invoice of the line. Refer to method
          `_get_to_invoice_qty()` for more information on how this quantity is calculated.
        - upselling: this is possible only for a product invoiced on ordered quantities for which
          we delivered more than expected. The could arise if, for example, a project took more
          time than expected but we decided not to invoice the extra cost to the client. This
          occurs onyl in state 'sale', so that when a SO is set to done, the upselling opportunity
          is removed from the list.
        - invoiced: the quantity invoiced is larger or equal to the quantity ordered.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if line.state not in ('sale', 'done'):
                line.cncw_invoice_status = 'no'
            elif line.is_downpayment and line.untaxed_amount_to_invoice == 0:
                line.cncw_invoice_status = 'invoiced'
            elif not float_is_zero(line.cncw_qty_to_invoice, precision_digits=precision):
                line.cncw_invoice_status = 'to invoice'
            elif line.state == 'sale' and line.product_id.invoice_policy == 'order' and \
                    float_compare(line.qty_delivered, line.product_uom_qty, precision_digits=precision) == 1:
                line.cncw_invoice_status = 'upselling'
            elif float_compare(line.qty_invoiced, line.product_uom_qty, precision_digits=precision) >= 0:
                line.cncw_invoice_status = 'invoiced'
            else:
                line.cncw_invoice_status = 'no'

    @api.depends('cncw_qty_invoiced', 'qty_delivered', 'product_uom_qty', 'order_id.state')
    def _get_to_cncw_invoice_qty(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.order_id.state in ['sale', 'done']:
                if line.product_id.invoice_policy == 'order':
                    line.cncw_qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                else:
                    line.cncw_qty_to_invoice = line.qty_delivered - line.qty_invoiced
            else:
                line.cncw_qty_to_invoice = 0

    @api.depends('cncw_invoice_lines.move_id.state', 'cncw_invoice_lines.quantity', 'untaxed_amount_to_invoice')
    def _get_cncw_invoice_qty(self):
        """
        Compute the quantity invoiced. If case of a refund, the quantity invoiced is decreased. Note
        that this is the case only if the refund is generated from the SO and that is intentional: if
        a refund made would automatically decrease the invoiced quantity, then there is a risk of reinvoicing
        it automatically, which may not be wanted at all. That's why the refund has to be created from the SO
        """
        for line in self:
            qty_invoiced = 0.0
            for invoice_line in line.cncw_invoice_lines:
                if invoice_line.move_id.state != 'cancel':
                    if invoice_line.move_id.move_type == 'out_invoice':
                        qty_invoiced += invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
                    elif invoice_line.move_id.move_type == 'out_refund':
                        if not line.is_downpayment or line.untaxed_amount_to_invoice == 0 :
                            qty_invoiced -= invoice_line.product_uom_id._compute_quantity(invoice_line.quantity, line.product_uom)
            line.cncw_qty_invoiced = qty_invoiced

    cncw_invoice_lines = fields.Many2many('cncw.invoice.move.line', 'sale_order_line_cncw_invoice_rel', 'order_line_id', 'invoice_line_id', string='发票行', copy=False)
    cncw_invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', '已开票'),
        ('to invoice', '待开票'),
        ('no', '无发票')
        ], string='开票状态', compute='_compute_cncw_invoice_status', store=True, readonly=True, default='no')
    cncw_qty_to_invoice = fields.Float(compute='_get_to_cncw_invoice_qty', string='开票数', store=True, readonly=True,
                                       digits='Product Unit of Measure')
    cncw_qty_invoiced = fields.Float(
        compute='_get_cncw_invoice_qty', string='已开票数', store=True, readonly=True,
        compute_sudo=True,
        digits='Product Unit of Measure')

    @api.depends('cncw_invoice_lines.move_id.state', 'cncw_invoice_lines.quantity', 'qty_received', 'product_uom_qty',
                 'order_id.state')
    def _compute_cncw_qty_invoiced(self):
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