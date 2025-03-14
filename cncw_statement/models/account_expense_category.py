# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError


class AccountExpenseCategory(models.Model):
    _name = 'account.expense.category'
    _rec_name = 'name'
    _description = '费用类别设置'

    @api.depends('name', 'parent_id')
    def name_get(self):
        res = []
        for record in self:
            name = record.name
            if record.parent_id:
                name = record.parent_id.name + ' / ' + name
            res.append((record.id, name))
        return res

    @api.model
    def _name_get_fnc(self):
        res = self.name_get()
        return dict(res)

    name = fields.Char('类别名称', required=True, )
    code = fields.Char('类别编号', required=True, )
    full_name = fields.Char('费用全称', required=True, )
    finance_checker = fields.Many2one('res.users', '复核人', )
    teller = fields.Many2one('res.users', '出纳', )
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    branch_leveltwo = fields.Boolean('部门二级复合', )
    account_id = fields.Many2one('cncw.account', '费用科目', required=False)
    special_mark = fields.Char('专用标记', )
    note = fields.Text('备注', )
    parent_id = fields.Many2one('account.expense.category', '上级类别',  ondelete='restrict')
    child_id = fields.One2many('account.expense.category', 'parent_id', '下级类别')
    sequence = fields.Integer('项次')
    type = fields.Selection([('view', '视图'),
                             ('normal', '标准')], '类属', default='normal')
    parent_left = fields.Integer('Left Parent', )
    parent_right = fields.Integer('Right Parent', )
    active = fields.Boolean('Active', default=True)
    company_id = fields.Many2one('res.company', 'Company',default=lambda self: self.env.company)
    state = fields.Selection([('draft', '草稿'), ('confirmed', '已审核')], string='状态',
                             default='draft')
    parent_path = fields.Char(index=True)
    sub_account_type = fields.Selection(related='account_id.sub_account_type', readonly=True,string='会科属性')
    sub_account_ids = fields.Many2many('res.partner', string='辅助核算')
    can_sub_account_ids = fields.Many2many('res.partner', compute='_get_sub_account_ids', string='可选辅助核算')


    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = 'sequence, name'
    _order = 'parent_left'

    _sql_constraints = [('name_uniq', 'unique (parent_id,name)',
                         '错误！您不能创建重复的类型编码信息.!'), ]

    @api.depends('account_id')
    def _get_sub_account_ids(self):
        for record in self:
            account_obj = self.env['cncw.account']
            record.can_sub_account_ids = account_obj.get_sub_account_ids(record.account_id)


    @api.model
    def child_get(self):
        return self.child_id

    # 确认审核
    def action_confirmed(self):
        self.ensure_one()
        self.state = "confirmed"

    # 取消确认
    def action_cancel(self):
        self.ensure_one()
        self.state = "draft"

    @api.model_create_multi
    def create(self, values):
        for value in values:
            if value['code']:
                base_cw.public.check_unique(self, ['code'], value, '类别编号')
            if value['name']:
                base_cw.public.check_unique(self, ['name'], value, '类别名称')
        res_id = super(AccountExpenseCategory, self).create(values)
        return res_id

    def copy(self, default=None):
        self.ensure_one()
        default = default or {}
        default.update(code=_("%s (copy)") % (self.code or ''))
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(AccountExpenseCategory, self).copy(default)

    def write(self, vals, ):
        self.ensure_one()
        if 'code' in vals:
            base_cw.public.check_unique(self, ['code'], vals, '类别编号')
        if 'name' in vals:
            base_cw.public.check_unique(self, ['name'], vals, '类别名称')
        res = super(AccountExpenseCategory, self).write(vals)
        return res

    def unlink(self):
        for r in self:
            if r.state == 'confirmed':
                raise UserError(_('操作错误!已经审核的资料不可以删除！'))
        res = super(AccountExpenseCategory, self).unlink()
        return res
