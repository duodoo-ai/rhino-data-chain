# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

class res_currency(models.Model):
    _name = 'res.currency'
    _inherit = ['res.currency', 'mail.thread']
    _description = '币别资料'
    _order = 'active desc, name'

    code = fields.Char('编号', required=False, default=False, tracking=True)
    name = fields.Char('币别', size=12, required=True, default=False, tracking=True)
    note = fields.Text('备注')

