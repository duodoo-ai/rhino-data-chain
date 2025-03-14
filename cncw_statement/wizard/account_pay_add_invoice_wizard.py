# -*- encoding: utf-8 -*-
import time
from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.tools import float_round



class account_pay_add_invoice_wizard(models.TransientModel):
    _name = 'account.pay.add.invoice.wizard'

    name = fields.Char(string=u"单据编号")
    active_id = fields.Integer(u"ActiveId")
    active_model = fields.Char(string=u"主档对象名", )
    is_all_check = fields.Boolean('全选', default=False)
    is_receive_pay_offset = fields.Boolean('应收应付对冲', default=False)
    partner_id = fields.Many2one('res.partner', '往来单位')#, domain=[('supplier', '=', True)]
    wizard_ids = fields.One2many('account.pay.add.invoice.wizard.line', 'wizard_id', '明细', )

    @api.model
    def default_get(self, fields):
        if self._context is None: self._context = {}
        res = super(account_pay_add_invoice_wizard, self).default_get(fields)
        active_id = self._context.get('active_id', False)
        active_model = self._context.get('active_model')
        if not active_id:
            return res
        if not active_model:
            return res
        obj = self.env[active_model].browse(active_id)
        if obj:
            res.update(partner_id=obj.partner_id.id)
        res.update(name=self._context.get('name', False))
        res.update(is_receive_pay_offset=self._context.get('is_receive_pay_offset', False))
        res.update(active_id=active_id)
        res.update(active_model=active_model)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    def action_query(self):
        self.ensure_one()
        master_id = self.env[self.active_model].browse(self.active_id)
        exists = master_id.offset_line_ids.mapped('invoice_id')
        domain = [('offset_state', '!=', 'A'), ('state', '=', 'open'), ('remaining_amount', '!=', 0.0)]
        if self.active_model == 'account.pay' and not self.is_receive_pay_offset:  # 收款
            domain += [('move_type', 'in', ('in_invoice', 'in_refund'))]
        elif self.active_model == 'account.receive' and not self.is_receive_pay_offset:  # 付款
            domain += [('move_type', 'in', ('out_invoice', 'out_refund'))]
        elif self.active_model == 'account.receive' and self.is_receive_pay_offset:  # 应付冲应收
            domain += [('move_type', 'in', ('in_invoice', 'in_refund'))]
        elif self.active_model == 'account.pay' and self.is_receive_pay_offset:  # 应收冲应付
            domain += [('move_type', 'in', ('out_invoice', 'out_refund'))]
        if self.partner_id:
            domain += [('partner_id', '=', self.partner_id.id)]
        else:
            domain += [('partner_id', '=', master_id.partner_id.id)]
        if exists:
            domain += [('id', 'not in', exists.ids)]
        results = self.env['cncw.invoice.move'].search(domain)

        items = []
        for x in results:
            items.append((0, 0, dict(invoice_id=x.id)))
        self.wizard_ids.unlink()
        if items:
            self.write(dict(wizard_ids=items))
        return self.wizard_view()

    def action_confirm(self):
        self.ensure_one()
        selects = self.wizard_ids.filtered(lambda x: x.is_check ==True)
        if not selects:
            raise UserError(_(u"提示!请选发票！"))
        for line in selects:
            item = dict(master_id=self.active_id,
                        invoice_id=line.invoice_id.id,
                        invoice_no=line.invoice_id.invoice_no,
                        date_invoice=line.date_invoice,
                        date_due=line.date_due,
                        amount=line.remaining_amount,
                        account_id=line.invoice_id.account1_id and line.invoice_id.account1_id.id or False,
                        )
            if line.invoice_id.account1_id.sub_account_type == 'has':
                line_data = {'category_id': line.invoice_id.partner_id.subaccount_category_id.id,
                             'sub_account_id': line.invoice_id.partner_id.id}
                sub_account_lines_data=[(0, 0, line_data)]
                item.update(
                    dict(sub_account_id=line.invoice_id.partner_id and line.invoice_id.partner_id.id or False,
                         sub_account_lines=sub_account_lines_data))
            self.env[self.active_model + '.offset.line'].create(item)
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_pay_add_invoice_wizard')
        return {
            'name': _('发票选择向导'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.pay.add.invoice.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class account_pay_add_invoice_wizard_line(models.TransientModel):
    _name = 'account.pay.add.invoice.wizard.line'

    @api.depends('date_due')
    def _compute_overdue_days(self):
        for record in self:
            record.overdue_days = 0
            if record.date_due:
                record.overdue_days = base_cw.public.get_days_between_date(time.strftime("%Y-%m-%d"), fields.Datetime.to_string(record.date_due))

    is_check = fields.Boolean('选择', default=False)
    wizard_id = fields.Many2one('account.pay.add.invoice.wizard', '主档', ondelete="cascade")
    invoice_id = fields.Many2one('cncw.invoice.move', '发票编号')
    date_invoice = fields.Date('发票日期', related='invoice_id.date_invoice', readonly=True)
    date_due = fields.Date(string='应付款日期', related='invoice_id.invoice_date_due', readonly=True)
    overdue_days = fields.Integer(string='逾期天数', compute='_compute_overdue_days', readonly=True)
    invoice_amount = fields.Float('发票金额',  digits='Product Price',
                                  related='invoice_id.total_invoice_amount', readonly=True)
    payment_amount = fields.Float('已付金额',  digits='Product Price', readonly=True,
                                  related='invoice_id.payment_amount')
    remaining_amount = fields.Float('剩余金额',  digits='Product Price', readonly=True,
                                    related='invoice_id.remaining_amount')
