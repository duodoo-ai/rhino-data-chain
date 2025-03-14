# -*- coding: utf-8 -*-

from odoo import models,api,fields

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    department_id = fields.Many2one('hr.department', '部门', required=False)

