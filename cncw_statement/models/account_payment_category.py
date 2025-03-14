# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.tools import float_compare, float_round
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class account_payment_category(models.Model):
    _name = 'account.payment.category'
    _rec_name = 'name'
    _description = '付款类别'

    name = fields.Char('付款类别', required=True)
    account_id = fields.Many2one('cncw.account', '会科')
    account_setup = fields.Selection([('A', '预设'), ('B', '人工输入'), ], '会科设定类别', required=True, default='A')
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    active = fields.Boolean('启用', default=True)
    state = fields.Selection([('draft', '草稿'), ('confirmed', '已审核')], string='状态',
                             default='draft')
    note = fields.Text('备注')
    is_payment = fields.Boolean('为付款项', default=True)
    sub_account_type = fields.Selection(related='account_id.sub_account_type', readonly=True, string='会科属性')
    sub_account_ids = fields.Many2many('res.partner', string='辅助核算')
    can_sub_account_ids = fields.Many2many('res.partner', compute='_get_sub_account_ids', string='可选辅助核算')

    @api.depends('account_id')
    def _get_sub_account_ids(self):
        for record in self:
            account_obj = self.env['cncw.account']
            record.can_sub_account_ids = account_obj.get_sub_account_ids(record.account_id)

    # 确认审核
    def action_confirmed(self):
        self.ensure_one()
        self.state = "confirmed"

    # 取消确认
    def action_cancel(self):
        self.ensure_one()
        self.state = "draft"

    def create(self, values):
        # if 'name' not in values:
        #     base_cw.public.check_unique(self, ['name'], values, '付款类别')
        res_id = super(account_payment_category, self).create(values)
        return res_id

    def copy(self, default=None):
        self.ensure_one()
        default = default or {}
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(account_payment_category, self).copy(default)

    def write(self, vals, ):
        self.ensure_one()
        # if 'name' in vals:
        #     base_cw.public.check_unique(self, ['name'], vals, '付款类别')
        res = super(account_payment_category, self).write(vals)
        return res

    def unlink(self):
        for r in self:
            if r.state == 'confirmed':
                raise  UserError(_('操作错误!已经审核的资料不可以删除！'))
        res = super(account_payment_category, self).unlink()
        return res


class account_receive_category(models.Model):
    _name = 'account.receive.category'
    _rec_name = 'name'
    _description = '收款类别'

    name = fields.Char('收款类别', required=True)
    account_id = fields.Many2one('cncw.account', '会科')
    account_setup = fields.Selection([('A', '预设'), ('B', '人工输入'), ], '会科设定类别', required=True, default='A')
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    active = fields.Boolean('启用', default=True)
    state = fields.Selection([('draft', '草稿'), ('confirmed', '已审核')], string='状态',
                             default='draft')
    note = fields.Text('备注')
    is_receive = fields.Boolean('为收款项', default=True)
    sub_account_ids = fields.Many2many('res.partner', string='辅助核算')
    can_sub_account_ids = fields.Many2many('res.partner', compute='_get_sub_account_ids', string='可选辅助核算')
    sub_account_type = fields.Selection(related='account_id.sub_account_type', readonly=True, string='会科属性')

    @api.depends('account_id')
    def _get_sub_account_ids(self):
        for record in self:
            account_obj = self.env['cncw.account']
            record.can_sub_account_ids = account_obj.get_sub_account_ids(record.account_id)
    # 确认审核
    def action_confirmed(self):
        self.ensure_one()
        self.state = "confirmed"

    # 取消确认
    def action_cancel(self):
        self.ensure_one()
        self.state = "draft"

    def create(self, values):
        # if 'name' not in values:
        #     base_cw.public.check_unique(self, ['name'], values, '收款类别')
        res_id = super(account_receive_category, self).create(values)
        return res_id

    def copy(self, default=None):
        self.ensure_one()
        default = default or {}
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(account_receive_category, self).copy(default)

    def write(self, vals, ):
        self.ensure_one()
        # if 'name' in vals:
        #     base_cw.public.check_unique(self, ['name'], vals, '收款类别')
        res = super(account_receive_category, self).write(vals)
        return res

    def unlink(self):
        for r in self:
            if r.state == 'confirmed':
                raise UserError(_('操作错误!已经审核的资料不可以删除！'))
        res = super(account_receive_category, self).unlink()
        return res
