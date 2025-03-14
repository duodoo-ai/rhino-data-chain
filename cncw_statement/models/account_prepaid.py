# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class account_prepaid(models.Model):
    _name = 'account.prepaid'
    _description = '预付款单'
    _order = 'name desc'

    name = fields.Char('预付单号', default='New')
    date = fields.Date('预付日期', default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', '供应商')
    currency_id = fields.Many2one('res.currency', '币别')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate')
    tax_rate = fields.Float('税率',  digits='Product Price',)
    amount = fields.Float('原币金额',  digits='Product Price',)
    tax_amount = fields.Float('原币税额',  digits='Product Price',)
    total_amount = fields.Float('原币总额',  digits='Product Price',)
    lc_amount = fields.Float('本币金额',  digits='Product Price',)
    lc_tax_amount = fields.Float('本币税额',  digits='Product Price',)
    lc_total_amount = fields.Float('本币总额',  digits='Product Price',)
    account_id = fields.Many2one('cncw.account', '预付科目')
    org_account_id = fields.Many2one('cncw.account', '付款科目')
    sub_account_id = fields.Many2one('res.partner', '科目辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_prepaid_id')
    sub_account_lines_str = fields.Char(string='会计辅助核算', compute='compute_sub_account_lines_str')

    def compute_sub_account_lines_str(self):
        for record in self:
            sub_account_lines_str = ''
            for line in record.sub_account_lines.filtered(lambda r: r.sub_account_id):
                sub_account_lines_str += ' | '+line.sub_account_id.name
                if line.category_id.code == 'cash_flow':
                    record.sub_account_id = line.sub_account_id
            record.sub_account_lines_str = sub_account_lines_str
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    note = fields.Text('备注')
    offset_state = fields.Selection([('N', '未冲销'),
                                     ('P', '部分冲销'),
                                     ('A', '已完全冲销')],
                                    '冲销状态', default='N')
    res_id = fields.Many2one('account.pay.line', '付款明细', ondelete="set null")
    pay_line_ids = fields.One2many('account.pay.line', 'prepaid_id', '付款(冲销)明细')
    paid_amount = fields.Float('原币累计冲销',  digits='Product Price',)
    lc_paid_amount = fields.Float('本币累计冲销',  digits='Product Price',)
    remaining_amount = fields.Float('原币未冲销余额',  digits='Product Price',)
    lc_remaining_amount = fields.Float('本币未冲销余额',  digits='Product Price',)

    state = fields.Selection(base_cw.public.VOUCHER_STATE, '状态', default='confirmed')
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True,
                                 default=lambda self: self.env.company)

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.prepaid",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_account_prepaid_form2').id,
            "res_id": self.id,
            "name": "编辑辅助核算",
            "target": 'new'
        }

    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals)
        return super(account_prepaid, self).create(vals)

    @api.depends('amount')
    def compute_remaining_amount(self):
        query = self.pay_line_ids.filtered(lambda x: x.master_id.state == 'done')
        if query:
            self.lc_paid_amount = sum(query.mapped('local_amount'))
            self.paid_amount = sum(query.mapped('amount'))
            self.remaining_amount = self.amount - self.paid_amount
            self.lc_remaining_amount = self.lc_amount - self.lc_paid_amount
        else:
            self.paid_amount = 0.0
            self.lc_paid_amount = 0.0
            self.remaining_amount = self.amount
            self.lc_remaining_amount = self.lc_amount
            self.total_amount = self.amount
            self.lc_total_amount = self.lc_amount

        if 0.0 < self.paid_amount < self.amount:
            self.offset_state = 'P'
            self.state = 'confirmed'
        elif self.paid_amount == self.amount:
            self.offset_state = 'A'
            self.state = 'done'
        else:
            self.offset_state = 'N'
            self.state = 'confirmed'
