# -*- encoding: utf-8 -*-
import time

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round, float_is_zero

PAY_TYPE = [
    ('A', '付款'),
    ('C', '预付款'),
]

RECEIVE_NATURE = [
    ('A', '货款'),
    ('B', '预收款'),
    ('C', '预付款'),
]

EXPIRY_TYPE = [
    ('A', '正常'),
    ('B', '部分逾期'),
    ('C', '全部逾期'),
]


class AccountPay(models.Model):
    _name = 'account.pay'
    _description = '付款单'
    _order = 'name desc'

    def _compute_invoice_line_ids(self):
        invoice_line_ids = self.env['cncw.invoice.move.line']
        for line in [r for r in self.offset_line_ids if r.amount > 0 and r.invoice_id]:
            for invoice_line in line.invoice_id.invoice_line_ids:
                invoice_line_ids |= invoice_line
        self.invoice_line_ids = invoice_line_ids

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_payment_amount(self):
        for record in self:
            record.payment_amount = sum(
                record.line_ids.filtered(lambda x: x.payment_category_id.is_payment).mapped('amount'))
            record.local_payment_amount = record.currency_id.round(
                record.payment_amount * record.exchange_rate) if record.currency_id else 0
            record.payment_amount_chinese = base_cw.public.get_chinese_money(record.local_payment_amount)

    @api.depends('offset_line_ids', 'offset_line_ids.amount', 'offset_line_ids.dc_type')
    def _compute_offset_amount(self):
        for record in self:
            precision = self.env['decimal.precision'].precision_get('Account')
            offset_amount = float_round(sum([x.amount for x in record.offset_line_ids if
                                             x.invoice_id and x.invoice_id.move_type in ('in_invoice', 'out_refund')])
                                        , precision_digits=precision)  # 应收帐款,
            if not offset_amount:
                offset_amount = float_round(sum([x.amount for x in record.offset_line_ids if
                                                 x.invoice_id and x.invoice_id.move_type in ('out_invoice', 'in_refund')])
                                            , precision_digits=precision)  # 应收帐款,
            record.offset_amount = offset_amount
            record.local_offset_amount = float_round(offset_amount * record.exchange_rate, precision_digits=precision)

    @api.depends('offset_line_ids.amount', 'offset_line_ids.dc_type', 'line_ids.amount', 'line_ids.dc_type')
    def _compute_diff_amount(self):
        for record in self:
            debit = sum(x.amount for x in record.offset_line_ids if x.dc_type == 'D')
            debit += sum(x.amount for x in record.line_ids if x.dc_type == 'D')
            credit = sum(x.amount for x in record.offset_line_ids if x.dc_type == 'C')
            credit += sum(x.amount for x in record.line_ids if x.dc_type == 'C')
            record.diff_amount = credit - debit

    name = fields.Char('付款单号', default=False)
    partner_id = fields.Many2one('res.partner', '供应商', ondelete="restrict")
    date = fields.Date('付款日期', default=fields.Date.context_today)

    currency_id = fields.Many2one('res.currency', '币别', copy=False, ondelete="restrict")
    exchange_rate = fields.Float(related='partner_id.partner_currency_id.rate', string='汇率', store=True,
                                 digits='Exchange Rate',
                                 default=1.0)
    tax_id = fields.Many2one('account.tax', '税别', ondelete="restrict")
    payment_type = fields.Selection([('A', '一般付款'),
                                     ('B', '预付款')], '付款性质', default='A')

    team_id = fields.Many2one('crm.team', '付款抬头', ondelete="restrict")
    receive_bank_ids = fields.Many2many('res.partner.bank', related='team_id.receive_bank_ids', string='收款行',
                                        readonly=True)
    notice_bank_ids = fields.Many2many('res.partner.bank', related='team_id.notice_bank_ids', string='通知行',
                                       readonly=True)
    expiry_type = fields.Selection(EXPIRY_TYPE, '逾期收款', default='A')
    payment_mode_id = fields.Many2one('payment.mode', '付款方式', ondelete="restrict")

    to_blank_id = fields.Many2one('res.partner.bank', '到款银行', ondelete="restrict")
    notice_bank_id = fields.Many2one('res.partner.bank', '通知银行', ondelete="restrict")

    note = fields.Text('说明', )
    supplier_name = fields.Char('收款人全称', )
    bank_name = fields.Char('开户银行', )
    bank_number = fields.Char('银行帐号', )
    payment_term_id = fields.Many2one('account.payment.term', '付款条件', ondelete="restrict")
    stock_incoterms_id = fields.Many2one('stock.incoterms', '价格条款', ondelete="restrict")

    offset_amount = fields.Float('冲销总额', compute="_compute_offset_amount", store=True,
                                 digits='Product Price', )
    payment_amount = fields.Float('付款总额', digits='Product Price', compute='_compute_payment_amount',
                                  store=True)
    diff_amount = fields.Float('差异金额', digits='Product Price', compute='_compute_diff_amount', store=True)
    payment_amount_chinese = fields.Char('本币付款总额大写', compute="_compute_payment_amount", store=True)
    local_payment_amount = fields.Float('本币付款总额', digits='Product Price', readonly=True,
                                        compute='_compute_payment_amount',
                                        store=True)
    local_offset_amount = fields.Float('本币冲销总额', digits='Product Price', readonly=True,
                                       compute="_compute_offset_amount",
                                       store=True, )

    confirm_date = fields.Date('确认日')
    confirm_user_id = fields.Many2one('res.users', '确认人')
    done_date = fields.Date('完成日')
    done_user_id = fields.Many2one('res.users', '完成人')
    move_id = fields.Many2one('cncw.invoice.move', '传票编号', readonly=True)

    agreement_no = fields.Char('合同号', )
    agreement_payment_terms = fields.Char('合同付款条款', )
    attachment_ids = fields.Many2many('ir.attachment', 'pay_attachment_rel', 'pay_id', 'attachment_id', '附件')
    invoice_line_ids = fields.Many2many('cncw.invoice.move.line', compute='_compute_invoice_line_ids', string='成本分配')
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '已确认'),
                              ('audited', '已审核'),
                              ('approved', '已核准'),
                              ('done', '已付款'),
                              ('cancel', '取消'),
                              ], '单据状态',
                             default='draft')
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True,
                                 default=lambda self: self.env.company)

    payment_confirm_date = fields.Date('付款确认日')
    payment_confirm_user_id = fields.Many2one('res.users', '确认人')
    offset_line_ids = fields.One2many('account.pay.offset.line', 'master_id', '冲销明细')
    line_ids = fields.One2many('account.pay.line', 'master_id', '付款明细')
    # 预付款金额
    advance_payment_apply_id = fields.Many2one('advance.payment.apply', string='预付款申请',
                                               domain="[('wait_amount_payment', '>', 0)]",
                                               readonly=True,
                                               # states={'draft': [('readonly', False)]}
                                               )

    advance_amount = fields.Float('本币待付款金额', digits='Product Price', store=True,
                                  related='advance_payment_apply_id.wait_amount_payment')
    lock_amount_payment = fields.Float('本币付款中金额', digits='Product Price', store=True,
                                       related='advance_payment_apply_id.lock_amount_payment')

    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals)
        return super(AccountPay, self).create(vals)

    def unlink(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('提示!只能删除草稿或取消状态的资料!'))
        res = super(AccountPay, self).unlink()
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.currency_id = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.id or False
            self.exchange_rate = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.rate
            self.tax_id = self.partner_id.account_tax_id and self.partner_id.account_tax_id.id or False

    # 申请确认
    @api.onchange('exchange_rate')
    def onchange_exchange_rate(self):
        if self.exchange_rate:
            for line in self.line_ids:
                line.local_amount = line.amount * self.exchange_rate

    @api.model
    def data_check(self):
        if len(self.line_ids) == 0.0 and len(self.offset_line_ids) == 0:
            # 如应付冲应收 时明细全部在offset_line_ids
            raise UserError(_('提示!付款明细不可为空!'))
        for line in self.line_ids:
            if line.amount == 0.0:
                raise UserError(_('提示!付款金额不可为0!'))
        if self.payment_type == 'A':
            if len(self.offset_line_ids) == 0 and not float_is_zero(self.diff_amount,
                                                                    precision_rounding=self.currency_id.rounding):
                raise  UserError(_('提示!冲销明细不可为空!'))
            if not float_is_zero(self.diff_amount, precision_rounding=self.currency_id.rounding):
                raise  UserError(_('提示!付款总额与冲销总额不一致不可以确认!'))

    def action_confirm(self):
        self.ensure_one()
        self.data_check()
        state = 'confirmed'
        self.write(dict(confirm_user_id=self._uid,
                        confirm_date=fields.Date.context_today(self),
                        state=state))

    # 取消申请
    def action_cancel_confirm(self):
        self.ensure_one()
        state = 'draft'
        self.write(dict(confirm_user_id=False,
                        confirm_date=None,
                        state=state))
        for line in self.line_ids:
            line.update_prepaid()

    @api.model
    def offset_line_data_check(self):
        for x in self.offset_line_ids.filtered('invoice_id'):
            if x.invoice_id.remaining_amount < x.amount:
                raise UserError(_('项次:%s [本次冲帐金额] 不可以大于 [发票未冲余额]' % (x.sequence,)))

    # 付款确认
    def action_done(self):
        self.ensure_one()
        self.offset_line_data_check()
        # self.action_create_account_move()
        state = 'done'
        self.write(dict(done_user_id=self._uid,
                        done_date=fields.Date.context_today(self),
                        state=state))
        for line in self.line_ids:
            if self.payment_type == 'B' or (
                    self.payment_type == 'A' and line.account_id.ap_ar_type in (
                    '10', '11') and line.dc_type == 'D'):  # 预付帐款
                line.create_account_prepaid()
            line.update_prepaid()
        if self.invoice_line_ids:
            self.update_invoice()

    def action_cancel_done(self):
        """
        取消付款
        :return:
        """
        self.ensure_one()
        # 验证预付款是否已做冲帐，若做了冲帐则不可以取消确认
        for line in self.line_ids:
            if self.payment_type == 'B' or (
                    self.payment_type == 'A' and line.account_id.ap_ar_type in (
                    '10', '11') and line.dc_type == 'D'):  # 预付帐款
                prepaid_id = self.env['account.prepaid'].search([('res_id', '=', line.id)], limit=1)
                if prepaid_id:
                    if len(prepaid_id.pay_line_ids) > 0:
                        raise  UserError(_('提示!产生的预付款已有冲帐不可以取消确认!'))

        state = 'confirmed'
        self.write(dict(confirm_user_id=False,
                        confirm_date=None,
                        done_user_id=False,
                        done_date=None,
                        state=state))
        self._cr.commit()
        self.invalidate_cache()
        for line in self.line_ids:
            line.update_prepaid()
        self.update_invoice()
        # 删除出纳日记账
        cash_dialy_id = self.env['account.cash.dialy'].search([('pay_order_id', 'in', self.ids)])
        if cash_dialy_id:
            cash_dialy_id.unlink()

    def action_create_account_move(self):
        """
        产生传票
        :return:
        """
        self.ensure_one()
        self.account_check()
        pass  # 在做总时写此methon

    def action_cancel_account_move(self):
        """
        取消传票
        :return:
        """
        self.ensure_one()
        pass  # 在做总时写此methon

    def voucher_check(self):
        if self.diff_amount != 0.0:
            raise  UserError(_('提示!付款额 与冲销金额不等,请确认!'))
        pass

    def account_check(self):
        pass  # 会科检核在总帐模组中写

    @api.model
    def update_invoice(self):
        for line in self.offset_line_ids.filtered(lambda x: x.invoice_id):
            line.update_invoice_payment_amount()

    def action_auto_offset(self):
        """
        依付款金额自动冲销发票
        :return:
        """
        self.ensure_one()
        exists = self.offset_line_ids.mapped('invoice_id')
        domain = [('offset_state', '!=', 'A'), ('state', '=', 'open'), ('remaining_amount', '!=', 0.0)]
        if self._name == 'account.pay':
            domain += [('move_type', 'in', ('in_invoice', 'in_refund'))]
        elif self._name == 'account.receive':
            domain += [('move_type', 'in', ('out_invoice', 'out_refund'))]
        domain += [('partner_id', '=', self.partner_id.id)]
        if exists:
            domain += [('id', 'not in', exists.ids)]
        invoice_ids = self.env['cncw.invoice.move'].search(domain, order='date_invoice')
        total_amount = abs(self.diff_amount) if self.payment_amount == 0.0 else self.diff_amount
        for invoice_id in invoice_ids:
            if total_amount <= 0.0: break
            this_amount = invoice_id.remaining_amount if float_compare(invoice_id.remaining_amount, total_amount,
                                                                       precision_rounding=0.00001) <= 0 else total_amount
            item = dict(master_id=self.id,
                        invoice_id=invoice_id.id,
                        invoice_no=invoice_id.invoice_no,
                        date_invoice=invoice_id.date_invoice,
                        date_due=invoice_id.invoice_date_due,
                        amount=this_amount,
                        account_id=invoice_id.account1_id and invoice_id.account1_id.id or False)
            if invoice_id.account_id.sub_account_type == 'has':
                sub_account_lines_data = []
                # for line2 in invoice_id.account_id.subaccount_category_ids:
                line_data = {
                    'category_id': self.partner_id.subaccount_category_id.id,
                    'sub_account_id': self.partner_id and self.partner_id.id or False
                }
                sub_account_lines_data = [(0, 0, line_data)]
                item.update(dict(
                    sub_account_id=self.partner_id and self.partner_id.id or False,
                    sub_account_lines=sub_account_lines_data
                ))
            self.env[self._name + '.offset.line'].create(item)
            total_amount = total_amount - invoice_id.remaining_amount

    def action_open_account_pay_add_invoice_wizard(self):
        """
        打开 选发票 明细 窗口
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       name=self.name,
                       active_id=self.id,
                       )
        self.env.context = context
        self._cr.execute("delete from account_pay_add_invoice_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.pay.add.invoice.wizard'].create(dict(active_id=self.id))
        return wizard_id.wizard_view()

    def action_open_account_pay_offset_receive_add_invoice_wizard(self):
        """
        打开 应收冲应付 (拿销售的发票 来冲 采购的发票)
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       name=self.name,
                       active_id=self.id,
                       is_receive_pay_offset=True,
                       )
        self.env.context = context
        self._cr.execute("delete from account_pay_add_invoice_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.pay.add.invoice.wizard'].create(dict(active_id=self.id))
        return wizard_id.wizard_view()

    def action_open_account_pay_prepaid_select_wizard(self):
        """
        打开 选 预付使用 明细 窗口
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       name=self.name,
                       active_id=self.id, )
        self.env.context = context
        self._cr.execute("delete from account_pay_prepaid_select_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.pay.prepaid.select.wizard'].create(dict(active_id=self.id))
        return wizard_id.wizard_view()


class AccountPayOffsetLine(models.Model):
    _name = 'account.pay.offset.line'
    _description = '付款单冲销明细'

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.pay.offset.line",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_account_pay_offset_line_form2').id,
            "res_id": self.id,
            "name": "编辑辅助核算",
            "target": 'new'
        }

    @api.depends('date_due')
    def _compute_overdue_days(self):
        for record in self:
            record.overdue_days = 0
            if record.date_due:
                record.overdue_days = base_cw.public.get_days_between_date(time.strftime("%Y-%m-%d"),
                                                                           fields.Datetime.to_string(record.date_due))

    @api.onchange('amount')
    def _onchange_local_amount(self):
        for record in self:
            if record.master_id and record.master_id.currency_id:
                record.local_amount = record.master_id.currency_id.round(record.amount * record.master_id.exchange_rate)

    @api.depends('amount', 'invoice_amount')
    def _compute_remaining_amount(self):
        for record in self:
            remaining_amount = record.invoice_amount - record.amount
            if remaining_amount < 0:
                remaining_amount = 0
            record.remaining_amount = remaining_amount

    master_id = fields.Many2one('account.pay', '付款单', ondelete="cascade")
    sequence = fields.Integer('项次', default=1)
    invoice_id = fields.Many2one('cncw.invoice.move', '发票号码',
                                 domain=[('move_type', 'in', ('in_invoice', 'in_refund'))])
    note = fields.Text('备注')
    expense_category_id = fields.Many2one('account.expense.category', '费用类别', )
    invoice_no = fields.Char('发票号码', help='人工输入')
    date_invoice = fields.Date('发票日期')
    date_due = fields.Date(string='应收款日期')
    overdue_days = fields.Integer(string='逾期天数', compute='_compute_overdue_days', copy=False)
    invoice_amount = fields.Float('发票金额', digits='Product Price',
                                  related='invoice_id.remaining_amount', readonly=True, )
    amount = fields.Float('本次冲帐金额', digits='Product Price', )
    account_id = fields.Many2one('cncw.account', '会科')
    sub_account_id = fields.Many2one('res.partner', '辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_pay_offset_line_id')
    sub_account_lines_str = fields.Char(string='会计辅助核算', compute='compute_sub_account_lines_str')

    def compute_sub_account_lines_str(self):
        for record in self:
            sub_account_lines_str = ''
            for line in record.sub_account_lines.filtered(lambda r: r.sub_account_id):
                sub_account_lines_str += ' | '+line.sub_account_id.name
                if line.category_id.code == 'cash_flow':
                    record.sub_account_id = line.sub_account_id
            record.sub_account_lines_str = sub_account_lines_str

    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    remaining_amount = fields.Float('剩余金额', digits='Product Price',
                                    compute='_compute_remaining_amount', store=True)
    total_offset_amount = fields.Float('累计冲销金额', related='invoice_id.payment_amount',
                                       digits='Product Price', readonly=True)
    offset_state = fields.Selection([('N', '未冲销'),
                                     ('P', '部分冲销'),
                                     ('A', '已完全冲销')],
                                    '冲销状态', related='invoice_id.offset_state', readonly=True)
    product_id = fields.Many2one('product.product', '付款货品')
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
    product_uom = fields.Many2one('uom.uom', related='product_id.uom_id', string='单位')
    price_unit = fields.Float('单价', digits='Product Price', )
    product_qty = fields.Float('数量', digits='Product Price', )
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '已确认'),
                              ('audited', '已审核'),
                              ('approved', '已核准'),
                              ('done', '已付款'),
                              ('cancel', '取消'),
                              ], '单据状态',
                             related='master_id.state', readonly=True, )

    local_amount = fields.Float('本币金额', digits='Product Price', store=True)
    note = fields.Text('备注')
    _sql_constraints = [('invoice_unique', 'unique (invoice_id,master_id)', '同张付款单不可重复冲销同一笔发票!'), ]

    @api.constrains('invoice_no', 'amount', 'date_invoice', 'date_due')
    def _check_qty_amount(self):
        for record in self:
            if record.amount == 0.0 and record.master_id.payment_type == 'A':
                raise UserError(_('错误提示!本次冲帐金额不可为0'))
            if not record.date_invoice:
                raise UserError(_('错误提示!发票日期不可为空'))
            if not record.date_due:
                raise UserError(_('错误提示!付款日期不可为空'))

    def create(self, vals):
        base_cw.public.generate_sequence(self, vals)
        return super(AccountPayOffsetLine, self).create(vals)

    @api.onchange('expense_category_id')
    def onchange_expense_category_id(self):
        for record in self:
            if record.expense_category_id:
                record.account_id = record.expense_category_id.account_id and record.expense_category_id.account_id.id or False
                record.sub_account_id = record.master_id.partner_id and record.master_id.partner_id.id or False
                record.dc_type = record.expense_category_id.dc_type

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        for record in self:
            if record.invoice_id:
                record.invoice_no = record.invoice_id.invoice_no or ''
                record.date_invoice = record.invoice_id.date_invoice
                record.date_due = record.invoice_id.invoice_date_due
                record.amount = record.invoice_id.remaining_amount
            else:
                res = dict(invoice_no='',
                           date_invoice=None,
                           date_due=None,
                           amount=0.0)
                record.update(res)

    @api.model
    def update_invoice_payment_amount(self):
        """
        更新发票冲销
        :return:
        """
        for record in self:
            if record.invoice_id:
                record.invoice_id.update_invoice_payment_amount(model_name=record._name)


class AccountPayLine(models.Model):
    _name = 'account.pay.line'
    _description = '付款单明细'

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.pay.line",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_account_pay_line_form2').id,
            "res_id": self.id,
            "domain":[("account_pay_line_id",'!=',False)],
            "context": { "default_category_id": self.account_id.subaccount_category_id.id,"default_sub_account_id":self.account_id.id},
            "name": "编辑辅助核算",
            "target": 'new'
        }

    @api.depends('master_id', 'sequence')
    def name_get(self):
        res = []
        for record in self:
            name = "%s - %s" % (record.master_id.name, record.sequence)
            res.append((record.id, name))
        return res

    master_id = fields.Many2one('account.pay', '付款单', ondelete="cascade")
    sequence = fields.Integer('项次', default=1)
    payment_category_id = fields.Many2one('account.payment.category', '付款类别', ondelete="restrict")
    account_id = fields.Many2one('cncw.account', '会科', ondelete="restrict")
    sub_account_id = fields.Many2one('res.partner', '辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_pay_line_id', string='辅助核算')

    sub_account_lines_str = fields.Char(string='会计辅助核算', compute='compute_sub_account_lines_str')

    @api.depends('sub_account_lines', 'sub_account_lines.sub_account_id')
    def compute_sub_account_lines_str(self):
        for record in self:
            sub_account_lines_str = ''
            for line in record.sub_account_lines.filtered(lambda r: r.sub_account_id):
                sub_account_lines_str += ' | '+line.sub_account_id.name
                if line.category_id.code == 'cash_flow':
                    record.sub_account_id = line.sub_account_id
            record.sub_account_lines_str = sub_account_lines_str

    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    amount = fields.Float('付款金额', digits='Product Price', )
    currency_id = fields.Many2one('res.currency', '币别', related='master_id.currency_id', readonly=True)
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', related='master_id.exchange_rate',
                                 readonly=True)
    local_amount = fields.Float('本币金额', digits='Product Price')
    prepaid_id = fields.Many2one('account.prepaid', '预付款单', ondelete="restrict")
    prepaid_amount = fields.Float('预付款余额', digits='Product Price', related='prepaid_id.remaining_amount',
                                  readonly=True, store=True)
    note = fields.Text('备注')

    def create(self, vals):
        base_cw.public.generate_sequence(self, vals)
        return super(AccountPayLine, self).create(vals)

    def unlink(self):
        for line in self:
            if line.master_id.payment_type == 'A':
                if line.prepaid_id:
                    line.prepaid_id.compute_remaining_amount()
        res = super(AccountPayLine, self).unlink()
        return res

    @api.onchange('amount')
    def _onchange_amount(self):
        for record in self:
            if record.master_id:
                record.local_amount = record.amount * record.master_id.exchange_rate

    @api.onchange('payment_category_id')
    def onchange_payment_category_id(self):
        for record in self:
            if record.payment_category_id and record.payment_category_id.account_setup == 'A':
                record.account_id = record.payment_category_id.account_id and record.payment_category_id.account_id.id or False
                record.dc_type = record.payment_category_id.account_id and record.payment_category_id.dc_type

    @api.model
    def create_account_prepaid(self):
        """
        创建 预付款单
        :return:
        or (
                        self.payment_type == 'A' and line.account_id.ap_ar_type == '10' and line.dc_type == 'D')
        """
        if self.master_id.state == 'done' and not self.prepaid_id and (self.master_id.payment_type == 'B' or (
                self.master_id.payment_type == 'A' and self.account_id.ap_ar_type in (
                '10', '11') and self.dc_type == 'D')):
            sub_account_lines_data = []
            for line2 in self.sub_account_lines:
                line_data = {'category_id': line2.category_id.id, 'sub_account_id': line2.sub_account_id.id}
                sub_account_lines_data.append((0, 0, line_data))
            item = dict(res_id=self.id,
                        name="New",
                        date=self.master_id.date,
                        partner_id=self.master_id.partner_id.id,
                        currency_id=self.master_id.currency_id.id,
                        exchange_rate=self.master_id.exchange_rate,
                        tax_rate=self.master_id.tax_id.amount,
                        amount=self.amount,
                        total_amount=self.amount,
                        paid_amount=0,
                        remaining_amount=self.amount,
                        lc_amount=self.local_amount,
                        lc_total_amount=self.local_amount,
                        lc_paid_amount=0,
                        lc_remaining_amount=self.local_amount,
                        dc_type=self.dc_type,
                        note=self.note,
                        account_id=self.account_id.id,
                        sub_account_id=self.sub_account_id.id,
                        sub_account_lines=sub_account_lines_data,
                        offset_state='N')
            self.env['account.prepaid'].create(item)

    @api.model
    def update_prepaid(self):
        """
        更新预付单信息
        :return:
        """
        if self.master_id.state in ('cancel', 'draft', 'confirmed') and (self.master_id.payment_type == 'B' or (
                self.master_id.payment_type == 'A' and self.account_id.ap_ar_type in (
                '10', '11') and self.dc_type == 'D')):
            self._cr.execute('delete from account_prepaid where res_id=%s' % (self.id,))
        if self.prepaid_id:
            self.prepaid_id.compute_remaining_amount()
