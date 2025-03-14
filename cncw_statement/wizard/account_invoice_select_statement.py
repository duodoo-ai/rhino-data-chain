# -*- encoding: utf-8 -*-
import time
from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
#import odoo.addons.decimal_precision as dp
from odoo.addons import base_cw


class account_invoice_select_statement(models.TransientModel):
    _name = 'account.invoice.select.statement'

    master_id = fields.Many2one('cncw.invoice.move', '发票', ondelete="cascade")
    partner_id = fields.Many2one('res.partner', '往来单位', related='master_id.partner_id', readonly=True)
    name = fields.Char('对帐单号')
    statement_type = fields.Selection(base_cw.public.STATEMENT_TYPE, '对帐类型')  # [('S', '销售'), ('P', '采购')]
    is_all_check = fields.Boolean('全选', default=False)
    wizard_ids = fields.One2many('account.invoice.select.statement.line', 'wizard_id', '明细', )

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(account_invoice_select_statement, self).default_get(fields)
        master_id = self._context.get('active_id', False)
        active_model = self._context.get('active_model', False)
        if not master_id:
            return res
        assert active_model in ('cncw.invoice.move'), '不是正确的来源对象！'
        res.update(master_id=master_id)
        res.update(statement_type=self._context.get('statement_type', 'S'))
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    def action_query(self):
        self.ensure_one()
        sql = """
           select a.id as  statement_line_id,a.statement_source,a.product_id,'1' as statement_method,
                  a.product_uom,a.qty,a.price_unit,a.amount,
                  a.freight_amount,a.invoiced_qty,a.invoiced_amount
             from account_statement_line a left join account_statement b on a.master_id=b.id
            where a.invoice_state='A'
              and b.partner_id=%s
              and b.statement_type='%s'
              and a.state in ('confirmed')
              and b.currency_id=%s
              and b.tax_id=%s
              and COALESCE (a.remaining_invoiced_amount,0)<>0
        """ % (self.partner_id.id, self.statement_type, self.master_id.currency_id.id, self.master_id.tax_id.id)
        if self.name:
            sql += """ and b.name ilike '%%%s%%'""" % (self.name,)
        exists = self.master_id.invoice_line_ids.mapped('account_statement_line_id.id')
        if len(exists) == 1:
            sql += """  and a.id <> %s""" % exists[0]
        elif len(exists) > 1:
            sql += """  and a.id not in %s """ % (tuple(exists),)
        items = []
        self._cr.execute(sql)
        result = self._cr.dictfetchall()
        for line in result:
            for k, v in line.items():
                if not v:
                    line[k] = False
            items.append((0, 0, line))
        self.wizard_ids = False
        self.is_all_check = False
        if items:
            self.wizard_ids = items
        return self.wizard_view()

    def action_confirm(self):
        self.ensure_one()
        selects = self.wizard_ids.filtered( lambda m: m.is_check == True)
        if not selects:
            raise UserError(_('请选择!'))
        account2_id = self.master_id.get_account(self.master_id.type)
        tax_account_id = self.master_id.get_tax_account(self.master_id.type)
        items = []
        statement_line_ids = selects.mapped('statement_line_id')
        seq = 1
        for x in statement_line_ids:
            # account1_id = self.master_id.get_pay_account(self.master_id.type, x.product_id)
            account1_id = self.master_id.get_pay_account_product_type(self.master_id.type, x.product_id.product_type)
            qty = x.remaining_invoiced_qty != 0 and x.remaining_invoiced_qty or 1
            price_unit = float_round(abs(x.remaining_invoiced_amount) / abs(qty),
                                     precision_rounding=self.master_id.currency_id.rounding)
            item = dict(
                        # origin=x.master_id.name,
                        sequence=seq,
                        purchase_line_id=x.purchase_line_id and x.purchase_line_id.id or False,
                        name=x.product_id.name or '',
                        product_uom_id=x.product_id.uom_id and x.product_id.uom_id.id or x.product_uos.id,
                        product_id=x.product_id.id,
                        account1_id=account1_id,  # 收入/支出 科目
                        account_id=tax_account_id,  # 进项税额 销项税额
                        account2_id=account2_id,  # 立帐会科
                        price_unit=abs(price_unit),
                        tax_ids=[(4, x.master_id.tax_id.id)],
                        price_subtotal=x.remaining_invoiced_amount,
                        quantity=qty != 0 and qty or 1,
                        remaining_invoiced_qty=qty != 0 and qty or 1,
                        remaining_invoiced_amount=x.remaining_invoiced_amount,
                        move_id=self.master_id.id,
                        account_statement_line_id=x.id,
                        freight_amount=x.freight_amount,
                        )
            if self.env['cncw.account'].browse(account2_id).sub_account_type == 'has':
                item.update(dict(sub_account_id=self.partner_id and self.partner_id.id or False, ))
            if x.sale_line_id:
                item['sale_line_ids'] = [(4, x.sale_line_id.id)]
            items.append((0, 0, item))
            seq += 1
        if items:
            vals = dict(invoice_line_ids=items)
            if not self.master_id.categ_id:
                vals['categ_id'] = selects[0].product_id.categ_id and selects[0].product_id.categ_id.id or False
            self.master_id.write(vals)
            self.master_id._onchange_invoice_line_ids()
            # self.master_id.onchange_amount_tax()
            self.master_id.action_statement_invoiced_amount()

        # self.master_id.create_invoce_line(statement_line_ids=selects.mapped('statement_line_id'))
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_invoice_select_statement')
        return {
            'name': _(''),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice.select.statement',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class account_invoice_select_statement_line(models.TransientModel):
    _name = 'account.invoice.select.statement.line'

    is_check = fields.Boolean('选择', default=False)
    wizard_id = fields.Many2one('account.invoice.select.statement', '主档', ondelete="cascade")
    statement_line_id = fields.Many2one('account.statement.line', '对帐明细')
    statement_method = fields.Selection(base_cw.public.STATEMENT_METHOD, string='结算类型', )
    statement_source = fields.Selection(base_cw.public.STATEMENT_SOURCE, string='对帐对象', )
    product_id = fields.Many2one('product.product', string='产品')
    product_uom = fields.Many2one('uom.uom', string='库存单位')
    qty = fields.Float(string='对帐数量', digits='Product Unit of Measure')
    price_unit = fields.Float(string='单价', digits='Product Price')
    amount = fields.Float(string='对帐金额',  digits='Product Price',)
    freight_amount = fields.Float(string='运费金额',  digits='Product Price',)
    invoiced_qty = fields.Float(string='已开票数量', digits='Product Unit of Measure')
    invoiced_amount = fields.Float(string='已开票金额',  digits='Product Price',)
