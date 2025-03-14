# -*- encoding: utf-8 -*-
import time, datetime
from odoo import models, fields, api, _
from odoo.exceptions import except_orm
#import odoo.addons.decimal_precision as dp
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.tools import float_compare, float_round
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class account_payment_confirm(models.Model):
    _name = 'account.payment.confirm'
    _inherit = ['mail.thread']
    _description = '付款确认单'
    _order = 'id desc'

    name = fields.Char('单据编号', )
    pay_id = fields.Many2one('account.pay', '付款申请单', required=True,
                             domain=[('state', '=', 'confirmed'),
                                     ('remaining_amount', '>', 0)])
    company_id = fields.Many2one('res.company', string='付款抬头',
                                 required=True, readonly=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='付款供应商', related='pay_id.partner_id', readonly=True)

    supplier_name = fields.Char(string='收款人全称', related='pay_id.supplier_name', readonly=True)

    payment_mode_id = fields.Many2one('payment.mode', '付款方式', required=True, ondelete="restrict")
    bill_no = fields.Char('承兑汇票号')
    bill_date = fields.Date('出票日')
    bill_due_date = fields.Date('汇票到期日')
    bill_amount = fields.Float('票面金额',  digits='Product Price',)
    for_this_amount = fields.Float('归入本单金额',  digits='Product Price',)
    amount = fields.Float('本次实际付款金额',  digits='Product Price',)
    late_fee = fields.Float('滞纳金',  digits='Product Price',)
    note = fields.Char('付款说明')
    payment_date = fields.Date('实际付款日期', default=fields.Date.context_today, required=True)
    attachment_ids = fields.Many2many('ir.attachment', 'payment_confirm_attachment_rel', 'payment_confirm_id',
                                      'attachment_id', '附件')
    state = fields.Selection(base_cw.public.VOUCHER_STATE, '单据状态', default='draft')
    confirm_user_id = fields.Many2one('res.users', '确认人')
    confirm_date = fields.Datetime('确认日')
    paid_amount = fields.Float(related='pay_id.paid_amount', string='已付金额', store=True, readonly=True,
                                digits='Product Price',)
    remaining_amount = fields.Float(related='pay_id.remaining_amount', string='剩余待付金额', store=True,
                                    readonly=True, copy=False,  digits='Product Price',)

    remaining_amount0 = fields.Float(string='剩余金额',  digits='Product Price',)

    @api.model
    def create(self, vals):
        base_cw.public.generate_voucher_no(self, vals)
        if 'pay_id' in vals and 'amount' in vals:
            account_pay = self.env['account.pay'].browse(vals["pay_id"])
            if float_round(vals["amount"], precision_rounding=0.01) > float_round(account_pay.remaining_amount,
                                                                                  precision_rounding=0.01):
                raise  UserError(_('提示!本次付款金额%s不能大于未付款金额%s' % (
                    float_round(vals["amount"], precision_rounding=0.01),
                    float_round(account_pay.remaining_amount, precision_rounding=0.01))))
        return super(account_payment_confirm, self).create(vals)

    @api.onchange('pay_id')
    def onchange_pay_id(self):
        if self.pay_id:
            self.payment_mode_id = self.pay_id.payment_mode_id and self.pay_id.payment_mode_id.id or False

    def unlink(self):
        for r in self:
            if r.state not in ("draft", "cancel"):
                raise  UserError(_('错误!只能删除草稿和取消状态的单据'))
        res = super(account_payment_confirm, self).unlink()
        return res

    @api.onchange('for_this_amount')
    def _onchange_for_this_amount(self):
        self.amount = self.for_this_amount

    @api.onchange('amount')
    def _onchange_amount(self):
        self.remaining_amount0 = self.pay_id.remaining_amount - self.amount

    def action_confirm(self):
        self.ensure_one()
        state = 'confirmed'
        self.write(dict(confirm_user_id=self._uid,
                        confirm_date=fields.Date.context_today(self),
                        state=state))

    def action_confirm(self):
        self.ensure_one()
        if float_compare(self.amount, self.pay_id.remaining_amount, precision_rounding=0.01) > 0:
            raise  UserError(_('提示!本次付款金额%s不能大于未付款金额%s' % (float_round(self.amount, precision_rounding=0.01),
                                                                   float_round(self.pay_id.remaining_amount,
                                                                               precision_rounding=0.01))))
        self._cr.commit()
        self.pay_id.payment_confirm_date = self.payment_date
        self.pay_id.payment_confirm_user_id = self._uid
        self.pay_id._compute_paid_amount()
        self.pay_id._compute_remaining_amount()

    def action_cancel_confirm(self):
        self.ensure_one()
        state = 'draft'
        self.write(dict(confirm_user_id=False,
                        confirm_date=None,
                        state=state))
        self.pay_id._compute_paid_amount()
        self.pay_id._compute_remaining_amount()
