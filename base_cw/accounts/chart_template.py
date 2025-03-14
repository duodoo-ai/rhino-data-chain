# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo import api, fields, models, _
from odoo import SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from .. import public
from . import cncw_org

import logging

_logger = logging.getLogger(__name__)

def migrate_set_tags_and_taxes_updatable(cr, registry, module):
    ''' This is a utility function used to manually set the flag noupdate to False on tags and account tax templates on localization modules
    that need migration (for example in case of VAT report improvements)
    '''
    env = api.Environment(cr, SUPERUSER_ID, {})
    xml_record_ids = env['ir.model.data'].search([
        ('model', 'in', ['account.tax.template', 'cncw.account.tag']),
        ('module', 'like', module)
    ]).ids
    if xml_record_ids:
        cr.execute("update ir_model_data set noupdate = 'f' where id in %s", (tuple(xml_record_ids),))

def preserve_existing_tags_on_taxes(cr, registry, module):
    ''' This is a utility function used to preserve existing previous tags during upgrade of the module.'''
    env = api.Environment(cr, SUPERUSER_ID, {})
    xml_records = env['ir.model.data'].search([('model', '=', 'cncw.account.tag'), ('module', 'like', module)])
    if xml_records:
        cr.execute("update ir_model_data set noupdate = 't' where id in %s", [tuple(xml_records.ids)])

#  ---------------------------------------------------------------
#   Account Templates: Account, Tax, Tax Code and chart. + Wizard
#  ---------------------------------------------------------------


class AccountGroupTemplate(models.Model):
    _name = "cncw.account.group.template"
    _description = 'Template for Account Groups'
    _order = 'code_prefix_start'

    parent_id = fields.Many2one('cncw.account.group.template', index=True, ondelete='cascade')
    name = fields.Char(required=True)
    code_prefix_start = fields.Char()
    code_prefix_end = fields.Char()
    # chart_template_id = fields.Many2one('cncw.chart.template', string='Chart Template', required=True)


class AccountAccountTemplate(models.Model,cncw_org.Globcncw_tag_Model):
    _name = "cncw.account.template"
    _description = 'Templates for Accounts'
    _order = "code"

    name = fields.Char(required=True, index=True)
    currency_id = fields.Many2one('res.currency', string='Account Currency', help="Forces all moves for this account to have this secondary currency.")
    code = fields.Char(size=64, required=True, index=True)
    user_type_id = fields.Many2one('cncw.account.type', string='Type', required=True,
        help="These types are defined according to your country. The type contains more information "\
        "about the account and its specificities.")
    reconcile = fields.Boolean(string='Allow Invoices & payments Matching', default=False,
        help="Check this option if you want the user to reconcile entries in this account.")
    note = fields.Text()
    tax_ids = fields.Many2many('account.tax.template', 'cncw_account_template_tax_rel', 'account_id', 'tax_id', string='Default Taxes')
    nocreate = fields.Boolean(string='Optional Create', default=False,
        help="If checked, the new chart of accounts will not contain this by default.")
    # chart_template_id = fields.Many2one('cncw.chart.template', string='Chart Template',
    #     help="This optional field allow you to link an account template to a specific chart template that may differ from the one its root parent belongs to. This allow you "
    #         "to define chart templates that extend another and complete it with few new accounts (You don't need to define the whole structure that is common to both several times).")
    parent_id = fields.Many2one('cncw.account.template', '上级科目', ondelete='cascade', domain=[('type', '=', 'view')])
    children_ids = fields.One2many('cncw.account.template', 'parent_id', '明细科目')
    user_type_id = fields.Many2one('cncw.account.type', string='Type', required=False, oldname="user_type", )
    sub_account_type = fields.Selection(public.SUB_ACCOUNT_TYPE, '会科属性', required=True, default='none')
    subaccount_category_id = fields.Many2one('subaccount.category', '辅助核算类别', required=False,
                                             ondelete="restrict")
    dc_type = fields.Selection(public.DC_TYPE, '借贷', default='D')
    active = fields.Boolean('启用', default=True)
    parent_left = fields.Integer('Parent Left', default=0)
    parent_right = fields.Integer('Parent Right', default=0)
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

    @api.depends('name', 'code')
    def name_get(self):
        res = []
        for record in self:
            name = record.name
            if record.code:
                name = record.code + ' ' + name
            res.append((record.id, name))
        return res


class AccountChartTemplate(models.Model,cncw_org.Globcncw_tag_Model):
    _name = "cncw.chart.template"
    _description = "会计科目模板"

    name = fields.Char(required=True)
    parent_id = fields.Many2one('cncw.chart.template', string='上级模板')
    code_digits = fields.Integer(string='# of Digits', required=True, default=6, help="No. of Digits to use for account code")
    visible = fields.Boolean(string='Can be Visible?', default=True,
        help="Set this to False if you don't want this template to be used actively in the wizard that generate Chart of Accounts from "
            "templates, this is useful when you want to generate accounts of this template only when loading its child template.")
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    use_anglo_saxon = fields.Boolean(string="Use Anglo-Saxon accounting", default=False)
    complete_tax_set = fields.Boolean(string='Complete Set of Taxes', default=True,
        help="This boolean helps you to choose if you want to propose to the user to encode the sale and purchase rates or choose from list "
            "of taxes. This last choice assumes that the set of tax defined on this template is complete")
    # account_ids = fields.One2many('cncw.account.template', 'chart_template_id', string='Associated Account Templates')
    # tax_template_ids = fields.One2many('account.tax.template', 'chart_template_id', string='Tax Template List',
    #     help='List of all the taxes that have to be installed by the wizard')
    bank_account_code_prefix = fields.Char(string='Prefix of the bank accounts', required=True)
    cash_account_code_prefix = fields.Char(string='Prefix of the main cash accounts', required=True)
    transfer_account_code_prefix = fields.Char(string='Prefix of the main transfer accounts', required=True)
    income_currency_exchange_account_id = fields.Many2one('cncw.account.template',
        string="Gain Exchange Rate Account", domain=[('internal_type', '=', 'other'), ('deprecated', '=', False)])
    expense_currency_exchange_account_id = fields.Many2one('cncw.account.template',
        string="Loss Exchange Rate Account", domain=[('internal_type', '=', 'other'), ('deprecated', '=', False)])
    account_journal_suspense_account_id = fields.Many2one('cncw.account.template', string='Journal Suspense Account')
    default_cash_difference_income_account_id = fields.Many2one('cncw.account.template', string="Cash Difference Income Account")
    default_cash_difference_expense_account_id = fields.Many2one('cncw.account.template', string="Cash Difference Expense Account")
    default_pos_receivable_account_id = fields.Many2one('cncw.account.template', string="PoS receivable account")
    property_account_receivable_id = fields.Many2one('cncw.account.template', string='Receivable Account')
    property_account_payable_id = fields.Many2one('cncw.account.template', string='Payable Account')
    property_account_expense_categ_id = fields.Many2one('cncw.account.template', string='Category of Expense Account')
    property_account_income_categ_id = fields.Many2one('cncw.account.template', string='Category of Income Account')
    property_account_expense_id = fields.Many2one('cncw.account.template', string='Expense Account on Product Template')
    property_account_income_id = fields.Many2one('cncw.account.template', string='Income Account on Product Template')
    property_stock_account_input_categ_id = fields.Many2one('cncw.account.template', string="Input Account for Stock Valuation")
    property_stock_account_output_categ_id = fields.Many2one('cncw.account.template', string="Output Account for Stock Valuation")
    property_stock_valuation_account_id = fields.Many2one('cncw.account.template', string="Account Template for Stock Valuation")
    property_tax_payable_account_id = fields.Many2one('cncw.account.template', string="Tax current account (payable)")
    property_tax_receivable_account_id = fields.Many2one('cncw.account.template', string="Tax current account (receivable)")
    property_advance_tax_payment_account_id = fields.Many2one('cncw.account.template', string="Advance tax payment account")
    property_cash_basis_base_account_id = fields.Many2one(
        comodel_name='cncw.account.template',
        domain=[('deprecated', '=', False)],
        string="Base Tax Received Account",
        help="Account that will be set on lines created in cash basis journal entry and used to keep track of the "
             "tax base amount.")

    @api.model
    def existing_accounting(self, company_id):
        """ Returns True iff some accounting entries have already been made for
        the provided company (meaning hence that its chart of accounts cannot
        be changed anymore).
        """
        model_to_check = ['cncw.account']
        for model in model_to_check:
            if self.env[model].sudo().search([('company_id', '=', company_id.id)], limit=1):
                return True
        return False