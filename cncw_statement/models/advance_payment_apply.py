# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError


class AdvancePaymentApply(models.Model):
    _name = 'advance.payment.apply'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = '付款申请单'

    def _domain_employee_id(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    @api.depends("purchase_order_ids", 'partner_id')
    def _compute_related_field(self):
        if self.partner_id:
            self.currency_id = self.partner_id.partner_currency_id
            self.exchange_rate = self.partner_id.partner_currency_id.rate or 1.0
            if self.currency_id != self.env.user.company_id.currency_id:
                self.is_exchange = True
            else:
                self.is_exchange = False
        else:
            self.currency_id = self.env.user.company_id.currency_id
            self.exchange_rate = self.env.user.company_id.currency_id.rate or 1.0

    name = fields.Char(string='单据编号', readonly=True, # states={'draft': [('readonly', False)]}
                       )
    account_user_id = fields.Many2one('res.users', string='财务确认')
    account_manager_user_id = fields.Many2one('res.users', string='财务主管确认', )
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '申请确认'),
                              ('manager', '部门主管确认'),
                              ('manager_cancel', '部门主管驳回'),
                              ('cancel', '取消'),
                              ('end', '财务确认完成'),
                              ], string='状态', default='draft', copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', '付款货币',compute='_compute_related_field',store=True,readonly=False)
    employee_id = fields.Many2one('hr.employee', u"员工", default=lambda self: self.env.user.employee_id)
    department_id = fields.Many2one(related='employee_id.department_id', string='部门', store=True, )
    department_manager_user_id = fields.Many2one(related='department_id.manager_id', string='部门主管', store=True)
    user_id = fields.Many2one('res.users', string='申请人', default=lambda self: self.env.user)
    check_date = fields.Datetime('提交日期')
    commit_user = fields.Many2one('res.users', string='提交人')
    manager_date = fields.Datetime('主管确认日期')
    manager_user = fields.Many2one('res.users', string='部门主管审核')
    account_date = fields.Datetime('财务确认日期')
    account_user = fields.Many2one('res.users', string='财务出纳审核')
    account_manager_date = fields.Datetime('财务主管确认日期')
    # line_ids = fields.One2many('advance.payment.apply.line', 'master_id', string='明细')
    order_type = fields.Selection([('A', '一般付款'), ('B', '预付款')], required=True, string='申请类型', store=True)
    partner_id = fields.Many2one('res.partner', string='往来单位',
                                 domain="[('supplier_rank','>','0')]")
    amount = fields.Float(string='申请金额', digits='Product Price', compute='_compute_amount', readonly=True,
                          store=True, # states={'draft': [('readonly', False)]}
                          )
    wait_amount = fields.Float(string='剩余申请金额', digits='Product Price', compute='_compute_amount', store=True,
                               readonly=True,
                               # states={'draft': [('readonly', False)]}
                               )
    is_use = fields.Integer(string='是否使用标识')
    purchase_order_ids = fields.Many2many('purchase.order', 'advance_payment_apply_purchase_rel', 'advance_id',
                                          'purchase_id',
                                          string='采购订单',
                                          domain="[('partner_id', '=', partner_id),('wait_apply_amount_total', '>', 0)]"
                                          )  # 采购订单
    account_move_purchase_ids = fields.Many2many('cncw.invoice.move', relation='account_move_purchase_rel', string='采购发票',
                                                 domain="[('state', 'in', ('open', 'paid')),('partner_id', '=', partner_id), ('id', 'not in', account_move_purchase_ids)]",
                                                 copy=False,

                                                 )  # 销售发票
    advance_payment_apply_lines = fields.One2many(comodel_name='advance.payment.apply.line',
                                                  inverse_name='payment_apply_id', string='已锁定金额')

    # line_ids = fields.One2many('advance.payment.apply.line', 'master_id', string='预付款/付款申请单明细')
    is_manager_user = fields.Boolean(default=False, compute='_compute_department_manager_user_id', )
    account_payment_ids = fields.One2many(comodel_name='account.pay', string='付款单',
                                          inverse_name='advance_payment_apply_id', readonly=True)
    amount_payment = fields.Float(digits='Product Price', string='已付款金额', compute='compute_account_payment_ids',
                                  store=True)
    wait_amount_payment = fields.Float(digits='Product Price', string='待付款金额', compute='compute_account_payment_ids',
                                       store=True)
    lock_amount_payment = fields.Float(digits='Product Price', string='已锁定付款金额', compute='compute_account_payment_ids',
                                       store=True)
    is_exchange = fields.Boolean(string='是否外币结算', compute='_compute_related_field', store=True)
    exchange_rate = fields.Float('汇率', digits='Exchange Rate',default=1.0)
    lc_amount = fields.Float('本币申请金额', digits='Product Price', compute='compute_account_payment_ids', store=True)
    lc_amount_payment = fields.Float('本币已付款金额', digits='Product Price', compute='compute_account_payment_ids',
                                     store=True)
    lc_wait_amount_payment = fields.Float('本币待付款金额', digits='Product Price', compute='compute_account_payment_ids',
                                          store=True)

    @api.depends('account_payment_ids', 'account_payment_ids.state', 'amount')
    def compute_account_payment_ids(self):
        for record in self:

            if record.account_payment_ids:
                # 已收款
                amount_payment = sum(
                    record.account_payment_ids.filtered(lambda obj: obj.state in ('done')).mapped('payment_amount'))
                # 已锁定
                lock_amount_payment = sum(
                    record.account_payment_ids.filtered(
                        lambda obj: obj.state not in ('draft', 'done', 'cancel')).mapped(
                        'payment_amount'))
                # 外币和本币关系换算
                lc_amount = record.amount * record.exchange_rate
                lc_amount_payment = record.amount_payment * record.exchange_rate
                lc_wait_amount_payment = (record.amount - amount_payment - lock_amount_payment) * record.exchange_rate
                # 待收款
                record.write(dict(
                    amount_payment=amount_payment,
                    lock_amount_payment=lock_amount_payment,
                    wait_amount_payment=record.amount - amount_payment - lock_amount_payment,
                    lc_amount=lc_amount,
                    lc_amount_payment=lc_amount_payment,
                    lc_wait_amount_payment=lc_wait_amount_payment,
                ))
            else:
                record.write(dict(
                    wait_amount_payment=record.amount,
                    lc_amount=record.amount * record.exchange_rate,
                    lc_wait_amount_payment=record.amount * record.exchange_rate
                ))

    def _compute_department_manager_user_id(self):
        for record in self:
            is_manager_user = self._uid == record.sudo().department_manager_user_id.user_id.id
            record.is_manager_user = is_manager_user

    @api.depends('purchase_order_ids', 'purchase_order_ids.wait_apply_amount_total')
    def _compute_amount(self):
        for record in self:
            # 统计可申请金额
            if record.purchase_order_ids:
                record.wait_amount = sum(record.purchase_order_ids.mapped('wait_apply_amount_total'))
            # else:
            #     record.wait_amount = 0

    def create(self, vals):
        order_type = vals.get('order_type')
        if order_type == 'A':
            sq_code = 'advance.payment.apply.a'
        else:
            sq_code = 'advance.payment.apply.b'
        vals['name'] = self.sudo().env['ir.sequence'].next_by_code(sq_code)
        return super(AdvancePaymentApply, self).create(vals)

    _sql_constraints = [('name_unique', 'unique (name, company_id)', '单据编号不可重复!'), ]

    # def action_create_payment(self):
    #     kv = {'advance_payment_id': self.id, 'payment_type': self.order_type,
    #           'currency_id': self.partner_id.currency_id.id,
    #           'partner_id': self.partner_id.id, 'advance_amount': self.amount
    #           }
    #     master = self.env['account.pay'].search([('advance_payment_id', '=', self.id)], limit=1)
    #     if not master:
    #         master = self.env['account.pay'].create(kv)
    #         values = []
    #         for invoice_id in self.account_move_purchase_ids:
    #             val = {'invoice_id': invoice_id.id, 'amount': invoice_id.remaining_amount, 'master_id': master.id,
    #                    "invoice_no": invoice_id.invoice_no, "date_due": invoice_id.invoice_date_due,
    #                    "date_invoice": invoice_id.date_invoice,
    #                    "account_id": invoice_id.account1_id and invoice_id.account1_id.id or False
    #                    }
    #             if invoice_id.account1_id.sub_account_type == 'has':
    #                 line_data = {'category_id': invoice_id.partner_id.subaccount_category_id.id,
    #                              'sub_account_id': invoice_id.partner_id.id}
    #                 sub_account_lines = [(0, 0, line_data)]
    #                 val.update({"sub_account_lines": sub_account_lines,
    #                             "sub_account_id": invoice_id.partner_id and invoice_id.partner_id.id or False})
    #             values.append(val)
    #         self.env['account.pay.offset.line'].create(values)
    #     return {
    #         "type": "ir.actions.act_window",
    #         "res_model": "account.pay",
    #         'view_mode': 'form',
    #         # 'view_id': master.id,
    #         "res_id": master.id,
    #         "name": "付款单",
    #         # "target": 'new'
    #     }
    #
    def action_confirm_emp(self):
        for record in self:

            # advance_payment_apply_lines = []
            """提交申请"""
            if record.state == 'draft':
                record.write(
                    {'state': 'confirmed', 'check_date': fields.Datetime.now(), 'commit_user': self.env.user.id})
            if record.order_type == 'A':
                move_purchase_ids = record.account_move_purchase_ids
                if move_purchase_ids:
                    for move_purchase in move_purchase_ids:
                        if move_purchase.state not in ['open', 'paid']:
                            raise UserError('请删除无效发票')
                    for move_purchase in move_purchase_ids:
                        move_purchase.write({'is_relation': True})
                # else:
                #     raise UserError('请选择发票明细')
            if record.amount <= 0:
                raise UserError('对不起，你输入的金额必须大于0')
            if record.purchase_order_ids:
                if record.amount > record.wait_amount:
                    raise UserError("申请金额不能大于可申请金额，请重新填写金额")
            if record.purchase_order_ids:
                '''金额计算'''
                # 申请金额
                amount_total = record.amount
                for purchase_order in record.purchase_order_ids:
                    # 申请金额 > 订单可申请    申请金额 = 申请金额 - 订单可用金额
                    if amount_total > 0:
                        # 申请金额 > 订单可用金额
                        if amount_total >= purchase_order.wait_apply_amount_total:
                            lock_mount = purchase_order.wait_apply_amount_total
                            lock_amount = purchase_order.wait_apply_amount_total
                            amount_total = amount_total - purchase_order.wait_apply_amount_total
                            purchase_order.wait_apply_amount_total = 0

                        else:
                            lock_mount = amount_total
                            lock_amount = amount_total
                            purchase_order.apply_amount_total = purchase_order.apply_amount_total + amount_total
                            amount_total = 0
                        advance_payment_apply_line = record.env['advance.payment.apply.line'].create(dict(
                            payment_apply_id=record.id,
                            purchase_order_id=purchase_order.id,
                            lock_mount=lock_mount,
                            lock_amount=lock_amount
                        ))
                #         advance_payment_apply_lines.append(advance_payment_apply_line.id)
                # record.write({'advance_payment_apply_lines': [(6, 0, advance_payment_apply_lines)]})
            # else:
            #     raise UserError('请选择销售订单明细')

    def action_confirm_dep(self):
        """部门主管确认"""
        if self.state == 'confirmed':
            self.write(
                {'state': 'manager', 'manager_date': fields.Datetime.now(), 'manager_user': self.env.user.id})

    def action_confirm_fin(self):
        """财务确认"""
        if self.state == 'manager':
            self.write({'state': 'end', 'account_date': fields.Datetime.now(), 'account_user': self.env.user.id})

    # def action_confirm_fi_sup(self):
    #     """财务主管确认"""
    #     if self.state == 'account':
    #         self.write(
    #             {'state': 'end', 'account_manager_date': fields.Datetime.now(), 'account_user': self.env.user.id})

    def action_confirm_emp_cancel(self):
        """申请人"""
        if self.state == 'draft':
            self.write({'state': 'cancel'})

    def action_confirm_dep_cancel(self):
        """部门"""
        if self.state == 'confirmed':
            self.write({'state': 'draft'})
            self.call_cancel()

    def action_confirm_fin_cancel(self):
        """财务"""
        if self.state == 'manager':
            self.write({'state': 'confirmed'})

    def call_cancel(self):
        for record in self:
            record.advance_payment_apply_lines.unlink()

    def unlink(self):
        for record in self:
            if record.state not in ['draft', 'cancel']:
                raise UserError("单据正在审核中，不能进行删除操作")
            record.advance_payment_apply_lines.unlink()
            return super().unlink()


class AdvancePaymentApplyLine(models.Model):
    _name = 'advance.payment.apply.line'
    _description = '扣减记录'

    payment_apply_id = fields.Many2one('advance.payment.apply', string='预付款单')
    purchase_order_id = fields.Many2one('purchase.order', string='采购单')
    lock_mount = fields.Float(digits=(16, 4), string='锁定金额')
    lock_amount = fields.Float(related='lock_mount', string='锁定金额')
