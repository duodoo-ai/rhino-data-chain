# -*- coding: utf-8 -*-
import calendar
import datetime
from decimal import Decimal
import json
import logging
import threading
from odoo import models, fields, api, SUPERUSER_ID, exceptions
from odoo import tools
from odoo import sql_db
# import sys
# 日志
_logger = logging.getLogger(__name__)
# 新增,修改,删除凭证时对科目余额的改变加锁
VOCHER_LOCK = threading.RLock()
# 全局标签模型,用于多重继承方式添加到模型
# 金额的默认币别,人民币在系统中的id
CNY = 7


class Globcncw_tag_Model(models.AbstractModel):
    '''全局标签模型,用于多重继承方式添加到模型'''
    _name = "cncw.glob_tag_model"
    _description = '全局标签模型'
    is_current = fields.Boolean(string="当前机构", compute="_is_current")
    glob_tag = fields.Many2many('cncw.glob_tag',
                                string='全局标签',
                                index=True)

class GlobCncwTagClass(models.Model):
    '''全局标签类别'''
    _name = 'cncw.glob_tag_class'
    _description = '全局标签类别'
    number = fields.Char(string='全局标签类别编码')
    name = fields.Char(string='全局标签类别名称', required=True)
    summary = fields.Char(string='使用范围和简介')
    _sql_constraints = [('cncw_tagclass_number_unique', 'unique(number)',
                         '全局标签类别编码重复了!'),
                        ('cncw_tagclass_name_unique', 'unique(name)',
                         '全局标签类别名称重复了!')]

class GlobTag(models.Model):
    '''模块全局标签'''
    _name = 'cncw.glob_tag'
    _description = '模块全局标签'
    name = fields.Char(string='全局标签名称', required=True)
    glob_tag_class = fields.Many2one('cncw.glob_tag_class',
                                     string='全局标签类别',
                                     index=True,
                                     ondelete='restrict')
    summary = fields.Char(string='使用范围')
    js_code = fields.Text(string='js代码')
    python_code = fields.Text(string='python代码')
    sql_code = fields.Text(string='sql代码')
    str_code = fields.Text(string='字符串')
    application = fields.Html(string='使用说明')
    _sql_constraints = [('cncw_glob_tag_name_unique', 'unique(name)',
                         '模块全局标签重复了!')]

##++++++++++++++++++++++++++++++++++++++++++++++
class CncwOrg(models.Model, Globcncw_tag_Model):
    '''中国会计核算机构'''
    _name = 'cncw.org'
    _description = '会计核算机构'
    number = fields.Char(string='核算机构编码')
    name = fields.Char(string='核算机构名称', required=True)
    accounts = fields.One2many('cncw.account',
                               'cncw_org',
                               string='科目')
    user_ids = fields.Many2many('res.users', string='用户组')
    _sql_constraints = [('cncw_org_number_unique', 'unique(number)',
                         '核算机构编码重复了!'),
                        ('cncw_org_name_unique', 'unique(name)',
                         '核算机构名称重复了!')]

    def _is_current(self):
        '''是否当前机构'''
        self.is_current = True

    def toggle(self):
        pass

    def unlink(self):
        '''删除'''
        for mySelf in self:
            if mySelf.id == 1:
                raise exceptions.ValidationError("不能删除默认机构，可以修改")
        rl_bool = super(CncwOrg, self).unlink()
        return rl_bool
