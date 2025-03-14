# -*- encoding: utf-8 -*-
from datetime import datetime
from collections import defaultdict, OrderedDict
from operator import itemgetter
from itertools import groupby
import math
from odoo import models, fields, api, _, tools, SUPERUSER_ID

from odoo.tools import float_compare, float_round, float_is_zero
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    exchange_rate = fields.Float('汇率', digits=(16, 3), default=1.0)
    tax_id = fields.Many2one('account.tax', '税别')

    @api.onchange('tax_id')
    def onchange_tax_id(self):
        if self.tax_id:
            for line in self.order_line:
                line.taxes_id = [(6, 0, (self.tax_id.id,))]

    @api.onchange("partner_id", "company_id")
    def onchange_partner_id(self):
        res = super(PurchaseOrder, self).onchange_partner_id()

        if not self.partner_id:
            self.payment_term_id = False
            self.currency_id = self.env.user.company_id.currency_id.id
            self.tax_id = False
        else:
            if not self.partner_id.partner_currency_id:
                raise UserError(u"供应商资料币别不可为空!")
            if not self.partner_id.account_tax_id:
                raise UserError(u"供应商资料税别不可为空!")
            self.tax_id = self.partner_id.account_tax_id.id or False
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id or False
            self.currency_id = self.partner_id.partner_currency_id.id or self.env.user.company_id.currency_id.id or False
            self.exchange_rate = self.partner_id.partner_currency_id.rate or False

        return res

    @api.onchange('fiscal_position_id')
    def _compute_tax_id(self):
        pass


class PurchaseOrderline(models.Model):
    _inherit = "purchase.order.line"

    # 替换源生方法
    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id._get_fiscal_position(line.order_id.partner_id)
            # filter taxes by company
            taxes = line.order_id.tax_id
            line.taxes_id = fpos.map_tax(taxes)
