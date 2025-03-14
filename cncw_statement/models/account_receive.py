# -*- encoding: utf-8 -*-
import time

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round, float_is_zero

RECEIVE_TYPE = [
    ('A', '一般收款'),
    ('C', '预收款'),
]

BALANCE_NATURE = [
    ('A', '质保金/押金'),
    ('B', '货款'),
    ('C', '模具费'),
    ('D', '小数点误差'),
]

EXPIRY_TYPE = [
    ('A', '正常'),
    ('B', '部分逾期'),
    ('C', '全部逾期'),
]


class account_receive(models.Model):
    _name = 'account.receive'
    _description = '收款单'
    _order = 'name desc'

    def _compute_invoice_line_ids(self):
        for record in self:
            invoice_line_ids = self.env['cncw.invoice.move.line']
            for line in [r for r in record.offset_line_ids if r.amount > 0 and r.invoice_id]:
                for invoice_line in line.invoice_id.invoice_line_ids:
                    invoice_line_ids |= invoice_line
                    record.invoice_line_ids = invoice_line_ids

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_receive_amount(self):
        for record in self:
            record.receive_amount = sum(
                record.line_ids.filtered(lambda x: x.receive_category_id.is_receive).mapped('amount'))
            record.local_receive_amount = record.currency_id.round(
                record.receive_amount * record.exchange_rate) if record.currency_id else 0
            record.receive_amount_chinese = base_cw.public.get_chinese_money(record.local_receive_amount)

    @api.depends('offset_line_ids', 'offset_line_ids.amount', 'offset_line_ids.dc_type')
    def _compute_offset_amount(self):
        for record in self:
            precision = self.env['decimal.precision'].precision_get('Account')
            offset_amount = float_round(sum([x.amount for x in record.offset_line_ids if
                                             x.invoice_id and x.invoice_id.move_type in ('out_invoice', 'in_refund')])
                                        , precision_digits=precision)  # 应收帐款,
            if not offset_amount:
                offset_amount = float_round(sum([x.amount for x in record.offset_line_ids if
                                                 x.invoice_id and x.invoice_id.move_type in ('in_invoice', 'out_refund')])
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

    # 取得部门
    @api.depends('user_id')
    def _compute_department(self):
        for record in self:
            record.department_id = record.user_id.department_id

    name = fields.Char('收款单号', default=False)
    partner_id = fields.Many2one('res.partner', '客户编号', ondelete="restrict")
    user_id = fields.Many2one('res.users', '申请人', required=False, default=lambda self: self.env.user,
                              ondelete="restrict")
    department_id = fields.Many2one('hr.department', '申请部门',
                                    compute='_compute_department', store=True)
    date = fields.Date('收款日期', default=fields.Date.context_today)

    currency_id = fields.Many2one(related='partner_id.partner_currency_id', string='币别', copy=False, store=True,
                                  ondelete="restrict")
    exchange_rate = fields.Float(related='partner_id.partner_currency_id.rate', string='汇率', store=True,
                                 digits='Exchange Rate',
                                 default=1.0)
    tax_id = fields.Many2one(related='partner_id.account_tax_id', string='税别', store=True)
    receive_type = fields.Selection([('A', '一般收款'),
                                     ('B', '预收款')], '收款性质', default='A')

    team_id = fields.Many2one('crm.team', string='销售团队', store=True, ondelete="restrict")
    receive_bank_ids = fields.Many2many('res.partner.bank', related='team_id.receive_bank_ids', string='收款行',
                                        readonly=True)
    notice_bank_ids = fields.Many2many('res.partner.bank', related='team_id.notice_bank_ids', string='通知行',
                                       readonly=True)
    expiry_type = fields.Selection(EXPIRY_TYPE, '逾期收款', default='A')
    payment_mode_id = fields.Many2one('payment.mode', '收款方式', ondelete="restrict")

    note = fields.Text('说明', )
    supplier_name = fields.Char('收款人全称', )
    bank_name = fields.Char('开户银行', )
    bank_number = fields.Char('银行帐号', )
    payment_term_id = fields.Many2one('account.payment.term', '收款条件', ondelete="restrict")
    stock_incoterms_id = fields.Many2one('stock.incoterms', '价格条款', ondelete="restrict")

    offset_amount = fields.Float('冲销总额', compute="_compute_offset_amount", store=True, digits='Product Price', )
    receive_amount = fields.Float('收款总额', digits='Product Price', compute='_compute_receive_amount', store=True)
    diff_amount = fields.Float('差异金额', digits='Product Price', compute='_compute_diff_amount', store=True,
                               help='收款总额-冲销总额')
    receive_amount_chinese = fields.Char('本币收款总额大写', compute="_compute_receive_amount", store=True)
    local_receive_amount = fields.Float('本币收款总额', digits='Product Price', compute="_compute_receive_amount",
                                        store=True,
                                        readonly=True, )
    local_offset_amount = fields.Float('本币冲销总额', digits='Product Price', compute="_compute_offset_amount", store=True,
                                       readonly=True)

    confirm_date = fields.Date('确认日')
    confirm_user_id = fields.Many2one('res.users', '确认人', ondelete="restrict")
    done_date = fields.Date('完成日')
    done_user_id = fields.Many2one('res.users', '完成人', ondelete="restrict")
    move_id = fields.Many2one('cncw.invoice.move', '传票编号', readonly=True)

    agreement_no = fields.Char('合同号', )
    agreement_receive_terms = fields.Char('合同收款条款', )
    attachment_ids = fields.Many2many('ir.attachment', 'receive_attachment_rel', 'receive_id', 'attachment_id', '附件')
    invoice_line_ids = fields.Many2many('cncw.invoice.move.line', compute='_compute_invoice_line_ids', string='成本分配')
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '已确认'),
                              ('audited', '已审核'),
                              ('approved', '已核准'),
                              ('done', '已收款'),
                              ('cancel', '取消'),
                              ], '单据状态',
                             default='draft')
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True,
                                 default=lambda self: self.env.company)
    offset_line_ids = fields.One2many('account.receive.offset.line', 'master_id', '冲销明细')
    line_ids = fields.One2many('account.receive.line', 'master_id', '收款明细')
    # 预收款金额
    advance_receive_apply_id = fields.Many2one('advance.receive.apply', string='预收款申请',
                                               domain="[('wait_amount_receive', '>', 0)]",
                                               readonly=True,
                                               # states={'draft': [('readonly', False)]}
                                               )

    advance_amount = fields.Float('本币待收款金额', digits='Product Price', store=True,
                                  related='advance_receive_apply_id.wait_amount_receive')
    lock_amount_receive = fields.Float('本币收款中金额', digits='Product Price', store=True,
                                       related='advance_receive_apply_id.lock_amount_receive')

    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals)
        return super(account_receive, self).create(vals)

    def unlink(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('提示!只能删除草稿或取消状态的资料!'))
        res = super(account_receive, self).unlink()
        return res

    def copy(self, default=None):
        raise UserError(_('提示!收款单不提供复制功能！'))

    @api.onchange('currency_id')
    def onchange_currency_id(self):
        self.exchange_rate = self.currency_id.rate

    @api.onchange('exchange_rate')
    def onchange_exchange_rate(self):
        if self.exchange_rate:
            for line in self.line_ids:
                line.local_amount = self.currency_id.round(line.amount * self.exchange_rate)

    @api.model
    def data_check(self):
        if len(self.line_ids) < 1 and len(self.offset_line_ids) < 1:
            raise UserError(_('提示!收款明细不可为空!'))
        for line in self.line_ids:
            if line.amount == 0.0:
                raise UserError(_('提示!收款金额不可为0!'))
        if self.advance_receive_apply_id:
            advance_amount = sum(self.line_ids.mapped('local_amount'))
            if advance_amount > self.advance_amount:
                raise UserError(_('提示!收款金额不可大于预收款余额!'))
        if self.receive_type == 'A' and len(self.offset_line_ids) > 0 and float_is_zero(self.diff_amount,
                                                                                        precision_rounding=self.currency_id.rounding):
            if not float_is_zero(self.diff_amount, precision_rounding=self.currency_id.rounding):
                raise UserError(_('提示!收款总额与冲销总额不一致不可以确认!'))
        if self.receive_amount < 0.0:
            raise UserError(_('提示!收款总额小于0不可以确认!'))

    def action_confirm(self):
        self.ensure_one()
        self.data_check()
        state = 'confirmed'
        self.write(dict(confirm_user_id=self._uid,
                        confirm_date=fields.Date.context_today(self),
                        state=state))

    def action_cancel_confirm(self):
        for receive in self:
            state = 'draft'
            receive.write(dict(confirm_user_id=False,
                               confirm_date=None,
                               state=state))

    @api.model
    def offset_line_data_check(self):
        for x in self.offset_line_ids.filtered('invoice_id'):
            if x.invoice_id.remaining_amount < x.amount:
                raise UserError(_('项次:%s [本次冲帐金额] 不可以大于 [发票未冲余额]' % (x.sequence,)))

    def action_done(self):
        self.ensure_one()
        self.offset_line_data_check()
        self.action_create_account_move()
        state = 'done'
        self.write(dict(done_user_id=self._uid,
                        done_date=fields.Date.context_today(self),
                        state=state))
        for line in self.line_ids:
            if self.receive_type == 'B' or (self.receive_type == 'A'
                                            and line.account_id.ap_ar_type in (
                                                    '20', '21') and line.dc_type == 'C'):  # 预收帐款
                line.create_account_advance()
            line.update_advance()
        self.update_invoice()

    def action_cancel_done(self):
        """
        取消收款
        :return:
        """
        self.ensure_one()
        # 验证预收是否已有冲帐：
        for line in self.line_ids:
            if self.receive_type == 'B' or (
                    self.receive_type == 'A' and line.account_id.ap_ar_type in (
                    '20', '21') and line.dc_type == 'C'):  # 预收帐款
                advance_id = self.env['account.advance'].search([('res_id', '=', line.id)], limit=1)
                if advance_id:
                    if len(advance_id.received_line_ids) > 0:
                        raise UserError(_('提示!产生的预收款已有冲帐不可以取消确认!'))
        self.action_cancel_account_move()
        state = 'confirmed'
        self.write(dict(confirm_user_id=False,
                        confirm_date=None,
                        done_user_id=False,
                        done_date=None,
                        state=state))
        for line in self.line_ids:
            line.update_advance()
        self.update_invoice()
        # 删除出纳日记账
        cash_dialy_id = self.env['account.cash.dialy'].search([('receive_order_id', 'in', self.ids)])
        if cash_dialy_id:
            cash_dialy_id.unlink()

    def action_create_account_move(self):
        """
        产生传票
        :return:
        """
        self.ensure_one()
        self.account_check()
        pass  # 在做总时写此method

    def action_cancel_account_move(self):
        """
        取消传票
        :return:
        """
        self.ensure_one()
        pass  # 在做总时写此methon

    def voucher_check(self):
        if self.diff_amount != 0.0:
            raise UserError(_('提示!收款额与冲销金额不等,请确认!'))
        pass

    def account_check(self):
        pass  # 会科检核在总帐模组中写

    @api.model
    def update_invoice(self):
        for line in self.offset_line_ids.filtered(lambda x: x.invoice_id):
            line.update_invoice_payment_amount()

    def action_auto_offset(self):
        """
        依收款金额自动冲销发票
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
        total_amount = abs(self.diff_amount) if self.diff_amount < 0.0 else 0.0
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
                line_data = {'category_id': self.partner_id.subaccount_category_id.id,
                             'sub_account_id': self.partner_id.id or False}
                sub_account_lines_data = [(0, 0, line_data)]
                item.update(dict(
                    sub_account_id=self.partner_id and self.partner_id.id or False,
                    sub_account_lines=sub_account_lines_data
                ))
            self.env[self._name + '.offset.line'].create(item)
            total_amount = total_amount - invoice_id.remaining_amount

    def action_open_account_receive_add_invoice_wizard(self):
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

    def action_open_account_receive_offset_pay_add_invoice_wizard(self):
        """
        打开 应付冲应收 (拿采购的发票 来冲 销售的发票)
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

    def action_open_account_receive_advance_select_wizard(self):
        """
        打开 选 预收使用 明细 窗口
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
        self._cr.execute("delete from account_receive_advance_select_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.receive.advance.select.wizard'].create(dict(active_id=self.id))
        return wizard_id.wizard_view()


class account_receive_offset_line(models.Model):
    _name = 'account.receive.offset.line'
    _description = '收款单冲销明细'

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.receive.offset.line",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_account_receive_offset_line_form2').id,
            "res_id": self.id,
            "name": "编辑辅助核算",
            "target": 'new'
        }

    @api.depends('date_due')
    def _compute_overdue_days(self):
        for record in self:
            record.overdue_days = 0
            if record.date_due:
                days = base_cw.public.get_days_between_date(time.strftime("%Y-%m-%d"),
                                                            fields.Datetime.to_string(record.date_due))
                if days < 0:
                    record.overdue_days = abs(days)

    master_id = fields.Many2one('account.receive', '收款单', ondelete="cascade")
    sequence = fields.Integer('项次', default=1)
    invoice_id = fields.Many2one('cncw.invoice.move', '发票号码', domain=[('type', 'in', ('in_invoice', 'in_refund'))])
    note = fields.Text('备注')
    expense_category_id = fields.Many2one('account.expense.category', '费用类别')
    invoice_no = fields.Char('发票号码', related='invoice_id.invoice_no', store=True, readonly=True)
    date_invoice = fields.Date('发票日期', related='invoice_id.date_invoice', store=True, readonly=True)
    date_due = fields.Date(string='应收款日期', related='invoice_id.invoice_date_due', store=True, readonly=True)
    overdue_days = fields.Integer(string='逾期天数', compute='_compute_overdue_days', copy=False)
    invoice_amount = fields.Float('发票金额', digits='Account',
                                  related='invoice_id.total_invoice_amount', readonly=True)
    invoice_remaining_amount = fields.Float('发票未冲余额', digits='Account',
                                            related='invoice_id.remaining_amount', readonly=True)

    amount = fields.Float('本次冲帐金额', digits='Account')
    amount_tax = fields.Float('本次冲帐税额', digits='Account')
    adjust_amount = fields.Float('调整金额', digits='Account')
    account_id = fields.Many2one('cncw.account', '会计科目')
    sub_account_id = fields.Many2one('res.partner', '辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_pay_receive_line_id')
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

    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='C')
    remaining_amount = fields.Float('剩余金额', digits='Account',
                                    compute='_compute_remaining_amount', store=True)
    total_offset_amount = fields.Float('累计冲销金额', related='invoice_id.payment_amount',
                                       digits='Account', readonly=True)

    product_id = fields.Many2one('product.product', '收款货品')
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True)
    product_uom = fields.Many2one('uom.uom', related='product_id.uom_id', string='单位', readonly=True, )
    price_unit = fields.Float('单价', digits='Product Price')
    product_qty = fields.Float('数量', digits='Product Price')

    offset_state = fields.Selection([('N', '未冲销'),
                                     ('P', '部分冲销'),
                                     ('A', '已完全冲销')],
                                    '冲销状态', related='master_id.state', readonly=True)
    local_amount = fields.Float('本币金额', digits='Account', store=True)
    local_amount_tax = fields.Float('本币税额', digits='Account')
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '已确认'),
                              ('audited', '已审核'),
                              ('approved', '已核准'),
                              ('done', '已收款'),
                              ('cancel', '取消'),
                              ], '单据状态', related='master_id.state', readonly=True)

    @api.constrains('invoice_no', 'amount', 'date_invoice', 'date_due')
    def _check_qty_amount(self):
        for record in self:
            if record.amount == 0.0 and record.master_id.receive_type == 'A':
                raise UserError(_('错误提示!本次冲帐金额不可为0!'))
            if not record.date_invoice:
                raise UserError(_('错误提示!发票日期不可为空!'))
            if not record.date_due:
                raise UserError(_('错误提示!应收款日期不可为空!'))
            if record.remaining_amount < 0:
                raise UserError(_('错误提示!本次冲帐金额不可大于发票未冲余额!'))

    def create(self, vals):
        base_cw.public.generate_sequence(self, vals)
        return super(account_receive_offset_line, self).create(vals)

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.invoice_no = self.invoice_id.invoice_no or ''
            self.date_invoice = self.invoice_id.date_invoice
            self.date_due = self.invoice_id.invoice_date_due

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.invoice_no = self.invoice_id.invoice_no or ''
            self.account_id = self.invoice_id.account_id and self.invoice_id.account_id.id or False
            self.date_invoice = self.invoice_id.date_invoice
            self.date_due = self.invoice_id.invoice_date_due
            self.amount = self.invoice_id.remaining_amount
        else:
            res = dict(invoice_no='',
                       date_invoice=None,
                       date_due=None,
                       amount=0.0)
            self.update(res)

    @api.onchange('amount')
    def _onchange_local_amount(self):
        for record in self:
            if record.master_id and record.master_id.currency_id:
                record.local_amount = record.master_id.currency_id.round(record.amount * record.master_id.exchange_rate)
            # self.local_amount_tax = self.master_id.currency_id.round(self.amount_tax * self.master_id.exchange_rate)

    @api.depends('amount', 'invoice_remaining_amount')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = record.amount - record.invoice_remaining_amount
        # self.remaining_amount = self.amount - self.invoice_amount

    @api.model
    def update_invoice_payment_amount(self):
        """
        更新发票冲销
        :return:
        """
        if self.invoice_id:
            self.invoice_id.update_invoice_payment_amount(model_name=self._name)


class account_receive_line(models.Model):
    _name = 'account.receive.line'
    _description = '收款单明细'

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.receive.line",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_account_receive_line_form2').id,
            "res_id": self.id,
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

    @api.depends('bill_due_date')
    def _compute_overdue_days(self):
        for record in self:
            record.overdue_days = 0
            if record.bill_date and record.bill_due_date:
                record.overdue_days = base_cw.public.get_days_between_date(time.strftime("%Y-%m-%d"),
                                                                           fields.Datetime.to_string(
                                                                               record.bill_due_date))

    master_id = fields.Many2one('account.receive', '收款单', ondelete="cascade")
    sequence = fields.Integer('项次', default=1)
    receive_category_id = fields.Many2one('account.receive.category', '收款类别', ondelete="restrict")
    account_id = fields.Many2one('cncw.account', '会计科目', ondelete="restrict")
    sub_account_id = fields.Many2one('res.partner', '辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'account_receive_line_id', string='辅助核算')
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
    amount = fields.Float('收款金额', digits='Product Price', )
    currency_id = fields.Many2one('res.currency', '币别', related='master_id.currency_id', readonly=True)
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', related='master_id.exchange_rate',
                                 readonly=True)
    local_amount = fields.Float('本币金额', digits='Product Price')
    bill_number = fields.Char('汇票编号')
    bill_date = fields.Date('汇票开立日期')
    bill_due_date = fields.Date('汇票到期日期')
    overdue_days = fields.Integer(string='汇票到期天数', compute='_compute_overdue_days', )
    receive_bank_id = fields.Many2one('res.partner.bank', '到款银行')
    acc_number = fields.Char('账户号码', related='receive_bank_id.acc_number', readonly=True)
    notice_bank_id = fields.Many2one('res.partner.bank', '通知银行')

    advance_id = fields.Many2one('account.advance', '预收款使用单')
    advance_amount = fields.Float('预收款余额', digits='Product Price', related='advance_id.remaining_amount',
                                  readonly=True, store=True)
    note = fields.Text('备注')
    team_id = fields.Many2one('crm.team', '销售团队', related='master_id.team_id', readonly=True, )
    receive_bank_ids = fields.Many2many('res.partner.bank', related='team_id.receive_bank_ids', string='可选收款行',
                                        readonly=True, )
    notice_bank_ids = fields.Many2many('res.partner.bank', related='team_id.notice_bank_ids', string='可选通知行',
                                       readonly=True, )

    def create(self, vals):
        base_cw.public.generate_sequence(self, vals)
        return super(account_receive_line, self).create(vals)

    @api.onchange('amount')
    def _onchange_amount(self):
        for r in self:
            r.local_amount = r.amount * r.master_id.exchange_rate

    def unlink(self):
        for line in self:
            if line.master_id.receive_type == 'A':
                if line.advance_id:
                    line.advance_id.compute_remaining_amount()
        res = super(account_receive_line, self).unlink()
        return res

    @api.onchange('receive_category_id')
    def onchange_receive_category_id(self):
        for record in self:
            if record.receive_category_id and record.receive_category_id.account_setup == 'A':
                record.account_id = record.receive_category_id.account_id and record.receive_category_id.account_id.id or False
                record.dc_type = record.receive_category_id.account_id and record.receive_category_id.dc_type

    @api.onchange('account_id')
    def onchange_account_id(self):
        for record in self:
            if record.account_id and record.account_id.sub_account_type == 'has' \
                    and record.account_id.subaccount_category_id.code == 'cash_flow':
                sub = record.env['res.partner'].search([('code', '=', 'cash_02')], limit=1)
                if sub:
                    record.sub_account_id = sub.id

    @api.model
    def get_advance_account(self):
        """
        取预收会计科目
        :return:
        """
        for record in self:
            return record.env['cncw.account'].search([], limit=1).id
            config = record.env['account.voucher.template'].search([('code', '=', '01')], limit=1)
            if not config or not config.advance_account_id:
                raise UserError(_('请在财务{凭证模版}设定中 维护应收、应付会计科目!'))
            account_id = config.advance_account_id.id
            return account_id

    def create_account_advance(self):
        """
        创建预收单
        :return:
        """
        for record in self:
            if record.master_id.state == 'done' and not record.advance_id and (record.master_id.receive_type == 'B' or (
                    record.master_id.receive_type == 'A' and record.account_id.ap_ar_type == '20' and record.dc_type == 'C')):
                # sub_account_lines_data = []
                # if record.master_id.partner_id:
                #     line_data = {'category_id': record.master_id.partner_id.subaccount_category_id.id,
                #                  'sub_account_id': record.master_id.partner_id.id}
                #     sub_account_lines_data = [(0, 0, line_data)]
                # for line in record.sub_account_lines:
                #     line_data = {'category_id': line.category_id.id, 'sub_account_id': line.sub_account_id.id}
                #     sub_account_lines_data.append((0, 0, line_data))
                item = dict(res_id=record.id,
                            date=record.master_id.date,
                            partner_id=record.master_id.partner_id.id,
                            currency_id=record.master_id.currency_id.id,
                            exchange_rate=record.master_id.exchange_rate,
                            tax_rate=record.master_id.tax_id.amount,
                            amount=record.amount,
                            total_amount=record.amount,
                            received_amount=0,
                            remaining_amount=record.amount,
                            lc_amount=record.local_amount,
                            lc_total_amount=record.local_amount,
                            lc_received_amount=0,
                            lc_remaining_amount=record.local_amount,
                            dc_type=record.dc_type,
                            note=record.note,
                            account_id=record.account_id and record.account_id.id or False,
                            sub_account_id=record.master_id.partner_id and record.master_id.partner_id.id or False,
                            # sub_account_lines=sub_account_lines_data,
                            offset_state='N')
                res = record.env['account.advance'].create(item)
                res.compute_remaining_amount()

    @api.model
    def update_advance(self):
        """
        更新预收单信息
        1.预收单删除
        2.预收使用更新冲销
        :return:
        """
        for record in self:
            if record.master_id.state in ('cancel', 'draft', 'confirmed') and (record.master_id.receive_type == 'B' or (
                    record.master_id.receive_type == 'A' and record.account_id.ap_ar_type in (
                    '20', '21') and record.dc_type == 'C')):
                record._cr.execute('delete from account_advance where res_id=%s' % (record.id,))
            if record.advance_id:
                record.advance_id.compute_remaining_amount()
