# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _


class SubAccountLine(models.Model):
    _name = 'sub.account.line'
    _description = '多辅助核算中间表'

    category_id = fields.Many2one('subaccount.category', string='辅助核算类别')
    sub_account_id = fields.Many2one('res.partner', string='辅助核算')
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company)
