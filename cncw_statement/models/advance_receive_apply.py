# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError


class AdvanceReceiveApply(models.Model):
    _name = 'advance.receive.apply'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = '收款申请单'

    def _domain_employee_id(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    name = fields.Char(string='单据编号', readonly=True, # states={'draft': [('readonly', False)]}
                       )
    account_user_id = fields.Many2one('res.users', string='财务确认')
    account_manager_user_id = fields.Many2one('res.users', string='财务主管确认')
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '申请确认'),
                              ('manager', '部门主管确认'),
                              ('manager_cancel', '部门主管驳回'),
                              ('cancel', '取消'),
                              ('end', '财务确认完成'),
                              ], string='状态', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='公司', default=lambda self: self.env.company)
    employee_id = fields.Many2one('hr.employee', u"员工", default=lambda self: self.env.user.employee_id)
    department_id = fields.Many2one(related='employee_id.department_id', string='部门', store=True, )
    department_manager_user_id = fields.Many2one(related='department_id.manager_id',
                                                 string='部门主管', store=True)
    user_id = fields.Many2one('res.users', string='申请人', default=lambda self: self.env.user)
    check_date = fields.Datetime('提交日期')
    commit_user = fields.Many2one('res.users', string='提交人')
    manager_date = fields.Datetime('主管确认日期')
    manager_user = fields.Many2one('res.users', string='部门主管审核')
    account_date = fields.Datetime('财务确认日期')
    account_user = fields.Many2one('res.users', string='财务出纳审核')
    account_manager_date = fields.Datetime('财务主管确认日期')
    order_type = fields.Selection([('A', '一般收款'), ('B', '预收款')], required=True, string='申请类型', store=True)
    partner_id = fields.Many2one('res.partner', string='往来单位',
                                 domain="[('customer_rank','>', 0)]")
    amount = fields.Float(string='申请金额', digits='Product Price', compute='_compute_amount', readonly=True,
                          # states={'draft': [('readonly', False)]},
                          store=True)
    wait_amount = fields.Float(string='剩余申请金额', digits='Product Price', compute='_compute_amount', readonly=True,
                               # states={'draft': [('readonly', False)]},
                               store=True)
    is_use = fields.Integer(string='是否使用标识')
    sale_order_ids = fields.Many2many('sale.order', 'advance_receive_apply_sale_rel', 'advance_id',
                                      'sale_id', string='销售订单',
                                      domain="[('partner_id','=',partner_id),('wait_apply_amount_total', '>', 0)]")  # 销售订单
    account_move_sale_ids = fields.Many2many('cncw.invoice.move', relation='account_move_sale_rel', string='销售发票',
                                             domain="[('state','in',['open','paid']),('partner_id','=',partner_id),('id','not in',account_move_sale_ids)]"
                                             )  # 销售发票
    team_id = fields.Many2one('crm.team', '销售团队', required=True)
    advance_receive_apply_lines = fields.One2many(comodel_name='advance.receive.apply.line',
                                                  inverse_name='receive_apply_id', string='已锁定金额')
    is_manager_user = fields.Boolean(default=False, compute='_compute_department_manager_user_id', )
    account_receive_ids = fields.One2many(comodel_name='account.receive', string='收款单',
                                          inverse_name='advance_receive_apply_id', readonly=True)
    amount_receive = fields.Float(digits='Product Price', string='已收款金额', compute='compute_account_receive_ids',
                                  store=True)
    wait_amount_receive = fields.Float(digits='Product Price', string='待收款金额', compute='compute_account_receive_ids',
                                       store=True)
    lock_amount_receive = fields.Float(digits='Product Price', string='已锁定收款金额', compute='compute_account_receive_ids',
                                       store=True)

    @api.depends('account_receive_ids', 'account_receive_ids.state', 'amount')
    def compute_account_receive_ids(self):
        for record in self:
            if record.account_receive_ids:
                # 已收款
                amount_receive = sum(
                    record.account_receive_ids.filtered(lambda obj: obj.state in ('done')).mapped('receive_amount'))
                # 已锁定
                lock_amount_receive = sum(
                    record.account_receive_ids.filtered(
                        lambda obj: obj.state not in ('draft', 'done', 'cancel')).mapped(
                        'local_receive_amount'))
                # 待收款
                record.write(dict(
                    amount_receive=amount_receive,
                    lock_amount_receive=lock_amount_receive,
                    wait_amount_receive=record.amount - amount_receive - lock_amount_receive
                ))
            else:
                record.write(dict(
                    wait_amount_receive=record.amount
                ))

    _sql_constraints = [('name_unique', 'unique (name, company_id)', '单据编号不可重复!'), ]

    def _compute_department_manager_user_id(self):
        for record in self:
            is_manager_user = self._uid == record.sudo().department_manager_user_id.user_id.id
            record.is_manager_user = is_manager_user

    @api.depends('sale_order_ids', 'sale_order_ids.wait_apply_amount_total')
    def _compute_amount(self):
        for record in self:
            # 统计销售订单可申请金额
            if record.sale_order_ids:
                record.wait_amount = sum(record.sale_order_ids.mapped('wait_apply_amount_total'))
            # else:
            #     record.wait_amount = 0

    def create(self, vals):
        order_type = vals.get('order_type')
        if order_type == 'A':
            sq_code = 'advance.receive.apply.a'
        else:
            sq_code = 'advance.receive.apply.b'
        vals['name'] = self.sudo().env['ir.sequence'].next_by_code(sq_code)
        return super(AdvanceReceiveApply, self).create(vals)

    def action_confirm_emp(self):
        for record in self:
            advance_receive_apply_lines = []
            """提交申请"""
            if record.state == 'draft':
                record.write(
                    {'state': 'confirmed', 'check_date': fields.Datetime.now(), 'commit_user': self.env.user.id})
            if record.order_type == 'A':
                move_sale_ids = record.account_move_sale_ids
                if move_sale_ids:
                    for move_sale in move_sale_ids:
                        if move_sale.state not in ['open', 'paid']:
                            raise UserError('请删除无效发票')
                    for move_sale in move_sale_ids:
                        move_sale.write({'is_relation': True})
                # else:
                #     raise UserError('请选择发票明细')

            if record.amount <= 0:
                raise UserError('对不起，你输入的金额必须大于0')
            if record.sale_order_ids:
                if record.amount > record.wait_amount:
                    raise UserError("申请金额不能大于可申请金额，请重新填写金额")
            if record.sale_order_ids:
                '''金额计算'''
                # 申请金额
                amount_total = record.amount
                for sale_order in record.sale_order_ids:
                    # 申请金额 > 订单可申请    申请金额 = 申请金额 - 订单可用金额
                    if amount_total > 0:
                        # 申请金额 >= 订单可用金额
                        if amount_total >= sale_order.wait_apply_amount_total:
                            lock_mount = sale_order.wait_apply_amount_total
                            lock_amount = sale_order.wait_apply_amount_total
                            amount_total = amount_total - sale_order.wait_apply_amount_total
                            sale_order.wait_apply_amount_total = 0

                        else:
                            sale_order.wait_apply_amount_total = sale_order.wait_apply_amount_total - amount_total
                            lock_mount = amount_total
                            lock_amount = amount_total
                            amount_total = 0
                        record.env['advance.receive.apply.line'].create(dict(
                            receive_apply_id=record.id,
                            sale_order_id=sale_order.id,
                            lock_mount=lock_mount,
                            lock_amount=lock_amount
                        ))
                #         advance_receive_apply_lines.append(advance_receive_apply_line.id)
                # record.write({'advance_receive_apply_lines': [(6, 0, advance_receive_apply_lines)]})

    def action_confirm_dep(self):
        """部门主管确认"""
        if self.state == 'confirmed':
            self.write({'state': 'manager', 'manager_date': fields.Datetime.now(), 'manager_user': self.env.user.id})

    def action_confirm_fin(self):
        """财务确认"""
        if self.state == 'manager':
            self.write({'state': 'end', 'account_date': fields.Datetime.now(), 'account_user': self.env.user.id})

    # def action_confirm_fi_sup(self):
    #     """财务主管确认"""
    #     if self.state == 'account':
    #         self.write({'state': 'end', 'account_manager_date': fields.Datetime.now()})

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
            record.advance_receive_apply_lines.unlink()

    def unlink(self):
        for record in self:
            if record.state not in ['draft', 'cancel']:
                raise UserError("单据正在审核中，不能进行删除操作")
            record.advance_receive_apply_lines.unlink()
            return super().unlink()


class AdvanceReceiveApplyLine(models.Model):
    _name = 'advance.receive.apply.line'
    _description = '扣减记录'

    receive_apply_id = fields.Many2one('advance.receive.apply', string='预付款单')
    sale_order_id = fields.Many2one('sale.order', string='销售单')
    lock_mount = fields.Float(digits=(16, 4), string='锁定金额')
    lock_amount = fields.Float(related='lock_mount', string='锁定金额')
