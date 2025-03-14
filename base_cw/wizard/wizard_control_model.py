# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WizardControlModel(models.Model):
    _name = 'wizard.control.model'
    _description = '添加模块'

    master_id = fields.Many2one('base.period.control', string='期间表')
    ir_model_ids = fields.Many2many('ir.model', string='模块')

    def action_done(self):
        val_list = []
        for mod in self.ir_model_ids:
            field_name_list = mod.field_id.filtered(lambda x: x.ttype in ['date', 'datetime'])
            val = {'master_id': self.master_id.id,
                   'ir_model_id': mod.id,
                   'field_name': field_name_list[0].id if field_name_list else None}
            val_list.append(val)

        self.env['base.period.control.line'].create(val_list)
