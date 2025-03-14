# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.tools import float_compare, float_round


class ir_attachment(models.Model):
    _inherit = 'ir.attachment'
    _description = '附件文件'

    res_model = fields.Char(readonly=False, )
    res_field = fields.Char(readonly=False, )
    res_id = fields.Integer(readonly=False, )

