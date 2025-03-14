# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, tools
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from .. import public

class AccountAccountType(models.Model):
    _name = "cncw.account.type"
    _description = "科目类型"

    name = fields.Char(string='科目类型', required=True, translate=False)
    note = fields.Char(string='备注')
    include_initial_balance = fields.Boolean(string=u"账户余额结转",)
    type = fields.Selection([
        ('other', '固定规则'),
        ('receivable', '应收账款'),
        ('payable', '应付账款'),
        ('liquidity', '流动资产'),
    ], required=True, default='other',)
    internal_group = fields.Selection([
        ('equity', '相等'),
        ('asset', '资产'),
        ('liability', '流动资产'),
        ('income', '收入'),
        ('expense', '费用'),
        ('off_balance', '不平'),
    ], string=u"内部分类",
        required=True,)

    def create(self, values):
        if 'name' in values:
            if values['name']:
                public.check_unique(self, ['name'], values, '科目类型')
        res_id = super(AccountAccountType, self).create(values)
        return res_id

    def write(self, vals, ):
        if 'name' in vals:
            public.check_unique(self, ['name'], vals, '科目类型')
        res = super(AccountAccountType, self).write(vals)
        return res


class AccountAccount(models.Model):
    _name = "cncw.account"
    _description = "会计科目"
    _check_company_auto = True
    _order = "company_id,parent_left"
    _parent_store = True
    _rec_name = 'code'

    @api.depends('code', 'complete_name')
    def name_get(self):
        res = []
        for record in self:
            name = '%s' % (record.complete_name)
            # name=record.code
            res.append((record['id'], name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(
                ['|', '|', '|', ('name', operator, name), '&', ('code', 'like', name), ('code', '>=', name),
                 ('short_code', operator, name), ('complete_name', operator, name)] + args,
                limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.model
    def get_sub_account_ids(self, account_id=False):
        """
        由会科取其 可用 辅助核算
        :param self:
        :param account_id:
        :return:
        """
        subaccounts = self.env['res.partner'].browse([])
        # 增加判断是否有多辅助核算的数据，没有的话沿用原来的逻辑
        if account_id and account_id.subaccount_category_ids:
            for subaccount_category_id in account_id.subaccount_category_ids:
                if subaccount_category_id.code == 'customer':
                    subaccounts = self.env['res.partner'].search([('customer_rank', '>', 0)])
                elif subaccount_category_id.code == 'supplier':
                    subaccounts = self.env['res.partner'].search([('supplier_rank', '>', 0)])
                else:
                    for x in subaccount_category_id.sub_account_ids:
                        subaccounts |= x
        elif account_id and account_id.subaccount_category_id:
            if account_id.subaccount_category_id.code == 'customer':
                subaccounts = self.env['res.partner'].search([('customer_rank', '>', 0)])
            elif account_id.subaccount_category_id.code == 'supplier':
                subaccounts = self.env['res.partner'].search([('supplier_rank', '>', 0)])
            else:
                for x in account_id.subaccount_category_id.sub_account_ids:
                    subaccounts |= x
        return subaccounts

    def update_level(self):
        objs = self.env['cncw.account'].search([('active', '=', True)])
        for obj in objs:
            obj._get_level()

    @api.depends('parent_id')
    def _get_level(self):
        level = 1
        parent = self.parent_id
        while parent:
            level += 1
            parent = parent.parent_id
        self.level = level

    @api.depends('parent_id', 'code', 'name')
    def _compute_complete_code(self):
        for record in self:
            name = ""
            code = ""
            if record.parent_id:
                # code = (self.parent_id and self.parent_id.complete_code or '')
                name = (record.parent_id and record.parent_id.complete_name or '')
            # code += (self.code and self.code or '')
            name += (record.name and record.name or '')
            record.complete_name = name

    @api.depends('children_ids', 'parent_id')
    def complete_has_children(self):
        for record in self:
            if record.parent_id and not record.parent_id.has_children:
                record.parent_id.has_children = True
            if len(record.children_ids) > 0:
                record.has_children = True
            else:
                record.has_children = False

    @api.constrains('internal_type', 'reconcile')
    def _check_reconcile(self):
        for account in self:
            if account.internal_type in ('receivable', 'payable') and account.reconcile == False:
                raise ValidationError(('您不能有无法对账的应收账款/应付账款,其编码是 : %s)', account.code))

    cncw_org = fields.Many2one('cncw.org', '核算机构', ondelete='cascade',)
    code = fields.Char('科目编码',size=64, required=True, index=True)
    has_children = fields.Boolean('有子阶', default=False, compute="complete_has_children")
    name = fields.Char('科目名称', required=True)
    complete_name = fields.Char(compute='_compute_complete_code', store=True, string='全称')
    parent_id = fields.Many2one('cncw.account', '上级科目', ondelete='cascade', domain=[('type', '=', 'view')])
    children_ids = fields.One2many('cncw.account', 'parent_id', '明细科目')
    user_type_id = fields.Many2one('cncw.account.type', string='Type', required=False,)
    sub_account_type = fields.Selection(public.SUB_ACCOUNT_TYPE, '会科属性', required=True, default='none')
    subaccount_category_id = fields.Many2one('subaccount.category', '辅助核算类别', required=False,
                                             ondelete="restrict")
    subaccount_category_ids = fields.Many2many('subaccount.category', string='辅助核算类别')
    dc_type = fields.Selection(public.DC_TYPE, '借贷', default='D')
    dc_type_int = fields.Integer('借贷值', help='用于计算', compute='compute_dc_type', store=True)
    active = fields.Boolean('启用', default=True)
    parent_left = fields.Integer('Parent Left', default=0)
    parent_right = fields.Integer('Parent Right', default=0)
    parent_path = fields.Char(index=True)
    level = fields.Integer('阶层', compute='_get_level', store=True, default=1)
    account_category = fields.Selection([('1', '资产类'),
                                         ('2', '负债类'),
                                         ('3', '共同类'),
                                         ('4', '所有者权益类'),
                                         ('5', '成本类'),
                                         ('6', '费用类'),
                                         ('7', '收入类'),
                                         ], '科目大类', default='1')

    ap_ar_type = fields.Selection([('10', '预付帐款'),
                                   ('11', '应付帐款'),
                                   ('12', '应付费用'),
                                   ('13', '其它应付'),
                                   ('20', '预收帐款'),
                                   ('21', '应收帐款'),

                                   ('23', '其它应收'), ], '应付应收科目类别', help='用于ap ar 月结时金额规类汇总')
    currency_id = fields.Many2one('res.currency', '币别', default=lambda self: self.env.user.company_id.currency_id)
    short_code = fields.Char('简码')
    active =  fields.Boolean('启用', default=True)
    deprecated = fields.Boolean(index=True, default=False)
    used = fields.Boolean(compute='_compute_used', search='_search_used')

    internal_type = fields.Selection(related='user_type_id.type', string=u"内部分类", store=True, readonly=True)
    internal_group = fields.Selection(related='user_type_id.internal_group', string=u"内部分类", store=True, readonly=True)
    reconcile = fields.Boolean(string='允许对帐', default=False,)
    note = fields.Text('备注')
    company_id = fields.Many2one('res.company', string='公司', required=True, readonly=True,
        default=lambda self: self.env.company)
    root_id = fields.Many2one('cncw.root', compute='_compute_account_root', store=True)

    @api.depends('code')
    def _compute_account_root(self):
        # this computes the first 2 digits of the account.
        # This field should have been a char, but the aim is to use it in a side panel view with hierarchy, and it's only supported by many2one fields so far.
        # So instead, we make it a many2one to a psql view with what we need as records.
        for record in self:
            record.root_id = (ord(record.code[0]) * 1000 + ord(record.code[1:2] or '\x00')) if record.code else False


    _sql_constraints = [
        ('code_company_uniq', 'unique (code,company_id)', '每个公司编码必须唯一 !')
    ]

    def get_subaccount_category_ids(self):
        res = self.env['subaccount.category']
        for record in self:
            if record.sub_account_type == 'has':
                res |= record.subaccount_category_ids
        return res

    def init(self):
        self._cr.execute("""
            update cncw_account set parent_left=0 where parent_left is null;
            update cncw_account set parent_right=0 where parent_left is null;
        """)

    def write(self, vals, ):
        if 'active' in vals:
            vals.update(dict(deprecated=vals.get('active', False)))
        res = super(AccountAccount, self).write(vals)
        return res

    @api.onchange('name')
    def onchange_name(self):
        if self.name:
            self.short_code = public.multi_get_letter(self, self.name)
        else:
            self.short_code = ''

    @api.depends('dc_type')
    def compute_dc_type(self):
        for record in self:
            if record.dc_type == 'D':
                record.dc_type_int = 1
            else:
                record.dc_type_int = -1

    def _search_used(self, operator, value):
        if operator not in ['=', '!='] or not isinstance(value, bool):
            raise UserError(_('Operation not supported'))
        if operator != '=':
            value = not value
        self._cr.execute("""
            SELECT id FROM cncw_account account
            WHERE EXISTS (SELECT * FROM cncw_move_line aml WHERE aml.account_id = account.id LIMIT 1)
        """)
        return [('id', 'in' if value else 'not in', [r[0] for r in self._cr.fetchall()])]

    def _compute_used(self):
        ids = set(self._search_used('=', True)[0][2])
        for record in self:
            record.used = record.id in ids

    @api.model
    def _search_new_account_code(self, company, digits, prefix):
        for num in range(1, 10000):
            new_code = str(prefix.ljust(digits - 1, '0')) + str(num)
            rec = self.search([('code', '=', new_code), ('company_id', '=', company.id)], limit=1)
            if not rec:
                return new_code
        raise UserError(_('Cannot generate an unused account code.'))

    @api.depends('internal_group')
    def _compute_is_off_balance(self):
        for account in self:
            account.is_off_balance = account.internal_group == "off_balance"

    def _set_opening_debit(self):
        for record in self:
            record._set_opening_debit_credit(record.opening_debit, 'debit')

    def _set_opening_credit(self):
        for record in self:
            record._set_opening_debit_credit(record.opening_credit, 'credit')

    @api.model
    def default_get(self, default_fields):
        """If we're creating a new account through a many2one, there are chances that we typed the account code
        instead of its name. In that case, switch both fields values.
        """
        if 'name' not in default_fields and 'code' not in default_fields:
            return super().default_get(default_fields)
        default_name = self._context.get('default_name')
        default_code = self._context.get('default_code')
        if default_name and not default_code:
            try:
                default_code = int(default_name)
            except ValueError:
                pass
            if default_code:
                default_name = False
        contextual_self = self.with_context(default_name=default_name, default_code=default_code)
        return super(AccountAccount, contextual_self).default_get(default_fields)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    @api.onchange('user_type_id')
    def _onchange_user_type_id(self):
        self.reconcile = self.internal_type in ('receivable', 'payable')
        if self.internal_type == 'liquidity':
            self.reconcile = False
        elif self.internal_group == 'off_balance':
            self.reconcile = False
            self.tax_ids = False
        elif self.internal_group == 'income' and not self.tax_ids:
            self.tax_ids = self.company_id.account_sale_tax_id
        elif self.internal_group == 'expense' and not self.tax_ids:
            self.tax_ids = self.company_id.account_purchase_tax_id

    def name_get(self):
        result = []
        for account in self:
            name = account.code + ' ' + account.name
            result.append((account.id, name))
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if default.get('code', False):
            return super(AccountAccount, self).copy(default)
        try:
            default['code'] = (str(int(self.code) + 10) or '').zfill(len(self.code))
            default.setdefault('name', _("%s (copy)") % (self.name or ''))
            while self.env['cncw.account'].search([('code', '=', default['code']),
                                                      ('company_id', '=', default.get('company_id', False) or self.company_id.id)], limit=1):
                default['code'] = (str(int(default['code']) + 10) or '')
                default['name'] = _("%s (copy)") % (self.name or '')
        except ValueError:
            default['code'] = _("%s (copy)") % (self.code or '')
            default['name'] = self.name
        return super(AccountAccount, self).copy(default)

    def action_duplicate_accounts(self):
        for account in self.browse(self.env.context['active_ids']):
            account.copy()

class AccountRoot(models.Model):
    _name = 'cncw.root'
    _description = '基础root'
    _auto = False

    name = fields.Char()
    parent_id = fields.Many2one('cncw.root')
    company_id = fields.Many2one('res.company')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW %s AS (
            SELECT DISTINCT ASCII(code) * 1000 + ASCII(SUBSTRING(code,2,1)) AS id,
                   LEFT(code,2) AS name,
                   ASCII(code) AS parent_id,
                   company_id
            FROM cncw_account WHERE code IS NOT NULL
            UNION ALL
            SELECT DISTINCT ASCII(code) AS id,
                   LEFT(code,1) AS name,
                   NULL::int AS parent_id,
                   company_id
            FROM cncw_account WHERE code IS NOT NULL
            )''' % (self._table,)
        )