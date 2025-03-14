# -*- encoding: utf-8 -*-

import time
from odoo import models, api, fields, _
from odoo.addons import base_cw
from odoo import tools
#import odoo.addons.decimal_precision as dp
from . import account_payable_report
# import sys


class account_receivable_report(models.Model):
    _name = 'account.receivable.report'
    _description = '应收款查询'
    _auto = False

    def _compute_read_users_ids(self):
        list = []
        users_ids = self.env['res.users']
        if self.partner_id:
            list = base_cw.public.get_user_by_partner(self, self.partner_id.id)
        else:
            list = [self.env.user.id]
        for user in self.env['res.users'].search([('id', 'in', list)]):
            users_ids |= user
        self.read_users_ids = users_ids

    partner_code = fields.Char('客户编码')
    partner_id = fields.Many2one('res.partner', '客户名称')
    categ_id = fields.Many2one('product.category', '货品分类')
    partner_name = fields.Char('客户名称')
    overdue_amount = fields.Float('超期应收款',  digits='Product Price', aggregator="sum")
    overdue_days = fields.Float('超期天数', digits=(16, 0))
    payment_term_id = fields.Many2one('account.payment.term', string=u"付款条件")
    overdue_time_range = fields.Selection(account_payable_report.OVER_DATA_SELECTION, string='超期范围')
    # overdue_time_range = fields.Text('超期范围')
    payment_date = fields.Date('收款日期')
    overdue_type = fields.Text('到期类型')
    amount_total = fields.Float('开票金额',  digits='Product Price', aggregator="sum")
    invalid_amount = fields.Float('作废金额',  digits='Product Price', aggregator="sum")
    date_invoice = fields.Date('开票日期')
    invoice_no = fields.Char('发票号码',)
    invoice_count = fields.Integer('发票份数')
    currency_id = fields.Many2one('res.currency', '开票币别')
    date_due = fields.Date('应收款日期')
    payment_amount = fields.Float('收款金额',  digits='Product Price', aggregator="sum")
    remaining_amount = fields.Float('剩余应收款',  digits='Product Price', aggregator="sum")
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', aggregator="avg")
    payment_rate = fields.Float('收款比率', digits='Exchange Rate', aggregator="avg")
    no_overdue_amount = fields.Float('未超期应收款',  digits='Product Price', aggregator="sum")
    invoice_state = fields.Text('开票状态')
    name = fields.Char('开票单号')
    read_users_ids = fields.Many2many('res.users', compute="_compute_read_users_ids", string='读取用户',
                                      search='_search_user_id')

    def _search_user_id(self, operation, value):
        order = []
        if not value:
            return [('id', '=', False)]
        list = base_cw.public.get_user_by_partner(self, self.partner_id.id)
        if list:
            self._cr.execute("""select id from account_receivable_report where partner_id in %s""", (tuple(list),))
            order = filter(None, map(lambda x: x[0], self._cr.fetchall()))
        return [('id', 'in', order)]

    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_receivable_report')
        self._cr.execute("""create or replace view account_receivable_report as (
                select t1.id,t1.partner_id,t2.code as partner_code,t2.name partner_name,t1.categ_id,--t6.manager_id,,t3.user_id,t9.execution_user_id
                        t1.date_invoice,t8.invoice_no,t8.invoice_count,t8.currency_id,t1.invoice_date_due as date_due,t8.payment_term_id,
                        t1.amount_total,t1.invalid_amount,t1.payment_amount,t1.remaining_amount,t1.overdue_days,
                        (case when t1.overdue_days>0 then t1.remaining_amount else 0 end) overdue_amount,
                        (case when t1.overdue_days<=0 then t1.remaining_amount else 0 end) no_overdue_amount,
                        (case when t1.amount_total>0 then t1.payment_amount*100/t1.amount_total else 0 end) payment_rate,
                        (case when t1.remaining_amount=0 then '已全部收款' else '未全部收款' end) as invoice_state,--t5.department_id,
                        (case Ceiling((cast(COALESCE(t1.overdue_days,0) as float)/30))  --超期类型
                                              when 0 then '0'
                                      when 1 then '1'
                                      when 2 then '2'
                                      when 3 then '3'
                                              else (case when t1.overdue_days>90 and t1.overdue_days<181 then '4' else '5' end)
                          end) as overdue_time_range,
                         (case when Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))<0 then '已到期' --到期类型
                               else (case when Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))>1 and Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))<7 then '本周到期'
                                  else (case when Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))>7 and Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))<14 then '下周到期'
                                         else (case when Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))>14 and Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))<30 then '本月到期'
                                                else (case when Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))>30 and Ceiling((cast(COALESCE(t1.overdue_days,0) as float)-0))<60 then '下月到期' end)
                                                end)
                                         end)
                                end)
                           end) as overdue_type,
                          t1.payment_date,t8.name,t1.exchange_rate

                   from (select id,move_type,partner_id,date_invoice,invoice_date_due,amount_total,invalid_amount,total_invoice_amount-remaining_amount as payment_amount ,
                                  (case when remaining_amount<=0 then 0 else remaining_amount end) remaining_amount,
                                  (case when remaining_amount>0 then (case when extract(day from(age(now(),invoice_date_due)))<0 then 0 else cast(extract(day from(age(now(),invoice_date_due))) as integer) end) else 0 end) overdue_days,
                                  payment_date,exchange_rate,categ_id
                            from cncw_invoice_move
                            where state in ('open','paid')
                              and move_type in ('out_invoice')
                                                           ) t1 left join cncw_invoice_move t8 on t1.id=t8.id
                                                                left join res_partner t2 on t1.partner_id=t2.id

                                                                left join res_company as t7 on t7.id=t2.company_id
               )
        """)



