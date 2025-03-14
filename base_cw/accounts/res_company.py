# -*- encoding: utf-8 -*-
from .. import public
from odoo import models, fields, api, _


class res_company(models.Model):
    _inherit = 'res.company'
    _description = '公司信息'

    cncw_credit_limit_control = fields.Boolean('销售信用额度控制', default=False)
    cncw_chart_template_id = fields.Many2one('cncw.chart.template', string='会计科目模板')