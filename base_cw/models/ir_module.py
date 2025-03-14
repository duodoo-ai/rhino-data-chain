# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import Warning


class ir_module_module(models.Model):
    _inherit = "ir.module.module"

    def button_immediate_install(self):
        mrp = self.search([('name', '=', 'mrp')])
        stock_cost_inv = self.search([('name', '=', 'stock_cost_inv')])
        to_install_name = self.mapped('name')

        if ('mrp' in to_install_name and 'stock_cost_inv' in to_install_name) or \
                ('mrp' in to_install_name and stock_cost_inv.state == 'installed') or \
                ('stock_cost_inv' in to_install_name and mrp.state == 'installed'):
            raise Warning('mrp 和 stock_cost_inv 不能同时安装')

        return super(ir_module_module, self).button_immediate_install()
