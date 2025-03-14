# -*- encoding: utf-8 -*-
import time
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.exceptions import UserError

class invalid_invoice_select_wizard(models.TransientModel):
    _name = 'invalid.invoice.select.wizard'
    origin_invoice_id = fields.Many2one('cncw.invoice.move', '原发票号码')
    invoice_id = fields.Many2one('cncw.invoice.move', '原发票号码')
    is_all_check = fields.Boolean('全选', default=False)
    wizard_ids = fields.One2many('invalid.invoice.select.wizard.line', 'wizard_id', '明细', )

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(invalid_invoice_select_wizard, self).default_get(fields)
        invoice_id = self._context.get('invoice_id', False)
        if not invoice_id:
            return res
        res.update(origin_invoice_id=self._context.get('origin_invoice_id', False))
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    def action_query(self):
        self.ensure_one()
        exists = self.invoice_id.invoice_line_ids.mapped('origin_invoice_line_id')
        domain = [('state', '=', 'open')]
        if self.invoice_id.move_type == 'in_refund':
            domain += [('move_type', 'in', ('in_invoice',))]
        elif self.invoice_id.move_type == 'out_refund':
            domain += [('move_type', 'in', ('out_invoice',))]

        domain += [('move_id', '=', self.origin_invoice_id.id)]
        if exists:
            domain += [('id', 'not in', tuple(exists.ids,))]
        results = self.env['cncw.invoice.move.line'].search(domain)

        items = []
        for x in results:
            items.append((0, 0, dict(invoice_line_id=x.id,
                                     quantity=x.quantity,
                                     price_unit=x.price_unit,
                                     price_subtotal=x.price_subtotal,
                                     tax_amount=x.tax_amount,
                                     product_id=x.product_id.id,
                                     total_amount=x.total_amount,
                                     )))
        if items:
            self.write(dict(wizard_ids=items))
        else:
            self.wizard_ids = False
        return self.wizard_view()

    def action_confirm(self):
        self.ensure_one()
        selects = self.wizard_ids.filtered(lambda x: x.is_check ==True)
        if not selects:
            raise UserError(_(u"请选发票明细！"))
        items = []
        account2_id = self.invoice_id.get_account(self.invoice_id.move_type)
        tax_account_id = self.invoice_id.get_tax_account(self.invoice_id.move_type)
        for line in selects:
            account1_id = self.invoice_id.get_pay_account(self.invoice_id.move_type, line.product_id)
            item = dict(origin_invoice_line_id=line.invoice_line_id.id,
                        statement_line_id=line.invoice_line_id.account_statement_line_id and line.invoice_line_id.account_statement_line_id.id or False,
                        stock_move_id=line.invoice_line_id.stock_move_id and line.invoice_line_id.stock_move_id.id or False,
                        name=line.product_id.name or '',
                        product_uom_id=line.product_id.uom_id and line.product_id.uom_id.id,
                        product_id=line.product_id.id,
                        account1_id=account1_id,  # 收入/支出 科目
                        account_id=tax_account_id,  # 进项税额 销项税额
                        account2_id=account2_id,  # 立帐会科
                        sub_account_id=line.invoice_line_id.sub_account_id and line.invoice_line_id.sub_account_id.id or False,
                        tax_ids=[(4, self.invoice_id.tax_id.id)],
                        quantity=-line.quantity,
                        price_unit=line.price_unit,
                        price_subtotal=-line.price_subtotal,
                        tax_amount=-line.tax_amount,
                        total_amount=-line.total_amount,
                        purchase_line_id=line.invoice_line_id.purchase_line_id and line.invoice_line_id.purchase_line_id.id or False,
                        )
            if line.invoice_line_id.sale_line_ids:
                for order_line in line.invoice_line_id.sale_line_ids:
                    item['sale_line_ids'] = [(4, order_line.id)]
            items.append((0, 0, item))
        if items:
            self.invoice_id.write(dict(invoice_line_ids=items))
        self.invoice_id._onchange_invoice_line_ids()
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_invalid_invoice_select_wizard')
        return {
            'name': _('作废发票选择向导'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'invalid.invoice.select.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class invalid_invoice_select_wizard_line(models.TransientModel):
    _name = 'invalid.invoice.select.wizard.line'

    is_check = fields.Boolean('选择', default=False)
    wizard_id = fields.Many2one('invalid.invoice.select.wizard', '主档', ondelete="cascade")
    invoice_line_id = fields.Many2one('cncw.invoice.move.line', '发票明细')
    product_id = fields.Many2one('product.product', '产品', related='invoice_line_id.product_id', readonly=True)
    quantity = fields.Float('开票数量', digits='Product Unit of Measure',
                            related='invoice_line_id.quantity', readonly=True)
    price_unit = fields.Float('开票单价', digits='Product Price',
                              readonly=True)
    price_subtotal = fields.Float('开票金额',  digits='Product Price',
                                  readonly=True)

    tax_amount = fields.Float('税额',  digits='Product Price',
                              readonly=True)
    total_amount = fields.Float('含税金额',  digits='Product Price',
                                readonly=True)
