# -*- encoding: utf-8 -*-
from .. import public
from odoo import models, fields, api, _


class res_bank(models.Model):
    _name = 'res.bank'
    _inherit = ['res.bank', 'mail.thread']
    _description = '银行资料'

    bic = fields.Char('编号', default=False, required=False, tracking=True)
    name = fields.Char('名称', default=False, tracking=True)
    note = fields.Text('备注')

    def create(self, values):
        if values.get('bic', ''):
            public.check_unique(self, ['bic'], values)
        if values.get('name', ''):
            public.check_unique(self, ['name'], values)
        res_id = super(res_bank, self).create(values)
        return res_id

    def copy(self, default=None):
        default = dict(default or {})
        default.update(bic=_("%s (copy)") % (self.bic or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(res_bank, self).copy(default)

    def write(self, vals):
        self.ensure_one()
        if 'bic' in vals:
            public.check_unique(self, ['bic'], vals)
        if 'name' in vals:
            public.check_unique(self, ['name'], vals)
        res = super(res_bank, self).write(vals)
        return res


# 银行类型
BANK_TYPE = [
    ('A', '收款银行'),
    ('B', '通知银行'),
    ('C', '其他银行'),
]

class res_partner_bank(models.Model):
    _name = 'res.partner.bank'
    _inherit = ['res.partner.bank', 'mail.thread']
    _description = '银行账户资料'

    acc_number = fields.Char('账户号码', default=False, tracking=True)
    bank_id = fields.Many2one('res.bank', '银行', ondelete="restrict", tracking=True)
    bank_type = fields.Selection(BANK_TYPE, '银行类型', default='C', tracking=True)
    name = fields.Char('开户行名称', required=False, default=False, tracking=True)
    account_id = fields.Many2one('cncw.account', '会计科目', ondelete="restrict")
    note = fields.Text('备注')
    active = fields.Boolean('启用', required=False, default=True)

    @api.onchange('bank_id')
    def onchange_bank_id(self):
        self.name = self.bank_id and self.bank_id.name or False

    def create(self, values):
        if 'acc_number' in values:
            public.check_unique(self, ['acc_number'], values, '账户号码')
        res_id = super(res_partner_bank, self).create(values)
        return res_id

    def copy(self, default=None):
        default = dict(default or {})
        default.update(acc_number=_("%s (copy)") % (self.acc_number or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(res_partner_bank, self).copy(default)

    def write(self, vals):
        self.ensure_one()
        if 'acc_number' in vals:
            public.check_unique(self, ['acc_number'], vals, '账户号码')
        res = super(res_partner_bank, self).write(vals)
        return res


class SetupBarBankConfigWizard(models.TransientModel):
    _inherit = 'account.setup.bank.manual.config'

    name = fields.Char('名称')
