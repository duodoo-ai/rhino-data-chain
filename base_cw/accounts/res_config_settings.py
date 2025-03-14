# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    org_id =  fields.Many2one('cncw.org',string='财务机构')
    org_period_id = fields.Many2one('account.fiscalyear',string='会计年度',domain="[('org_id','=',org_id)]")
    cncw_tag_model =  fields.Many2one('cncw.glob_tag_model',string='全局标签')
    cncw_tag_class =  fields.Many2one('cncw.glob_tag_class',string='全局标签')
    has_cncw_accounting_entries = fields.Boolean(default=True)
    has_cncw_chart_of_accounts = fields.Boolean(compute='_compute_has_cncw_chart_of_accounts', string='科目模板？',)
    currency_id = fields.Many2one('res.currency', related="company_id.currency_id",  readonly=True,
        string='货币')
    # Technical field to hide country specific fields from accounting configuration
    country_code = fields.Char(related='company_id.country_id.code', readonly=True)
    # cncw_chart_template_id = fields.Many2one('cncw.chart.template', string='财务模板',)
    cncw_sale_tax_id = fields.Many2one('account.tax', string="默认销售税率", related='company_id.account_sale_tax_id', readonly=False)
    cncw_purchase_tax_id = fields.Many2one('account.tax', string="默认采购税率", related='company_id.account_purchase_tax_id', readonly=False)

    module_cncw_ledger = fields.Boolean(string='财务总帐模组')
    module_cncw_statement = fields.Boolean(string='应收应付模组')
    module_customer_credit_limit = fields.Boolean(string="信用额度模组")

    @api.depends('company_id')
    def _compute_has_cncw_chart_of_accounts(self):
        pass
        # self.has_cncw_chart_of_accounts = bool(self.company_id.cncw_chart_template_id)
        # self.has_cncw_accounting_entries = self.env['cncw.chart.template'].existing_accounting(self.company_id)

    def action_add_org(self):
        pass
