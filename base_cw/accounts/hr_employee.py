# -*- encoding: utf-8 -*-
import time, datetime
from collections import defaultdict, OrderedDict
from operator import itemgetter
from itertools import groupby
import math
from odoo import models, fields, api, _, tools, SUPERUSER_ID


class hr_employee(models.Model):
    _inherit = "hr.employee"
    _description = u"员工"

    code = fields.Char('员工工号')
    partner_id = fields.Many2one('res.partner', '辅助核算', ondelete="set null")

    def create(self, vals):
        res = super(hr_employee, self).create(vals)
        return res

    def write(self, vals):
        if 'code' in vals and self.partner_id:
            self.partner_id.code = vals.get('code')
        if 'name' in vals and self.partner_id:
            self.partner_id.name = vals.get('name')
        res = super(hr_employee, self).write(vals)
        return res

    @api.constrains('code')
    def check_name(self):
        if self.search_count([('code', '=', self.code)]) > 1:
            raise Warning('工号 %s 已经存在' % self.code)


class hr_department(models.Model):
    _inherit = "hr.department"
    # _rec_name = 'code'
    _description = u"部门"

    partner_id = fields.Many2one('res.partner', '辅助核算', ondelete="set null")
    code = fields.Char('部门代号')

    @api.depends('name', 'parent_id.complete_name', 'code')
    def _compute_complete_name(self):
        """重构部门展示名称"""
        for department in self:
            if department.parent_id:
                department.complete_name = '%s / %s %s' % (department.parent_id.complete_name,
                                                           department.name, department.code or '')
            else:
                department.complete_name = '%s %s' % (department.name, department.code or '')

    def create(self, vals):
        res = super(hr_department, self).create(vals)
        return res

    def write(self, vals):
        if 'code' in vals and self.partner_id:
            self.partner_id.code = vals.get('code')
        if 'name' in vals and self.partner_id:
            self.partner_id.name = vals.get('name')
        res = super(hr_department, self).write(vals)
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=880):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', ('code', 'ilike', name), ('name', 'ilike', name)] + args, limit=limit)
        if not recs:
            recs = self.search(['|', ('code', 'ilike', name), ('name', 'ilike', name)] + args, limit=limit)
        return recs.name_get()


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    code = fields.Char('编号')
    partner_id = fields.Many2one('res.partner', '辅助核算', ondelete="set null")
