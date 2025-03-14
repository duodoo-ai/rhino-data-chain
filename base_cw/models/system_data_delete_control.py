# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

# #=============================================
# # 类名:system.data.delete.control
# # Copyright(c):
# # 功能描述: 控制系统初始化资料,不可以在UI删除;
# # 创 建 人: sunshine
# #=============================================
class system_data_delete_control(models.Model):
    """
    控制系统初始化资料,不可以在UI删除;

    1、所要控制的model为新增model只需继承此类即可,格式如下：
        _inherit=['system.data.delete.control']
        或
        _inherit='system.data.delete.control'
    2、如所控制的模组是odoo已有model 加继承为如下格式 (如此增加的栏位还是在原table)
        _name="'orign_model'"
        _inherit=['orign_model','system.data.delete.control']
    """
    _name = 'system.data.delete.control'
    _auto = 'False'
    _description = '系统数据删除控制'

    def unlink(self):
        for x in self:
            if x.is_system_created:
                raise  UserError('删除错误系统预设资料不可删除！')
        return super(system_data_delete_control, self).unlink()

    is_system_created = fields.Boolean('为系统初识化资料', required=False, default=False, help='标示此笔资料为系统初识化所创建,不可以删除')

    def write(self, vals):
        for x in self:
            if x.is_system_created:
                raise  UserError('资料修改错误,系统预设资料不可修改！')
        return super(system_data_delete_control, self).write(vals)
