# -*- encoding: utf-8 -*-
from odoo import models, fields, api
from odoo.addons import base_cw


class account_advance(models.Model):
    _name = 'account.advance'
    _description = '预收款单'

    name = fields.Char('预收单号', default='New')
    date = fields.Date('预收日期', default=lambda self: fields.Date.context_today(self))
    partner_id = fields.Many2one('res.partner', '客户编号')
    currency_id = fields.Many2one('res.currency', '币别')
    exchange_rate = fields.Float(related='partner_id.partner_currency_id.rate', string='汇率', store=True,
                                 digits='Exchange Rate',
                                 default=1.0)
    tax_rate = fields.Float('税率', digits='Product Price', )
    amount = fields.Float('收款金额', digits='Product Price', )
    tax_amount = fields.Float('收款税额', digits='Product Price', )
    total_amount = fields.Float('收款总额', digits='Product Price', )
    lc_amount = fields.Float('本币收款金额', digits='Product Price', )
    lc_tax_amount = fields.Float('本币收款税额', digits='Product Price', )
    lc_total_amount = fields.Float('本币收款总额', digits='Product Price', )
    account_id = fields.Many2one('cncw.account', '预收科目')
    org_account_id = fields.Many2one('cncw.account', '收款科目')
    sub_account_id = fields.Many2one('res.partner', '科目辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_pay_line_id', string='辅助核算')

    sub_account_lines_str = fields.Char(string='会计辅助核算', compute='compute_sub_account_lines_str')

    @api.depends('sub_account_lines', 'sub_account_lines.sub_account_id')
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
    res_id = fields.Many2one('account.receive.line', '收款明细', ondelete="set null")
    received_line_ids = fields.One2many('account.receive.line', 'advance_id', '收款(冲销)明细')
    received_amount = fields.Float('累计冲销金额', digits='Product Price', )
    lc_received_amount = fields.Float('本币累计冲销金额', digits='Product Price', )
    remaining_amount = fields.Float('未冲销金额', digits='Product Price', )
    lc_remaining_amount = fields.Float('本币未冲销金额', digits='Product Price', )

    state = fields.Selection(base_cw.public.VOUCHER_STATE, '状态', default='confirmed')
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True,
                                 default=lambda self: self.env.company)

    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals)
        return super(account_advance, self).create(vals)

    @api.depends('amount')
    def compute_remaining_amount(self):
        query = self.received_line_ids.filtered(lambda x: x.master_id.state == 'done')
        if query:
            self.lc_received_amount = sum(query.mapped('local_amount'))*self.exchange_rate
            self.received_amount = sum(query.mapped('amount'))
            self.remaining_amount = self.amount - self.received_amount
            self.lc_remaining_amount = (self.lc_amount - self.lc_received_amount)*self.exchange_rate
        else:
            self.received_amount = 0.0
            self.lc_received_amount = 0.0
            self.remaining_amount = self.amount
            self.lc_remaining_amount = self.lc_amount*self.exchange_rate
            self.total_amount = self.amount
            self.lc_total_amount = self.lc_amount*self.exchange_rate

        if 0.0 < self.received_amount < self.amount:
            self.offset_state = 'P'
            self.state = 'confirmed'
        elif self.received_amount == self.amount:
            self.offset_state = 'A'
            self.state = 'done'
        else:
            self.offset_state = 'N'
            self.state = 'confirmed'
        objs = self.search([('partner_id', '=', self.partner_id.id), ('remaining_amount', '>', 0.0)])
        if objs:
            self.partner_id.write(dict(advance_amount=sum(objs.mapped('remaining_amount'))))
