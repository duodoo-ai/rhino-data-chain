# -*- coding: utf-8 -*-
from odoo import fields, api, models


class advance_receive_payment_order(models.Model):
    _name = 'advance.receive.payment.order'
    _description = '预收预付款申请单'

    def _domain_employee_id(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    name = fields.Char('名称')
    department_id = fields.Many2one('hr.department', string='部门', compute='_compute_base_data', store=True)
    account_user_id = fields.Many2one('res.users', string='财务确认')
    account_manager_user_id = fields.Many2one('res.users', string='财务主管确认')
    state = fields.Selection([('draft', '草稿'),
                              ('confirmed', '确认'),
                              ('manager', '部门主管确认'),
                              ('manager_cancel', '部门主管驳回'),
                              ('account', '财务确认'),
                              ('account_cancel', '财务驳回'),
                              ('account_manager', '财务主管确认'),
                              ('account_manager_cancel', '财务主管驳回'),
                              ('cancel', '取消')], string='状态', default='draft')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    employee_id = fields.Many2one('hr.employee', "员工", domain=_domain_employee_id)
    user_id = fields.Many2one('res.users', string='申请人', default=lambda self: self.env.user)
    check_date = fields.Datetime('确认日期')
    manager_date = fields.Datetime('主管确认日期')
    account_date = fields.Datetime('财务确认')
    account_manager_date = fields.Datetime('财务主管确认')
    line_ids = fields.One2many('advance.receive.payment.order.line', 'master_id', string='明细')
    order_type = fields.Selection([('advance_receive', '预收'), ('advance_payment', '预付')], string='申请类型')
    partner_id = fields.Many2one('res.partner', string='往来单位')


    @api.depends('employee_id')
    def _compute_base_data(self):
        for record in self:
            if record.employee_id:
                record.department_id = record.employee_id.department_id.id
            else:
                record.department_id = False

    def action_confirmed(self):
        """确认"""
        for record in self:
            if record.state == 'draft':
                record.write({'state': 'confirmed', 'check_date': fields.Datetime.now()})


class advance_receive_payment_order_line(models.Model):
    _name = 'advance.receive.payment.order.line'
    _description = '预收预付款申请单明细'

    master_id = fields.Many2one('advance.receive.payment.order', string='申请单')
    order_type = fields.Selection([('advance_receive', '预收'),
                                   ('advance_payment', '预付')],
                                  string='申请类型',
                                  related='master_id.order_type', readonly=True)
    amount = fields.Monetary('金额', digits='Product Price')
    state = fields.Selection(related='master_id.state', string='单据状态', readonly=True)
