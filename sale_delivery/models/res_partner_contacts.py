# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import Warning
import logging
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class ResPartnerContacts(models.Model):
    _name = 'res.partner.contacts'
    _description = "收货人信息"
    _order = "create_date desc"
    _check_company_auto = True

    name = fields.Char(string='收货人')
    phone = fields.Char(string='联系手机/电话')
    city_id = fields.Many2one('city.city', string='送货城市')
    street = fields.Text('送货详细地址')
    partner_id = fields.Many2one('res.partner', string='客户')
    logistic_no = fields.Char('物流单号')
    company_id = fields.Many2one('res.company', string='公司', required=True, index=True,
                                 default=lambda self: self.env.company.id)