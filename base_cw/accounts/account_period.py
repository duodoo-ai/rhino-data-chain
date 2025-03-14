# -*- encoding: utf-8 -*-
#from __future__ import unicode_literals
import time
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


from dateutil.relativedelta import relativedelta

class account_fiscalyear(models.Model):
    _name = 'account.fiscalyear'
    _description = '会计年度'
    _order = "date_start"

    name = fields.Char('年度', default=False)
    date_start = fields.Date('开始日期')
    date_stop = fields.Date('结束日期')
    state = fields.Selection([('draft', '开启'), ('done', '关闭')], '状态', index=True, readonly=False, required=True,
                             default='draft')
    period_ids = fields.One2many('account.period', 'fiscalyear_id', '会计期间', required=False)
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True, # states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env.company)
    org_id =  fields.Many2one('cncw.org', string='财务机构')

    _sql_constraints = [('name_uniq', 'unique (name)', '会计年度不能重复建立!'), ]

    @api.onchange('name')
    def onchange_year(self):
        if self.name:
            self.date_start = datetime(int(self.name), 1, 1).strftime('%Y-%m-%d')
            self.date_stop = datetime(int(self.name), 12, 31).strftime('%Y-%m-%d')

    @api.constrains('date_start', 'date_stop')
    def _check_account_period_date(self):
        if self.date_start > self.date_stop:
            raise Warning(_('会计年度的结束日期不能小于开始日期!'))

    def data_prepared(self, periods, interval=1):
        for period in periods:
            if (period.date_stop - period.date_start).days > 60:
                period.period_type = 'quarter'
            else:
                period.period_type = 'period'

            ds = period.date_start
            dt_s = (ds - relativedelta(months=interval)).strftime('%Y-%m-%d')
            dt_e = (ds + relativedelta(months=interval)).strftime('%Y-%m-%d')
            if not period.special:
                period.pre_period_id = period.find_period(dt=dt_s, period_type=period.period_type)
                if period.pre_period_id and not period.pre_period_id.next_period_id:
                    period.pre_period_id.next_period_id = period.id
                period.next_period_id = period.find_period(dt=dt_e, period_type=period.period_type)


    def update_period(self):
        self.ensure_one()
        obj = self.env["account.period"]
        periods = obj.search(
            ['&', ('special', '=', False), '|', ('pre_period_id', '=', False), ('next_period_id', '=', False)])
        if periods:
            self.data_prepared(periods)

    def create_period(self):
        self.ensure_one()
        if not self.period_ids:
            self.create_periods()
        self.data_prepared(self.period_ids)
        self.update_period()
        return

    def create_periods(self):
        self.ensure_one()
        if self.period_ids:
            raise UserError(_('会计期间已经建立,不能重复建立!'))
        period_obj = self.env['account.period']
        ds = self.date_start
        while ds < self.date_stop:
            de = ds + relativedelta(months=1, days=-1)
            if de > self.date_stop:
                de = datetime.strptime(self.date_stop, '%Y-%m-%d')
            period_obj.create(dict(
                id=int(ds.strftime('%Y%m')),
                name=ds.strftime('%Y%m'),
                date_start=ds.strftime('%Y-%m-%d'),
                date_stop=de.strftime('%Y-%m-%d'),
                fiscalyear_id=self.id
            ))
            ds = ds + relativedelta(months=1)
        return True


PERIOD_SATE = [('open', '使用中'), ('close', '已关帐')]


class account_period(models.Model):
    _name = 'account.period'
    _description = '会计期间'
    _order = 'date_start'

    # id = fields.Integer('key',required=True)
    name = fields.Char('期间编码', required=True, default=False)
    date_start = fields.Date('开始日期')
    date_stop = fields.Date('结束日期')
    pre_period_id = fields.Many2one('account.period', string='前期', help='')
    next_period_id = fields.Many2one('account.period', string='下期', help='')
    period_type = fields.Selection([('period', '月'), ('quarter', '季')], string='period type', help='')
    special = fields.Boolean('特殊期别', default=False)
    fiscalyear_id = fields.Many2one('account.fiscalyear', '所在年度', required=False, ondelete="cascade")
    state = fields.Selection(PERIOD_SATE, '状态', index=True,
                             required=True, default='close', tracking=True)
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True, # states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env.company)
    stock_state = fields.Selection(PERIOD_SATE, '进销存模组', tracking=True,
                                   index=True, required=True, default='close')
    gl_state = fields.Selection(PERIOD_SATE, '财务模组', tracking=True,
                                index=True, readonly=False, required=True, default='close')
    mrp_state = fields.Selection(PERIOD_SATE, '生产模组', tracking=True,
                                 index=True, required=True, default='close')

    _sql_constraints = [('name_uniq', 'unique (name)', '会计期间不能重复建立!'), ]

    @api.constrains('date_start', 'date_stop')
    def _check_account_period_date(self):
        if self.date_start > self.date_stop:
            raise Warning(_('会计期间的结束日期不能小于开始日期!'))

    @api.onchange('state')
    def onchange_state(self):
        if self.state == 'close':
            self.stock_state = 'close'
            self.gl_state = 'close'
            self.mrp_state = 'close'
        else:
            self.stock_state = 'open'
            self.gl_state = 'open'
            self.mrp_state = 'open'

    @api.onchange('stock_state', 'gl_state', 'mrp_state')
    def onchange_three_state(self):
        if all((self.stock_state == 'close', self.gl_state == 'close', self.mrp_state == 'close')) \
                and self.state != 'close':
            self.state = 'close'
        if all((self.stock_state == 'open', self.gl_state == 'open', self.mrp_state == 'open')) \
                and self.state != 'open':
            self.state = 'open'

    @api.returns('self')
    def find_period(self, dt=None, period_type='period'):
        obj = self.env["account.period"]
        if not dt:
            dt = fields.Date.context_today(self)
        args = [('date_start', '<=', dt), ('date_stop', '>=', dt), ('period_type', '=', period_type)]
        args = args + [('special', '=', False)]

        if self.env.context.get('company_id', False):
            args.append(('company_id', '=', self.env.context['company_id']))
        else:
            company_id = self.env.user.company_id.id
            args.append(('company_id', '=', company_id))
        result = obj.search(args, limit=1)
        return result

    @api.model
    def period_state_check(self, model_name, date=None, belongs_to_module=None):
        period = self.find_period(dt=date)
        if not period:
            raise UserError(_('请建立期别!'))
        else:
            model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            if model:
                if model.belongs_to_module == 'stock':
                    if period.stock_state == 'close':
                        raise UserError(_('库存组模已关帐,不可修改库存单据,请与财务联系!'))
                elif model.belongs_to_module == 'mrp':
                    if period.mrp_state == 'close':
                        raise UserError(_('生产组模已关帐,不可修改库存单据,请与财务联系!'))
                elif model.belongs_to_module == 'gl':
                    if period.gl_state == 'close':
                        raise UserError(_('总帐组模已关帐,不可修改库存单据,请与财务联系!'))
                elif model.belongs_to_module == 'hr':
                    if period.hr_state == 'close':
                        raise UserError(_('人力资源组模已关帐,不可修改库存单据,请与财务联系!'))
                else:
                    pass

    @api.model
    def next(self, period_id, step=1):
        '''
        计算当前会计期间的下一个会计期间
        :param period_id:
        :param step:
        :return:
        '''
        periods = self.search([('date_start', '>', period_id.date_start), ('company_id', '=', period_id.company_id.id)])
        if len(periods) >= step:
            return periods[step - 1]
        return False

    @api.model
    def previous(self, period_id, step=1):
        '''
        计算当前会计期间的下一个会计期间
        :param period_id:
        :param step:
        :return:
        '''
        periods = self.search([('date_stop', '<=', period_id.date_start), ('company_id', '=', period_id.company_id.id)])
        if len(periods) >= step:
            return sorted(periods, key=lambda x: x.date_stop, reverse=1)[step - 1]
        return False

    @api.model
    def find(self, dt=None):
        '''
        查找指定时间的会计期间
        :param dt: 如果不指定则为当天
        :return:
        '''
        period = False
        if not dt:
            dt = fields.Date.context_today(self)
        domain = [('date_start', '<=', dt), ('date_stop', '>=', dt),
                  ('company_id', '=', self.context.get('company_id', self.env.user.company_id.id))]
        periods = self.search(domain)
        if periods:
            period = periods[0]
        return period

    def action_open(self):
        '''
        将会计期间返回开启状态
        :return:
        '''
        for period in self:
            if period.fiscalyear_id.state == 'close':
                raise UserError(_('会计年度已关闭,不能返回开启状态!'))
            period.state = 'open'
            period.onchange_state()
            # self.invalidate_cache()
        return True

    def action_close(self):
        '''
        关闭指定的会计期间
        :return:
        '''
        for period in self:
            if period.state == 'close' or period.fiscalyear_id.state == 'close':
                raise UserError(_('会计期间或会计年度已关闭,不能重复关闭!'))
            period.state = 'close'
            period.onchange_state()
        return True


