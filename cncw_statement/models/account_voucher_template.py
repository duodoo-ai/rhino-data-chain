# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_compare


class AccountVoucherTemplate(models.Model):
    _name = 'account.voucher.template'
    _description = '凭证模版'

    code = fields.Char('模版代码', required=True)
    name = fields.Char('模版名称', required=True)

    note = fields.Text('备注')
    is_default = fields.Boolean('默认模版', default=False)
    is_profit = fields.Boolean('结转损益模版', default=False)
    is_system_created = fields.Boolean('为系统初识化资料', default=False,
                                       help='标示此笔资料为系统初识化所创建,不可以删除')
    line_ids = fields.One2many('account.voucher.template.line', 'master_id', '凭证模版', copy=True)

    payable_account_id = fields.Many2one('cncw.account',
                                         domain="[('ap_ar_type','in',('10','11','12','13')),('active', '=', True)]",
                                         string=u"应付科目", )
    receivable_account_id = fields.Many2one('cncw.account',
                                            domain="[('ap_ar_type','in',('20','21','23')),('active', '=', True)]",
                                            string=u"应收科目")
    payable_bill_account_id = fields.Many2one('cncw.account',
                                              domain="[('ap_ar_type','in',('10','11','12','13')),('active', '=', True)]",
                                              string=u"应付票据科目", )
    receivable_bill_account_id = fields.Many2one('cncw.account',
                                                 domain="[('ap_ar_type','in',('20','21','23')),('active', '=', True)]",
                                                 string=u"应收票据科目")
    sale_tax_account_id = fields.Many2one('cncw.account', string=u"销项税科目", help=u"已不在这里取值，改为到税别定义的地方取值")
    purchase_tax_account_id = fields.Many2one('cncw.account', string=u"进项税科目", help=u"已不在这里取值，改为到税别定义的地方取值")
    current_year_profit_account_id = fields.Many2one('cncw.account', string=u"本年利润")

    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D', required=True)
    prepaid_account_id = fields.Many2one('cncw.account',
                                         domain="[('ap_ar_type','in',('10','11','20','21','23')), ('active', '=', True)]",
                                         string=u"预付科目", )
    advance_account_id = fields.Many2one('cncw.account',
                                         domain="[('ap_ar_type','in',('10','20','21','11','12','13',)),('active', '=', True)]",
                                         string=u"预收科目")
    _sql_constraints = [('code_unique', 'unique (code)', '凭证模版代码不能重复!'),
                        ('name_unique', 'unique (name)', '凭证模版名称不能重复!'), ]
    total_amount = fields.Float('金额',  digits='Product Price',)

    est_payable_account_id = fields.Many2one('cncw.account',
                                         domain="[('active', '=', True)]",
                                         string=u"应付暂估科目", )
    material_account_id = fields.Many2one('cncw.account',
                                         domain="[('active', '=', True)]",
                                         string=u"原材料", )
    outsourcing_account_id = fields.Many2one('cncw.account',
                                         domain="[('active', '=', True)]",
                                         string=u"加工费", )

    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals[0])
        return super(AccountVoucherTemplate, self).create(vals)

    def unlink(self):
        for x in self:
            if x.is_system_created:
                raise UserError('删除错误!系统预设资料不可删除！')
        return super(AccountVoucherTemplate, self).unlink()


class AccountVoucherTemplateLine(models.Model):
    _name = 'account.voucher.template.line'
    _description = '凭证模版明细'

    #Jon   update account_voucher_template_line a set amount=0
    amount = fields.Float('金额')

    master_id = fields.Many2one('account.voucher.template', '凭证模版', ondelete="cascade")
    sequence = fields.Integer('项次', default=1)
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D', required=True)
    account_id = fields.Many2one('cncw.account', '会计科目', required=False, ondelete="restrict")
    note = fields.Text('备注')
    amount = fields.Float('Amount',  digits='Product Price',)

    def create(self, vals):
        base_cw.public.generate_sequence(self, vals[0])
        return super(AccountVoucherTemplateLine, self).create(vals)
