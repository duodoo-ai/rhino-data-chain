# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class crm_team(models.Model):
    _inherit = 'crm.team'
    _description = '销售团队'

    def _compute_banks(self):
        self.receive_bank_ids = self.bank_ids.filtered(lambda x: x.bank_type == 'A')
        self.notice_bank_ids = self.bank_ids.filtered(lambda x: x.bank_type != 'A')

    name = fields.Char(translate=False)
    code = fields.Char('编码', default=False)
    bank_ids = fields.Many2many('res.partner.bank', 'crm_team_bank_rel', 'team_id', 'bank_id', '银行帐号')
    receive_bank_ids = fields.Many2many('res.partner.bank', compute='_compute_banks', string='收款行')
    notice_bank_ids = fields.Many2many('res.partner.bank', compute='_compute_banks', string='通知行')
    note = fields.Text('备注')
    state = fields.Selection([('draft', '草稿'), ('confirmed', '已审核')], string='状态',
                             default='draft')
    _sql_constraints = [
        ('name_unique', 'unique (name)', '团队名称不可重复 !')
    ]

    # 确认审核
    def action_confirmed(self):
        self.ensure_one()
        self.state = "confirmed"

    # 取消确认
    def action_cancel(self):
        self.ensure_one()
        self.state = "draft"

    def copy(self, default=None):
        self.ensure_one()
        default = default or {}
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(crm_team, self).copy(default)

    def write(self, values):
        self.ensure_one()
        if 'name' in values:
            base_cw.public.check_unique(self, ['name'], values, '团队名称')
        res = super(crm_team, self).write(values)
        return res

    def unlink(self):
        for r in self:
            if r.state == 'confirmed':
                raise UserError(_('操作错误!已经审核的资料不可以删除！'))
        res = super(crm_team, self).unlink()
        return res
