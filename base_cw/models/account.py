# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from ..public import generate_sequence

PAYMENT_TERM_TYPE = [
    ('A', '预付款类'),
    ('B', '后付款类'),
    ('C', u"预+后付款类"),
]

PAYMENT_DATE_TYPE = [
    ('A', '出货日'),
    ('B', '开票日'),
    ('C', u"提单日"),
]


class account_payment_term(models.Model):
    _name = 'account.payment.term'
    _inherit = ['account.payment.term', 'mail.thread']
    _description = '付款条件'

    code = fields.Char('编码', tracking=True)
    name = fields.Char('付款条件', translate=False, tracking=True)
    invoice_days = fields.Integer('开票周期', help='出货后的多少天内开票')
    is_monthly = fields.Boolean('月末开票', default=False,
                                help=u"[月末开票]是指出货后是在月底开发票票，如果[开票周期]和[月末开票]都有维护则票期计算不考虑[开票周期]而是取当月最后一天")
    note = fields.Char('备注', )
    sequence = fields.Integer('项次',)

    _sql_constraints = [('code_unique', 'unique (code)', '付款条件编码不能重复!'),
                        ('name_unique', 'unique (name)', '付款条件名称不能重复!'), ]


    def copy(self, default=None):
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(account_payment_term, self).copy(default)



class AccountPaymentTermLine(models.Model):
    _name = "account.payment.term.line"
    _inherit = ['account.payment.term.line']
    _description = '付款条件明细'

    option = fields.Selection([
        ('day_after_invoice_date', '开票之后的天数'),
        ('fix_day_following_month', '开票次月固定日期'),
        ('last_day_following_month', '开票次月最后一天'),
        ('last_day_current_month', '开票当月最后一天'),
    ],ondelete={'fix_day_following_month': 'cascade','last_day_following_month': 'cascade','last_day_current_month': 'cascade',} ,default='day_after_invoice_date', required=True, string='Options')

    sequence = fields.Integer('项次', )


class payment_mode(models.Model):
    _name = 'payment.mode'
    _inherit = ['mail.thread']
    _description = '付款方式'

    code = fields.Char('编码', required=True, tracking=True)
    name = fields.Char('名称', required=True, default=False, tracking=True)
    company_id = fields.Many2one('res.company', string='公司', change_default=True, required=True, readonly=True,
                                 default=lambda self: self.env.company)
    active = fields.Boolean('启用', required=False, default=True)
    note = fields.Text('备注')
    sequence = fields.Integer(u"排序", default=10, index=True)

    _sql_constraints = [('code_unique', 'unique (code, name)', '付款方式不能重复!'), ]


    def copy(self, default=None):
        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(payment_mode, self).copy(default)



class account_tax(models.Model):
    _name = 'account.tax'
    _inherit = ['account.tax','mail.thread']
    _order = 'code'
    _description = '税别'

    code = fields.Char('税别编码', tracking=True)
    name = fields.Char('税别名称', default=False, tracking=True)
    amount = fields.Float('税率', tracking=True)
    e_include = fields.Boolean('内含税', default=False, tracking=True)
    note = fields.Text('备注')
    type_tax_use = fields.Selection(selection_add=[('cost', '费用'), ('all', '采购/销售')],ondelete={'cost': 'cascade','all':'cascade'},
                                    required=True, tracking=True)
    active = fields.Boolean('启用', default=True, tracking=True)
    sequence = fields.Integer(u"排序", default=10, index=True)

    _sql_constraints = [
        ('name_type_tax_use_unique', 'unique (name,type_tax_use)', '名称类型不可重复!'),
    ]

    def copy(self, default=None):

        default = dict(default or {})
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(account_tax, self).copy(default)

    @api.model
    def _amount_turn_tax_amount(self, base_amount, price_include, currency=None):
        if len(self) == 0:
            company_id = self.env.user.company_id
        else:
            company_id = self[0].company_id
        if not currency:
            currency = company_id.currency_id
        amount = False
        if price_include:
            amount = base_amount / (1 + self.amount / 100)
        else:
            amount = base_amount * (1 + self.amount / 100)
        return currency.round(amount)
