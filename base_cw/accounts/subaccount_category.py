# -*- encoding: utf-8 -*-
from odoo import models, fields, api
from .. import public


class SubaccountCategory(models.Model):
    _name = 'subaccount.category'
    _description = '辅助核算类别设定'

    code = fields.Char('编码')
    name = fields.Char('辅助核算类别', translate=False)
    note = fields.Char('备注', )
    active = fields.Boolean('启用', default=True)
    sub_account_ids = fields.One2many('res.partner', 'subaccount_category_id', '辅助核算')
    is_system_created = fields.Boolean('系统预设', default=False, readonly=True)

    partner_id = fields.Many2one('res.partner', '按供应商过滤')
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company)

    _sql_constraints = [('code_unique', 'unique (code)', '辅助核算类别编码不能重复!'),
                        ('name_unique', 'unique (name)', '辅助核算类别名称不能重复!'), ]

    # @api.model
    def create(self, values):
        if 'code' in values:
            if values['code']:
                public.check_unique(self, ['code'], values, '编码')
        if 'name' in values:
            if values['name']:
                public.check_unique(self, ['name'], values, '辅助核算类别')
        res_id = super(SubaccountCategory, self).create(values)
        return res_id

    def action_sync_hr_employee(self):
        self.ensure_one()
        emps = self.env['hr.employee'].search([('active', '!=', False)])
        for x in emps:
            item = dict(code=x.code,
                        name=x.name,
                        subaccount_category_id=self.id,
                        active=True,
                        customer_rank=0,
                        supplier_rank=0,
                        employee=True,
                        )
            self.create_or_write(x, item)

    def create_or_write(self, x, item):
        res_partner_id = self.env['res.partner'].search(
            [('code', '=', item.get('code')), ('name', '=', item.get('name'))])
        if res_partner_id:
            res_partner_id.write(item)
            res_partner_id.customer_rank = False
            x.partner_id = res_partner_id.id
        else:
            partner_id = self.env['res.partner'].create(item)
            partner_id.customer_rank = False
            x.partner_id = partner_id.id

    def action_sync_hr_department(self):
        self.ensure_one()

        depts = self.env['hr.department'].search([('partner_id', '=', False), ('active', '!=', False)])
        for x in depts:
            item = dict(code=x.code,
                        name=x.name,
                        subaccount_category_id=self.id,
                        active=True,
                        customer_rank=0,
                        supplier_rank=0,
                        employee=False,
                        # state='approve',
                        )
            self.create_or_write(x, item)

    def action_sync_cash_flow(self):
        self.ensure_one()
        report = self.env['account.report.format.designer'].search([('report_type', '=', 'cash')], limit=1)
        for x in report.line_ids.filtered(lambda x: x.partner_id and x.llc > 0):
            item = dict(code='cash_%s' % (
                str(x.sequence).zfill(len(str(x.sequence)) if len(str(x.sequence)) >= 2 else len(str(x.sequence)) + 1)),
                        name=x.name,
                        subaccount_category_id=self.id,
                        customer_rank=0,
                        supplier_rank=0,
                        employee=False,
                        active=True,
                        )
            self.create_or_write(x, item)

        for x in report.line_ids.filtered(lambda x: not x.partner_id and x.llc > 0):
            item = dict(code='cash_%s' % (
                str(x.sequence).zfill(len(str(x.sequence)) if len(str(x.sequence)) >= 2 else len(str(x.sequence)) + 1)),
                        name=x.name,
                        subaccount_category_id=self.id,
                        customer_rank=0,
                        supplier_rank=0,
                        employee=False,
                        active=True,
                        )
            self.create_or_write(x, item)
            # self._cr.commit()

    def action_sync_bank(self):
        self.ensure_one()
        if self.partner_id:
            bank_ids = self.env['res.partner.bank'].search([('partner_id', '=', self.partner_id.id),
                                                            ('acc_number', '!=', False), ('bank_id', '!=', False)])
        else:
            bank_ids = self.env['res.partner.bank'].search([('acc_number', '!=', False), ('bank_id', '!=', False)])
        for x in bank_ids:
            item = dict(code=x.acc_number,
                        name=x.acc_number,
                        subaccount_category_id=self.id,
                        active=True,
                        customer_rank=0,
                        supplier_rank=0,
                        employee=False,
                        )
            self.create_or_write(x, item)

    def write(self, vals):
        if 'code' in vals:
            public.check_unique(self, ['code'], vals, '编码')
        if 'name' in vals:
            public.check_unique(self, ['name'], vals, '辅助核算类别')
        return super(SubaccountCategory, self).write(vals)
