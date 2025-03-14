# -*- encoding: utf-8 -*-

import time
from odoo import models, api, fields, _
from odoo.addons import base_cw
from odoo import tools
#import odoo.addons.decimal_precision as dp

class AccountReceivedReport(models.Model):
    _name = "account.received.report"
    _description = '到款查询'
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

    partner_id = fields.Many2one('res.partner', '客户')
    date = fields.Date('开单日期')
    done_date = fields.Date('收款日期')
    partner_code = fields.Char('客户编码')
    partner_name = fields.Char('客户名称')

    company_id = fields.Many2one('res.company', '结算公司')
    receive_type = fields.Selection([('A', '一般收款'),
                                     ('B', '预收款')], '收款性质')
    payment_mode_id = fields.Many2one('payment.mode', '收款方式')
    currency_id = fields.Many2one('res.currency', '收款币别')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', aggregator="avg")
    amount = fields.Float('原币总金额',  digits='Product Price', aggregator="sum")
    local_amount = fields.Float('人民币总金额',  digits='Product Price', aggregator="sum")
    receive_bank_id = fields.Many2one('res.partner.bank', '到款银行')
    notice_bank_id = fields.Many2one('res.partner.bank', '通知银行')
    department_id = fields.Many2one('hr.department', '部门')
    note = fields.Char('备注')
    # team_id = fields.Many2one('crm.team', '销售团队', required=False,)
    account_team_id = fields.Many2one('crm.team', '销售团队', required=False,)

    receive_category_id = fields.Many2one('account.receive.category', '收款类别', ondelete="restrict")
    read_users_ids = fields.Many2many('res.users', compute="_compute_read_users_ids", string='读取用户',
                                      search='_search_user_id')

    def _search_user_id(self, operation, value):
        order = []
        if not value:
            return [('id', '=', False)]
        list = []
        if list:
            self._cr.execute("""select id from account_received_report where partner_id in %s""", (tuple(list),))
            order = filter(None, map(lambda x: x[0], self._cr.fetchall()))
        return [('id', 'in', order)]

    def init(self):
        tools.drop_view_if_exists(self._cr, 'account_received_report')
        self._cr.execute(""" create or replace view account_received_report as (
                       select a.id,b.partner_id,b.create_date date,b.date done_date,c.code as partner_code,c.name as partner_name,
                               b.receive_type,b.payment_mode_id,b.currency_id,b.exchange_rate,b.department_id,
                               a.amount, a.local_amount,a.receive_category_id,
                               a.receive_bank_id, a.notice_bank_id, a.note, b.team_id as account_team_id
                          from account_receive_line a 
                          left join account_receive b on a.master_id = b.id
                          left join res_partner c on b.partner_id = c.id
                          where b.state='done' and a.advance_id is null
                )
        """)

