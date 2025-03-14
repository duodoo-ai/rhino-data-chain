# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


class BasePeriodControl(models.Model):
    _name = 'base.period.control'
    _description = '配置期间表'

    name = fields.Char('名称', default='期间配置表')
    line_ids = fields.One2many('base.period.control.line', 'master_id', string='模块明细')
    active = fields.Boolean('有效', default=True)
    ir_rule_ids = fields.Many2many('ir.rule', string='权限')

    def create_ir_rule(self):
        """创建权限明细"""
        if self.ir_rule_ids:
            self.ir_rule_ids.unlink()
        val_list = []
        for mod in self.line_ids:
            val = {'name': '模块%s结转控制' % mod.ir_model_id.name,
                   'perm_write': 1,
                   'perm_read': 0,
                   'perm_unlink': 0,
                   'perm_create': 0,
                   'groups': [(6, 0, [self.env.ref('base.group_user').id,
                                      self.env.ref('base_cw.account_group_account_user').id])],
                   'model_id': mod.ir_model_id.id,
                   'domain_force': '%s' % self.get_cdr_domain(mod.field_name.name),

                   }
            val_list.append(val)
        ir_rule_ids = self.env['ir.rule'].create(val_list)
        self.ir_rule_ids = [(6, 0, ir_rule_ids.ids)]

    def get_cdr_domain(self, field_name):
        # Used from facility_manager/security.xml to filter CDR records
        # period_control = self.env['base.period.control'].search([], limit=1)
        # model_list = self.ir_model_ids
        period = self.env['account.period'].search([('state', '=', 'open')], order='date_start', limit=1)
        if period:
            return str([(field_name, '>=', fields.Datetime.to_string(period.date_start))])
        else:
            raise UserError('没有开启的期间！')

    def add_line(self):
        """添加明细按钮"""
        return {
            'name': '模块选择',
            'view_mode': 'form',
            'res_model': 'wizard.control.model',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_master_id': self.id}

        }


class BasePeriodControlLine(models.Model):
    _name = 'base.period.control.line'
    _description = "期间控制行"

    master_id = fields.Many2one('base.period.control', string='主表')
    ir_model_id = fields.Many2one('ir.model', string='模块')
    model_name = fields.Char(related='ir_model_id.name', string='模块名称')
    model_state = fields.Selection(related='ir_model_id.state', string='模块类型')
    model_transient = fields.Boolean(related='ir_model_id.transient', string='瞬态类')
    field_name = fields.Many2one('ir.model.fields', string='控制字段')
