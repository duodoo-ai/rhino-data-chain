# -*- encoding: utf-8 -*-

from odoo import models, fields, api
from odoo import tools
from odoo.exceptions import UserError

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class res_users_employee(models.Model):
    _name = "res.users.employee"
    _description = '用户清单'
    _auto = False

    employee_id = fields.Many2one('hr.employee', '员工', required=False, )
    user_id = fields.Many2one('res.users', '员工对应用户', required=False, )
    partner_id = fields.Many2one('res.partner', '往来单位', required=False, )
    parent_user_id = fields.Many2one('res.users', '部门经理对应用户', required=False, )
    parent_employee__id = fields.Many2one('hr.employee', '部门经理', required=False, )
    parent_partner_id = fields.Many2one('res.partner', '部门经理对应往来单位', required=False, )
    department_id = fields.Many2one('hr.department', '部门', required=False, )

    def init(self):
        tools.drop_view_if_exists(self._cr, 'res_users_employee')
        self._cr.execute("""
              drop view if exists res_users_employee;
              create or replace view res_users_employee as (
              select a.id as employee_id,
                     b.user_id,
                     c.partner_id,
                     a.department_id,
                     bb.user_id as parent_user_id,
                     a.parent_id as parent_employee_id,
                     cc.partner_id as parent_partner_id
                     from hr_employee a left join resource_resource b on a.resource_id=b.id
                     left join res_users c on b.user_id=c.id
                     left join res_partner d on c.partner_id=d.id
                     left join hr_employee aa on a.parent_id=aa.id
                     left join resource_resource bb on aa.resource_id=bb.id
                     left join res_users cc on bb.user_id=cc.id
                     left join res_partner dd on cc.partner_id=dd.id
                     left join hr_department e on a.department_id=e.id
                     where b.user_id is not null
                      )
        """)


class res_users_parent(models.Model):
    """
    MF:
    1、由员工的 阶层关系 找登入用户的阶层关系，
    递归部分是由父阶找所有的 子阶
    2、最后一个select 问题 是为了把父阶也加一笔进去
       用途:a.用于权限过滤，当前用户可以看到自已和下阶用户的 资料
    """
    _name = "res.users.parent"
    _description = '用户清单'
    _auto = False

    user_id = fields.Many2one('res.users', '子阶用户', required=False, )
    parent_user_id = fields.Many2one('res.users', '父阶用户', required=False, )

    def init(self):
        tools.drop_view_if_exists(self._cr, 'res_users_parent')
        self._cr.execute("""
         drop view if exists res_users_parent;
         create or replace view res_users_parent as (
                    WITH RECURSIVE r AS (
                                           select user_id,parent_user_id,employee_id,parent_employee_id
                                             from res_users_employee
                                            union all
                                           select a.user_id,r.user_id as parent_user_id,
                                                  a.employee_id,r.parent_employee_id
                                             from res_users_employee a, r
                                            where a.parent_employee_id = r.employee_id
                         )
                    select  user_id,parent_user_id from r
                    union all
                    select user_id,user_id parent_user_id
                      from res_users_employee
                     where user_id is not null)
        """)


CUST_SOURCE = [('A', '自行开发'),
               ('B', '展会'),
               ('C', '客户推荐'),
               ('D', '员工推荐'),
               ('E', '友人推荐'),
               ('F', '黄页'),
               ('G', '自动上门'),
               ('H', '网上获取'),
               ('I', '其他'), ]


class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = '往来单位'

    @api.model
    def _default_partner_currency_id(self):
        return self.env.user.company_id.currency_id

    @api.model
    def _get_default_tax(self):
        try:
            return self.env.ref('base_cw.account_tax_h')
        except Exception as e:
            return self.env['account.tax'].search([('code', '=', 'H')], limit=1)

    partner_currency_id = fields.Many2one('res.currency', '交易币别',
                                          default=_default_partner_currency_id,
                                          required=True, ondelete="restrict")
    code = fields.Char('编号', default="/")
    account_tax_id = fields.Many2one('account.tax','税别',
                                     ondelete="set null", default=_get_default_tax)
    account_tax_amount = fields.Float(related='account_tax_id.amount', readonly=True, string='税率')
    is_customer = fields.Boolean('客户')
    is_supplier = fields.Boolean('供应商')
    is_default = fields.Boolean('默认', default=False)
    property_cncw_account_payable_id = fields.Many2one('cncw.account', string="应付款科目", required=False)
    property_cncw_account_receivable_id = fields.Many2one('cncw.account', string="应收款科目", required=False)
    payment_mode_id = fields.Many2one('payment.mode', '付款方式', )
    payment_term_id = fields.Many2one('account.payment.term', '付款条件')
    out_stock_amount = fields.Float('已出货金额', digits='Amount')
    return_amount = fields.Float('已退货金额', digits='Amount')
    rebate_amount = fields.Float('已折扣货金额', digits='Amount')
    fandian_amount = fields.Float('已返点货金额', digits='Amount')
    policy_amount = fields.Float('政策货金额', digits='Amount')
    checked_amount = fields.Float('已对帐金额', digits='Amount')
    invoiced_amount = fields.Float('已开票金额', digits='Amount')
    received_amount = fields.Float('已收收帐款', digits='Amount', help='含预收帐款')
    advance_amount = fields.Float('预收金额', digits='Amount', help='预收未冲销金额')
    receivable_amount = fields.Float('应收金额', digits='Amount', help='应收金额')

    @api.model_create_multi
    def create(self, vals_list):
        search_partner_mode = self.env.context.get('res_partner_search_mode')
        is_customer = search_partner_mode == 'customer'
        is_supplier = search_partner_mode == 'supplier'
        for vals in vals_list:
            if vals.get('code', '/') == '/':
                if is_customer:
                    vals['code'] = self.env['ir.sequence'].next_by_code(
                        'partner.customer.code') or '/'
                    vals['is_customer'] = True
                if is_supplier:
                    vals['code'] = self.env['ir.sequence'].next_by_code(
                        'partner.supplier.code') or '/'
                    vals['is_supplier'] = True
        return super(ResPartner, self).create(vals_list)
