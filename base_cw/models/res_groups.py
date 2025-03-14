# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.tools import float_compare, float_round
from .. import public


class res_groups(models.Model):
    _inherit ='res.groups'
    _description = '用户组'

    is_custom = fields.Boolean('用户自定义', required=False, default=False)

