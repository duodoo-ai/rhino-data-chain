# -*- encoding: utf-8 -*-
import time

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
import logging

_logger = logging.getLogger(__name__)

class AccountInvoice(models.Model):
    _name = 'cncw.invoice.move'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'sequence.mixin']
    _order = 'date desc, name desc, id desc'
    _description = '发票'
    _mail_post_access = 'read'
    _check_company_auto = True


    @api.model
    def _get_invoice_default_sale_team(self):
        return self.env['crm.team']._get_default_team_id()

    @api.depends("origin_invoice_id",'account_statement_id', 'partner_id')
    def _compute_related_field(self):
        if self.partner_id:
            self.currency_id = self.partner_id.partner_currency_id
            self.exchange_rate = self.partner_id.partner_currency_id.rate or 1.0
        else:
            self.currency_id = self.env.user.company_id.currency_id
            self.exchange_rate = self.env.user.company_id.currency_id.rate or 1.0

    team_id = fields.Many2one(
        'crm.team', string='销售团队', default=_get_invoice_default_sale_team,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    ref = fields.Char(string='参考', copy=False, tracking=True)
    company_id = fields.Many2one(comodel_name='res.company', string='公司',
                                 store=True, readonly=True,default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(string='公司货币', readonly=True,
                                          related='company_id.currency_id')
    currency_id = fields.Many2one('res.currency', store=True, tracking=True, required=True,
                                  # states={'draft': [('readonly', False)]},
                                  string='货币',
                                  default='_compute_related_field')
    is_relation = fields.Boolean(string="是否关联申请", default=False)
    amount_total_company_signed = fields.Monetary(string='公司总金额', store=True, readonly=True,
                                                  compute='_compute_amount', currency_field='company_currency_id')
    amount_total = fields.Monetary(string='总金额', store=True, readonly=True,
                                   compute='_compute_amount', currency_field='company_currency_id')
    amount_untaxed = fields.Monetary(string='不含税金额', store=True, readonly=True, tracking=True,
        compute='_compute_amount')
    amount_residual = fields.Monetary(string='到期金额', store=True,
        compute='_compute_amount')
    amount_tax = fields.Monetary(string='税金', store=True, readonly=True,
        compute='_compute_amount')
    amount_total_signed = fields.Monetary(string='已确认总额', store=True, readonly=True,
        compute='_compute_amount', currency_field='company_currency_id')
    amount_residual_signed = fields.Monetary(string='已确认到期金额', store=True,
        compute='_compute_amount', currency_field='company_currency_id')
    amount_untaxed_signed = fields.Monetary(string='不含税金额', store=True, readonly=True,
        compute='_compute_amount', currency_field='company_currency_id')
    name = fields.Char('单据编号', default="New")
    type = fields.Selection([
        ('out_invoice', '客户发票'),
        ('in_invoice', '供应商发票'),
        ('out_refund', '客户红字发票'),
        ('in_refund', '供应商红字发票'),
    ], readonly=True, index=True, change_default=True,
        default=lambda self: self._context.get('type', 'out_invoice'),
        tracking=True)
    state = fields.Selection([
        ('draft', '草稿'),
        ('proforma', '发票形式1'),
        ('proforma2', '发票形式2'),
        ('open', '开票'),
        ('paid', '确认支付'),
        ('cancel', '取消'),
    ], string='Status', default="draft", readonly=True)
    date = fields.Date('记帐日期', default=fields.Date.context_today)
    account_statement_id = fields.Many2one('account.statement', '对帐单')
    invoice_no = fields.Char('发票号码')
    date_invoice = fields.Date(default=fields.Date.context_today, string='发票日期')
    invoice_date_due = fields.Date(string='到期日期', readonly=True, index=True, copy=False,
                                   # states={'draft': [('readonly', False)]}
                                   )
    origin_invoice_id = fields.Many2one('cncw.invoice.move', '原发票号码')
    partner_id = fields.Many2one('res.partner', readonly=True, tracking=True,
                                 # states={'draft': [('readonly', False)]},
                                 check_company=True,
                                 string='往来单位', change_default=True)

    move_type = fields.Selection(selection=[
        ('entry', 'Journal Entry'),
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bill'),
        ('in_refund', 'Vendor Credit Note'),
        ('out_receipt', 'Sales Receipt'),
        ('in_receipt', 'Purchase Receipt'),
    ], string='类型', required=True, store=True, index=True, readonly=True, tracking=True,
        default="entry", change_default=True)
    type_name = fields.Char('类型名称', compute='_compute_type_name')
    user_id = fields.Many2one('res.users', '订单执行员', required=False)
    confirm_date = fields.Datetime('确认日期')
    confirm_user_id = fields.Many2one('res.users', '确认人员', required=False)
    categ_id = fields.Many2one('product.category', '货品分类')
    open_date = fields.Datetime('核准日', readonly=True)
    open_user_id = fields.Many2one('res.users', '核准人', required=False, readonly=True)
    invoice_count = fields.Integer('发票份数')
    days = fields.Integer(compute='_compute_due_days', string='天数', )
    exchange_rate = fields.Float('汇率', digits='Product Unit of Measure', default=1.0)
    tax_id = fields.Many2one('account.tax', '税别')
    tax_rate = fields.Float(related='tax_id.amount', string='税率', readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', 'invoice_attachment_rel', 'invoice_id', 'attachment_id', '附件')

    invalid_amount = fields.Float(string='作废金额', digits='Product Price',
                                  compute='_compute_invalid_amount', store=True)
    adjust_amount = fields.Float('调整金额', digits='Product Price', readonly=False)
    total_invoice_amount = fields.Float(string='发票总金额', compute='compute_total_invoice_amount',
                                        digits='Product Price', store=True, readonly=False)
    lc_total_invoice_amount = fields.Float(string='发票总金额(本币)', compute='compute_total_invoice_amount',
                                           digits='Product Price', store=True, readonly=False)
    payment_amount = fields.Float('已付金额', digits='Product Price', compute='_compute_payment_amount',
                                  store=True, readonly=False,
                                  help='已付金额指已做付款申请的冲销金额合计，不管付款单的状态是否确认都会回写到此栏位中。')
    remaining_amount = fields.Float('剩余金额', digits='Product Price', readonly=False,
                                    compute='compute_total_invoice_amount', store=True)
    lc_remaining_amount = fields.Float('剩余金额(本币)', readonly=False, digits='Product Price',
                                       compute='compute_total_invoice_amount', store=True)
    offset_state = fields.Selection([('N', '未冲销'),
                                     ('P', '部分冲销'),
                                     ('A', '已完全冲销')],
                                    '冲销状态', default='N', readonly=True)
    payment_mode_id = fields.Many2one('payment.mode', '付款方式', ondelete="restrict")
    stock_incoterms_id = fields.Many2one('stock.incoterms', '价格条款 ', ondelete="restrict")
    payment_term_id = fields.Many2one('account.payment.term', '付款条件', ondelete="restrict")
    payment_date = fields.Date('最后付款日期', help='最后一次付款日期')
    account_id = fields.Many2one('cncw.account', '科目',default=lambda self: self.get_tax_account(self._context.get('type')))
    pay_offset_ids = fields.One2many('account.pay.offset.line', 'invoice_id', '付款明细', required=False)
    receive_offset_ids = fields.One2many('account.receive.offset.line', 'invoice_id', '收款明细', required=False)
    invoice_category = fields.Selection([('A', '普票'), ('B', '增票')], '发票种类', default='A')
    tax_amount = fields.Float('税额', digits='Product Price', help='自主档总金额计算税额')
    # journal_id = fields.Many2one('account.journal', required=False, )
    amount_discount = fields.Float(string='折扣金额', compute="_compute_amount", store=True)
    amount_discount_signed = fields.Float(string='本币折扣金额', compute="_compute_amount", store=True)

    is_red_invoice = fields.Boolean('为红冲发票', compute="_compute_red_invoice", store=True)
    invoice_line_ids = fields.One2many('cncw.invoice.move.line', 'move_id', string='发票明细',
                                       copy=False, readonly=True,
                                       domain=[('exclude_from_invoice_tab', '=', False)],
                                       # states={'draft': [('readonly', False)]}
                                       )
    line_categ_id = fields.Many2one('product.category', '明细货品分类', related='invoice_line_ids.categ_id')
    comment = fields.Char(string='备注')
    type_tax_use = fields.Selection(related='tax_id.type_tax_use', string='征税范围')
    invoice_line_ids2 = fields.One2many(related="invoice_line_ids", readonly=True, copy=False)
    account1_id = fields.Many2one('cncw.account', string='发票科目')
    invoice_partner_bank_id = fields.Many2one('res.partner.bank', string="客户发票银行",
                                              readonly=False, store=True)
    tax_line_ids = fields.One2many('account.invoice.tax', 'invoice_id', string='税科目金额',
                                   readonly=True, # states={'draft': [('readonly', False)]},
                                   copy=True)

    lc_payment_amount = fields.Float('累计收付款金额(本币)', digits='Product Price', readonly=True)

    purchase_vendor_bill_id = fields.Many2one('purchase.bill.union', store=False, readonly=True,
        # states={'draft': [('readonly', False)]},
        string='自动完成',)
    purchase_id = fields.Many2one('purchase.order', store=False, readonly=True,
        # states={'draft': [('readonly', False)]},
        string='采购单',)

    def _get_invoice_reference(self):
        self.ensure_one()
        vendor_refs = [ref for ref in set(self.line_ids.mapped('purchase_line_id.order_id.partner_ref')) if ref]
        if self.ref:
            return [ref for ref in self.ref.split(', ') if ref and ref not in vendor_refs] + vendor_refs
        return vendor_refs

    @api.onchange('date_invoice')
    def _onchange_invoice_date(self):
        if self.date_invoice:
            if not self.invoice_date_due or self.invoice_date_due < self.date_invoice:
                self.invoice_date_due = self.date_invoice
            if self.date != self.date_invoice:  # Don't flag date as dirty if not needed
                self.date = self.date_invoice

    def is_invoice(self, include_receipts=False):
        return self.move_type in self.get_invoice_types(include_receipts)

    @api.model
    def get_invoice_types(self, include_receipts=False):
        return ['out_invoice', 'out_refund', 'in_refund', 'in_invoice'] + (include_receipts and ['out_receipt', 'in_receipt'] or [])

    def _get_lines_onchange_currency(self):
        # Override needed for COGS
        return self.invoice_line_ids

    @api.onchange('date', 'currency_id')
    def _onchange_currency(self):
        currency = self.currency_id or self.company_id.currency_id

        if self.is_invoice(include_receipts=True):
            for line in self._get_lines_onchange_currency():
                line.currency_id = currency
                line._onchange_currency()
        else:
            for line in self.invoice_line_ids:
                line._onchange_currency()

        # self._recompute_dynamic_lines(recompute_tax_base_amount=True)


    def write(self, vals):
        # OVERRIDE
        old_purchases = [move.mapped('invoice_line_ids.purchase_line_id.order_id') for move in self]
        res = super(AccountInvoice, self).write(vals)
        for i, move in enumerate(self):
            new_purchases = move.mapped('invoice_line_ids.purchase_line_id.order_id')
            if not new_purchases:
                continue
            diff_purchases = new_purchases - old_purchases[i]
            # if diff_purchases:
            #     refs = ["<a href=# data-oe-model=purchase.order data-oe-id=%s>%s</a>" % tuple(name_get) for name_get in diff_purchases.name_get()]
            #     message = _("This vendor bill has been modified from: %s") % ','.join(refs)
            #     move.message_post(body=message)
        return res


    @api.depends('name', 'move_type', 'invoice_no')
    def name_get(self):
        result = []
        for line in self:
            result.append((line.id, line.invoice_no or line.name or ''))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search(['|', ('invoice_no', 'ilike', name), ('name', 'ilike', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    # 计算开票日期到应收款日期的天数
    @api.depends('date_invoice', 'invoice_date_due')
    def _compute_due_days(self):
        for record in self:
            days = 0
            if record.date_invoice and record.invoice_date_due:
                days = base_cw.public.get_days_between_date(record.date_invoice,
                                                            fields.Datetime.to_string(record.invoice_date_due))
            record.days = days

    @api.depends('pay_offset_ids', 'pay_offset_ids.amount', 'receive_offset_ids',
                 'receive_offset_ids.amount')
    def _compute_payment_amount(self):
        for record in self:
            pay_records = record.pay_offset_ids.filtered(lambda x: x.master_id.state == 'done')
            receive_records = record.receive_offset_ids.filtered(lambda x: x.master_id.state == 'done')
            record.payment_amount = sum(pay_records.mapped('amount')) + sum(receive_records.mapped('amount'))
            record.lc_payment_amount = sum(pay_records.mapped('local_amount')) + sum(
                receive_records.mapped('local_amount'))
        # self.remaining_amount =lc_remaining_amount= self.total_invoice_amount - self.payment_amount
        #
        # if self.currency_id != self.company_id.currency_id:
        #     lc_remaining_amount = self.company_id.currency_id.round(self.remaining_amount * self.exchange_rate)
        # self.lc_remaining_amount=lc_remaining_amount
        # if self.remaining_amount == 0 and self.payment_amount == 0:
        #     self.offset_state = 'N'

    @api.depends('adjust_amount', 'amount_total', 'payment_amount')
    def compute_total_invoice_amount(self):
        for record in self:
            if record.invoice_line_ids:
                record.total_invoice_amount = record.amount_total + record.adjust_amount + record.invalid_amount
                record.remaining_amount = record.total_invoice_amount - record.payment_amount
                lc_total_invoice_amount = record.total_invoice_amount = record.amount_total + record.adjust_amount + record.invalid_amount
                lc_remaining_amount = record.remaining_amount = record.total_invoice_amount - record.payment_amount
                if record.company_id.currency_id and record.currency_id != record.company_id.currency_id:
                    lc_remaining_amount = record.company_id.currency_id.round(
                        record.remaining_amount * record.exchange_rate)
                    lc_total_invoice_amount = record.company_id.currency_id.round(
                        record.total_invoice_amount * record.exchange_rate)
                record.lc_total_invoice_amount = lc_total_invoice_amount
                record.lc_remaining_amount = lc_remaining_amount

                if record.remaining_amount == 0 and record.payment_amount == 0:
                    record.offset_state = 'N'
                elif abs(record.remaining_amount) > 0 and (
                        abs(record.remaining_amount) < abs(record.total_invoice_amount)):
                    record.offset_state = 'P'
                    if record.state == 'paid':
                        record.state = 'open'  # 状态更新为开启
                elif float_compare(record.payment_amount, record.total_invoice_amount,
                                   precision_rounding=0.01) == 0:
                    record.offset_state = 'A'
                    if record.state == 'open':
                        record.state = 'paid'  # 状态更新为已付
                elif record.total_invoice_amount < 0 and record.move_type in ('out_invoice', 'in_invoice'):
                    record.state == 'paid'
                    record.offset_state = 'A'
                elif record.remaining_amount == 0 and record.payment_amount == 0 and record.total_invoice_amount == 0 and \
                        record.invalid_amount < 0:
                    record.state == 'paid'
                    record.offset_state = 'A'
                else:
                    record.offset_state = 'N'
                    if record.state == 'paid':
                        record.state = 'open'

    # commit 修改原生account.move中的_compute_amount方法，要注释到原生的depend依赖
    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.amount', 'currency_id', 'company_id')
    def _compute_amount(self):
        for record in self:
            record.amount_untaxed = sum(line.price_subtotal for line in record.invoice_line_ids)
            record.amount_tax = sum(line.amount for line in record.invoice_line_ids)
            record.amount_total = record.amount_untaxed + record.amount_tax
            record.amount_discount = amount_discount_signed = sum(
                line.amount_discount for line in record.invoice_line_ids)
            amount_total_company_signed = record.amount_total
            amount_untaxed_signed = record.amount_untaxed
            # TODO 待确认数据传递
            # if record.currency_id and record.currency_id != record.company_id.currency_id:
                # amount_total_company_signed = record.currency_id.compute(record.amount_total,
                #                                                          record.company_id.currency_id)
                # amount_untaxed_signed = record.currency_id.compute(record.amount_untaxed, record.company_id.currency_id)
                # amount_discount_signed = record.currency_id.compute(amount_discount_signed,
                #                                                     record.company_id.currency_id)
            # sign = record.move_type in ['in_refund', 'out_refund'] and -1 or 1
            # record.amount_total_company_signed = amount_total_company_signed * sign
            # record.amount_total_signed = record.amount_total * sign
            # record.amount_untaxed_signed = amount_untaxed_signed * sign
            # record.amount_discount_signed = amount_discount_signed * sign

    @api.depends('invoice_line_ids', 'invoice_line_ids.invalid_amount')
    def _compute_invalid_amount(self):
        for record in self:
            if record.invoice_line_ids:
                record.invalid_amount = sum(line.invalid_amount for line in record.invoice_line_ids)
                record.compute_total_invoice_amount()

    @api.model
    def get_account(self, invoice_type, partner_id=None):
        """
        取应收、应付会计科目
        :return:
        """
        if not partner_id:
            config = self.env['account.voucher.template'].search([('code', '=', '01')], limit=1)
            if not config or not config.payable_account_id or not config.receivable_account_id:
                raise UserError(_('请在财务设定中 维护应收、应付会计科目!'))
            if invoice_type in ('out_invoice', 'out_refund'):
                account_id = config.receivable_account_id.id
            else:
                account_id = config.payable_account_id.id
            return account_id
        return account_id

    @api.model
    def get_pay_account(self, invoice_type, product_id=None, product_type=None, fiscal_pos=None):
        """
        取应收、应付会计科目
        :return:
        """
        return False

    @api.model
    def get_tax_account(self, type):
        """
        取会科
        :return:
        """
        config = self.env['account.voucher.template'].search([('code', '=', '01')], limit=1)
        if not config or not config.sale_tax_account_id or not config.purchase_tax_account_id:
            raise UserError(_('请在 凭证模版之[预会计科目] 设定中 维护进项税、销项税会计科目!'))
        if type in ('out_invoice', 'out_refund'):
            account_id = config.sale_tax_account_id.id
        else:
            account_id = config.purchase_tax_account_id.id
        return account_id

    @api.depends('invoice_line_ids', 'invoice_line_ids.origin_invoice_line_id')
    def _compute_red_invoice(self):
        for record in self:
            if len(record.invoice_line_ids) == 0 or (len(record.invoice_line_ids) > 0 and len(
                    self.invoice_line_ids.mapped('origin_invoice_line_id')) > 0):
                record.is_red_invoice = True
            else:
                record.is_red_invoice = False

    # 付款逾期提醒
    def payment_overdue(self):
        overdue_ids = self.search([
            ('invoice_date_due', '<', fields.date.today()),
            ('state', 'not in', ('draft', 'paid', 'cancel')),
        ])
        if overdue_ids:
            group_ids = self.env['res.groups'].search([('name', 'ilike', '财务会计')]).ids
            purchase_ui_view_id = self.env['ir.ui.view'].search([('name', 'like', 'account.move.purchase.form'),('xml_id','=','cncw_statement.view_account_invoice_purchase_form')],limit=1).id
            customer_ui_view_id = self.env['ir.ui.view'].search([('name', 'like', 'account.move.sale.form')]).id
            purchase_view_id = self.env['ir.actions.act_window.view'].search([('view_id', '=', purchase_ui_view_id)])
            customer_view_id = self.env['ir.actions.act_window.view'].search([('view_id', '=', customer_ui_view_id)])
            mail_channel = self.env['mail.channel']
            mail_post = mail_channel.search([('name', 'ilike', '付款逾期提醒')])
            if not mail_post:
                mail_post = mail_channel.create(dict(
                    name="付款逾期提醒",
                    description='付款逾期',
                    public='groups',
                    moderation_notify_msg='moderation_notify_msg',
                    moderation_guidelines_msg='moderation_guidelines_msg',
                    group_ids=group_ids,
                ))
            purchase_body = ''
            customer_body = ''
            for overdue in overdue_ids:
                if overdue.partner_id.subaccount_category_id.code == 'supplier':
                    purchase_body = purchase_body + '<a href=/web#id=%d&action=%d&model=account.move&view_type=form>%s</a>；' % (
                        overdue.id, purchase_view_id.act_window_id.id, overdue.display_name)
                else:
                    customer_body = customer_body + '<a href=/web#id=%d&action=%d&model=account.move&view_type=form>%s</a>；' % (
                        overdue.id, customer_view_id.act_window_id.id, overdue.display_name)
            body = "应付账款逾期：<p>" + purchase_body + "</p>应收账款逾期：<p>" + customer_body + "</p>"
            mail_post.message_post(message_type='comment', body=body, subtype='mail.mt_comment')

        @api.model_create_multi
        def create(self, vals):
            res = super(AccountInvoice, self).create(vals)
            if res.move_type in ("out_invoice", 'out_refund'):
                res.name = self.env['ir.sequence'].next_by_code('sale.invoice.no') or 'New'
            elif res.move_type in ('in_invoice', 'in_refund'):
                res.name = self.env['ir.sequence'].next_by_code('purchase.invoice.no') or 'New'
            for move in res:
                if move.reversed_entry_id:
                    continue
                purchase = move.line_ids.mapped('purchase_line_id.order_id')
                if not purchase:
                    continue
                refs = ["<a href=# data-oe-model=purchase.order data-oe-id=%s>%s</a>" % tuple(name_get) for name_get in
                        purchase.name_get()]
                message = _("This vendor bill has been created from: %s") % ','.join(refs)
                move.message_post(body=message)
            return res

    def _write(self, vals):
        res = super(AccountInvoice, self)._write(vals)
        return res

    def action_invoice_paid(self):
        pass

    def unlink(self):
        for r in self:
            if r.state != 'cancel':
                raise  UserError(_('提示：发票%s未取消,只能删除已取消的发票!' % r.name))
        res = super(AccountInvoice, self).unlink()
        return res

    def copy(self, default=None):
        raise except_orm(_('系统提示'), _('不提供复制功能!'))
        res_id = super(AccountInvoice, self).copy(default)
        return res_id

    def action_create_invoice_no(self):
        self.ensure_one()
        self.name = self.env['ir.sequence'].next_by_code('sale.invoice.no') or 'New'

    @api.depends('move_type')
    def _compute_type_name(self):
        type_name_mapping = {k: v for k, v in
                             self._fields['move_type']._description_selection(self.env)}
        replacements = {'out_invoice': ('发票'), 'out_refund': ('Credit Note')}

        for record in self:
            name = type_name_mapping[record.move_type]
            record.type_name = replacements.get(record.move_type, name)

    @api.depends('move_type')
    def _compute_invoice_filter_type_domain(self):
        for move in self:
            if move.is_sale_document(include_receipts=True):
                move.invoice_filter_type_domain = 'sale'
            elif move.is_purchase_document(include_receipts=True):
                move.invoice_filter_type_domain = 'purchase'
            else:
                move.invoice_filter_type_domain = False

    @api.onchange('origin_invoice_id')
    def _onchange_origin_invoice_id(self):
        if self.invoice_line_ids:
            self.invoice_line_ids = False
            # self.flush()
        if self.origin_invoice_id:
            self.currency_id = self.origin_invoice_id.currency_id.id
            self.exchange_rate = self.origin_invoice_id.exchange_rate
            origin_invoice_ids = self.env['cncw.invoice.move'].search(
                [('state', 'in', ('draft', 'open')), ('origin_invoice_id', '=', self.origin_invoice_id.id)])
            if len(origin_invoice_ids) > 1:
                raise UserError(_('系统中已存在此发票的红字发票还没有确认不可以重复创建!'))
            else:
                # 将未作废完的发票明细带入红字发票
                results = self.origin_invoice_id.invoice_line_ids.filtered(
                    lambda x: (x.invalid_amount + x.total_amount) != 0)
                move_lines = self.env['cncw.invoice.move.line']
                for line in results:
                    sub_account_lines_data = []
                    for line2 in line.sub_account_lines:
                        line_data = {'category_id': line2.category_id.id, 'sub_account_id': line2.sub_account_id.id}
                        sub_account_lines_data.append((0, 0, line_data))
                    item = dict(origin_invoice_line_id=line.id,
                                # move_id=self.id,
                                account_statement_line_id=line.account_statement_line_id and line.account_statement_line_id.id or False,
                                stock_move_id=line.stock_move_id and line.stock_move_id.id or False,
                                name=line.product_id.name,
                                product_uom_id=line.product_id.uom_id and line.product_id.uom_id.id or line.product_uos.id,
                                product_id=line.product_id.id,
                                account_id=line.account_id and line.account_id.id or False,
                                account1_id=line.account1_id and line.account1_id.id or False,
                                account2_id=line.account2_id and line.account2_id.id or False,
                                sub_account_id=line.sub_account_id and line.sub_account_id.id or False,
                                sub_account_lines=sub_account_lines_data,
                                tax_ids=[(4, line.move_id.tax_id.id)],
                                quantity=-line.quantity,
                                price_unit=line.price_unit,
                                price_subtotal=-line.price_subtotal,
                                tax_amount=-line.tax_amount,
                                total_amount=-line.total_amount,
                                purchase_line_id=line.purchase_line_id and line.purchase_line_id.id or False,
                                exclude_from_invoice_tab=False,
                                )
                    if line.sale_line_ids:
                        for order_line in line.sale_line_ids:
                            item['sale_line_ids'] = [(4, order_line.id)]
                    move_lines |= self.invoice_line_ids.new(item)
                self.invoice_line_ids = move_lines

    def clear_in_out_refund_invoice(self):
        if self.origin_invoice_id:
            self.invoice_line_ids.with_context(check_move_validity=False).unlink()
            self.with_context(check_move_validity=False).write({'origin_invoice_id': False,
                                                                'amount_total': 0,
                                                                'total_invoice_amount': 0,
                                                                'remaining_amount': 0
                                                                })
            self.flush()

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.origin_invoice_id = False
            self.invoice_line_ids = False
            self.payment_mode_id = self.partner_id and self.partner_id.payment_mode_id and self.partner_id.payment_mode_id.id or False
            self.tax_id = self.partner_id.account_tax_id and self.partner_id.account_tax_id.id
            self.currency_id = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.id or False

            self.payment_term_id = self.partner_id.payment_term_id and self.partner_id.payment_term_id.id or False
            if self.move_type in ('out_invoice', 'out_refund') or self._context.get('default_type') in (
                    'out_invoice', 'out_refund'):
                self.account_id = self.partner_id.property_cncw_account_receivable_id and self.partner_id.property_cncw_account_receivable_id.id or False
            else:
                self.account_id = self.partner_id.property_cncw_account_payable_id and self.partner_id.property_cncw_account_payable_id.id or False
            if self.partner_id.bank_ids:
                self.invoice_partner_bank_id  = self.partner_id.bank_ids[0].id
            user = self.partner_id.user_id
            if user:
                self.user_id = user.id

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        if self.currency_id:
            self.exchange_rate = self.currency_id.rate

    @api.model
    def invalid_invoice_confirm_data_check(self):
        if self.is_red_invoice and not self.origin_invoice_id:
            raise  UserError(_('提示!原发票号码不可为空!'))
        if self.total_invoice_amount > 0:
            raise  UserError(_('提示!红字发票金额不能大于0!'))

    # 红字发票申请确认
    def action_invalid_invoice_confirm(self):
        """
        作废发票 确认更新相关
        :return:
        """
        self.ensure_one()
        self.invalid_invoice_confirm_data_check()
        if self.invoice_line_ids.mapped('origin_invoice_line_id'):
            # 调整 红字发票 确认后金额直接在原发票中扣减， 收付款 时不可再选来收付款 所以直接 为付款状态
            # 在开票 统计时 还要做特别处理
            for x in self.invoice_line_ids.filtered(lambda y: y.origin_invoice_line_id):
                x.origin_invoice_line_id.invalid_amount += x.total_amount
                x.origin_invoice_line_id.invalid_qty += x.quantity
                # 作废发票需要将作废金额数量写入对账单并重新对账
                if x.account_statement_line_id:
                    x.account_statement_line_id.invalid_amount += x.total_amount
                    x.account_statement_line_id.invalid_qty += x.quantity
                if x.stock_move_id:
                    x.stock_move_id.compute_checked_qty()
            self.write(dict(confirm_user_id=self._uid,
                            confirm_date=fields.Date.context_today(self),
                            state='paid'))
            # 判断是否全部反冲
            if abs(self.total_invoice_amount) == self.origin_invoice_id.total_invoice_amount:
                self.origin_invoice_id.write(dict(state='paid', offset_state='A'))
        else:
            # 一般红字发票 退货 or 折让产生的 红字发票
            self.write(dict(confirm_user_id=self._uid,
                            confirm_date=fields.Date.context_today(self),
                            state='open'))
        self.origin_invoice_id._compute_invalid_amount()
        self.action_statement_invoiced_amount()

    # 红字发票取消确认
    def action_invalid_invoice_cancel_confirm(self):
        """
        作废发票 更新原发票相关
        :return:
        """
        for invoice in self:
            invoice.invoice_check()
            if invoice.invoice_line_ids.mapped('origin_invoice_line_id'):
                for x in invoice.invoice_line_ids.filtered(lambda y: y.origin_invoice_line_id):
                    x.origin_invoice_line_id.invalid_amount -= x.total_amount
                    x.origin_invoice_line_id.invalid_qty -= x.quantity
                    # 作废发票需要将作废金额数量写入对账单并重新对账
                    if x.account_statement_line_id:
                        x.account_statement_line_id.invalid_amount -= x.total_amount
                        x.account_statement_line_id.invalid_qty -= x.quantity
                    if x.stock_move_id:
                        x.stock_move_id.compute_checked_qty()
            invoice.write(dict(confirm_user_id=False,
                               confirm_date=None,
                               state='draft'))
            invoice.origin_invoice_id._compute_invalid_amount()
            invoice.action_statement_invoiced_amount()

    # 红字发票作废
    def action_invalid_invoice_draft_to_cancel(self):
        self.ensure_one()
        self.invoice_check()
        if self.invoice_line_ids.mapped('origin_invoice_line_id'):
            self.origin_invoice_id._compute_invalid_amount()
        if self.account_statement_id.state == 'done' and self.account_statement_id.invoice_id:
            self.account_statement_id.write(dict(
                invoice_id=False,
                state='confirmed',
                done_user_id=False,
                done_date=None, )
            )
        self.invoice_line_ids.mapped('account_statement_line_id').write(dict(state='confirmed'))
        self.write(dict(state='cancel'))
        self.invoice_line_ids.write(dict(state='cancel'))
        self.action_statement_invoiced_amount()

    @api.model
    def invoice_confirm_data_check(self):
        if self.invoice_no:
            if len(self.invoice_no) > len(self.invoice_no.strip()):
                raise UserError(_('提示!发票号码不可为空!'))
        else:
            raise UserError(_('提示!发票号码不可为空!'))
        if self.total_invoice_amount < 0:
            raise UserError(_('提示!发票金额不能小于0!'))
        for line in self.invoice_line_ids:
            if line.quantity > line.remaining_invoiced_qty:
                raise UserError(_('提示!开票数量不可大于未开票数量!'))

    # 发票申请确认
    def action_confirm(self):
        self.ensure_one()
        self.invoice_confirm_data_check()
        for line in self.invoice_line_ids:
            precision = self.env['decimal.precision'].precision_get('Account')
            if line.account_statement_line_id.state != 'done' and float_round(
                    line.account_statement_line_id.remaining_invoiced_amount,
                    precision_digits=precision) == 0:
                line.account_statement_line_id.state = 'done'
        self.write(dict(confirm_user_id=self._uid,
                        confirm_date=fields.Date.context_today(self),
                        state='open'))
        self.action_statement_invoiced_amount()
        self._distribute_diff_amount()

    # 发票取消确认
    def action_cancel_confirm(self):
        for invoice in self:
            invoice.invoice_check()
            invoice.write(dict(confirm_user_id=False,
                               confirm_date=None,
                               state='draft'))
            invoice.action_statement_invoiced_amount()

    # 取消发票作废掉
    def action_draft_to_cancel(self):
        self.ensure_one()
        self.invoice_check()
        if self.account_statement_id.state == 'done' and self.account_statement_id.invoice_id:
            self.account_statement_id.write(dict(
                invoice_id=False,
                state='confirmed',
                done_user_id=False,
                done_date=None, )
            )
        self.invoice_line_ids.mapped('account_statement_line_id').write(dict(state='confirmed'))
        self.write(dict(state='cancel'))
        self.invoice_line_ids.write(dict(state='cancel'))
        self.action_statement_invoiced_amount()

    def action_compute_advanced_amount(self):
        """
          计算 预开发票累计冲销
        :return:
        """
        for x in self.advance_offset_ids:
            sql = """select coalesce(sum(coalesce(amount,0)),0)  from account_invoice_advance_offset_line a left join cncw_invoice_move b on a.invoice_id=b.id
                      where b.state in ('open','paid')
                        and a.advance_invoice_id=%s""" % (x.advance_invoice_id.id,)
            self._cr.execute(sql)
            amount = self._cr.fetchone()[0]
            x.advance_invoice_id.advance_offset_amount = amount
            x.advance_invoice_id._compute_advance_remaining_amount()

    def invoice_check(self):
        """
        取消检查
        :return:
        """
        if self.payment_amount > 0.0:
            raise UserError(_('提示!发票已付款不可取消.'))
        list = self.env['cncw.invoice.move.line'].search(
            [('state', '!=', 'cancel'), ('origin_invoice_line_id', 'in', self.invoice_line_ids.ids)], limit=1)
        if list:
            raise UserError(_('提示!发票已做红字发票,不能取消.'))

    # 作废发票转草稿
    def action_cancel_to_draft(self):
        self.ensure_one()
        self.write(dict(state='draft'))
        self.action_statement_invoiced_amount()

    def action_statement_invoiced_amount(self):
        self.ensure_one()
        for x in self.invoice_line_ids.filtered(lambda v: v.account_statement_line_id):
            x.account_statement_line_id.compute_invoiced_amount_qty()
            if x.stock_move_id:
                x.stock_move_id.update_move_invoiced_amount_date()
            if x.purchase_line_id:
                x.purchase_line_id.compute_statement_state()

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        """由主档金额 计算税金"""
        taxs = self.tax_id.compute_all(sum(self.invoice_line_ids.mapped('total_amount')))
        self.tax_amount = taxs.get('total_included', 0) - taxs.get('total_excluded', 0)


    def _compute_tax_amount(self):
        """
        由主档的总金额计算税额
        :return:
        """
        taxs = self.tax_id.compute_all(sum(self.invoice_line_ids.mapped('total_amount')))
        self.tax_amount = taxs.get('total_included', 0) - taxs.get('total_excluded', 0)

    def _distribute_diff_amount(self):
        """分滩 主档明细档税金额差异，以主档为主"""
        if self.invoice_line_ids:
            line_tax_amount = sum(self.invoice_line_ids.mapped('amount'))
            diff = self.amount_tax - line_tax_amount
            if float_compare(diff, 0.0, precision_digits=4) != 0:
                self.invoice_line_ids[0].tax_amount += diff
                lines = max(self.invoice_line_ids, key=lambda x: x.total_amount)
                if len(lines) > 0:
                    line = lines[-1]
                    line.amount_tax += diff
                    line.price_subtotal -= diff
                    line.price_subtotal_signed -= diff

        diff = sum(self.invoice_line_ids.mapped('total_amount')) - self.amount_tax - sum(
            self.invoice_line_ids.mapped('price_subtotal'))
        if float_compare(diff, 0.0, precision_digits=4) != 0:
            lines = max(self.invoice_line_ids, key=lambda x: x.total_amount)
            if len(lines) > 0:
                line = lines[-1]
                line.price_subtotal += diff
                line.price_subtotal_signed += diff

    def action_test(self):
        self.ensure_one()
        self._onchange_invoice_line_ids()

    def action_done(self):
        self.action_date_assign()
        self.action_move_create()
        self.invoice_validate()
        self.write(dict(open_user_id=self._uid,
                        open_date=fields.Date.context_today(self),
                        state='open'))

    @api.model
    def update_invoice_payment_amount(self, model_name):
        """
        更新发票付款及最后付款日期  由收付款明细 在付确认时调用
        :return:
        """
        date = None
        if self.state == 'done':
            date = time.strftime("%Y-%m-%d")
        # 查找所有已付完成的冲销明细 MF 2016-09-25
        items = self.env[model_name].search([('state', '=', 'done'), ('invoice_id', '=', self.id)])
        if items:
            date = time.strftime("%Y-%m-%d")
        self.write(dict(payment_amount=sum([x.amount for x in items]),
                        payment_date=date))
        if self.invoice_line_ids:
            self.compute_total_invoice_amount()
        self.distr_payment_amount()
        self.invoice_line_ids.update_move_invoiced_amount_date()

    @api.onchange('payment_amount')
    def distr_payment_amount(self):
        """
        以发票金额分摊累计付款到明细  没有考滤 帐款调整金额
        :return:
        """
        amount = 0
        obj = self.invoice_line_ids and self.invoice_line_ids[0] or None
        if self.amount_total != 0.0:
            for x in self.invoice_line_ids:
                x.payment_amount = float_round(x.price_subtotal * self.payment_amount / self.amount_total,
                                               precision_rounding=0.0001)
                amount += x.payment_amount
                if float_compare(abs(x.price_subtotal), abs(obj.price_subtotal), precision_rounding=0.0001) > 0:
                    # 取值金额最大一笔平差异
                    obj = x
            if obj and not float_compare(amount, self.payment_amount, precision_rounding=0.0001):
                diff = self.payment_amount - amount
                obj.payment_amount += diff

    def action_open_account_invoice_select_statement_wizard(self):
        """
        打开 销售货款 对帐明细 窗口
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       active_id=self.id,
                       statement_type='S' if self.move_type in ('out_refund', 'out_invoice') else 'P', )
        self.env.context = context
        self._cr.execute("delete from account_invoice_select_statement where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.invoice.select.statement'].create(dict(master_id=self.id))
        return wizard_id.wizard_view()

    def action_open_invalid_invoice_select_wizard(self):
        """
        打开 作废发票选择向导
        :return:
        """
        self.ensure_one()
        if not self.origin_invoice_id:
            raise UserError(_('原发票号码不可为空!'))
        else:
            origin_invoice_id = self.env['cncw.invoice.move'].search(
                [('state', 'in', ('draft', 'open')), ('id', '!=', self.id),
                 ('origin_invoice_id.id', '=',
                  self.origin_invoice_id.id)])
            if origin_invoice_id:
                raise UserError(_('系统中已存在此发票的红字发票还没有确认不可以重复创建!'))
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       origin_invoice_id=self.origin_invoice_id.id,
                       invoice_id=self.id)
        self.env.context = context
        self._cr.execute("delete from invalid_invoice_select_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['invalid.invoice.select.wizard'].create(dict(invoice_id=self.id))
        return wizard_id.wizard_view()


class AccountInvoiceLine(models.Model):
    _name = 'cncw.invoice.move.line'
    _description = '发票明细'
    _order = "date desc, move_name desc, id"
    _check_company_auto = True

    price_subtotal = fields.Float("开票金额", digits='Product Price', )
    move_id = fields.Many2one('cncw.invoice.move', string='发票单据',
                              index=True, required=True, readonly=True, auto_join=True, ondelete="cascade",
                              check_company=True,
                              help="开票单据号.")
    move_name = fields.Char(string='单据名称', related='move_id.name', store=True, index=True)
    date = fields.Date(related='move_id.date', string='单据日期', store=True, readonly=True, index=True, copy=False,
                       aggregator='min')
    ref = fields.Char(related='move_id.ref', string='单据参考', store=True, copy=False, index=True, readonly=False)
    parent_state = fields.Selection(related='move_id.state', string='单据状态', store=True, readonly=True)
    company_id = fields.Many2one(related='move_id.company_id', store=True, readonly=True, string='公司',
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='公司货币',
                                          readonly=True, store=True)
    partner_id = fields.Many2one('res.partner', string='往来单位', ondelete='restrict')
    sub_account_ids = fields.Many2many('res.partner', compute='_get_sub_account_ids', string='可选辅助核算')
    note = fields.Text('备注')
    amount = fields.Float('税金', related='tax_amount')
    amount_discount = fields.Float(string='折扣金额', compute='_compute_price', store=True)
    amount_discount_signed = fields.Float(string='本币折扣金额', compute='_compute_price', store=True)
    currency_id = fields.Many2one('res.currency', string='货币',related="move_id.currency_id",store=True)
    product_uom_id = fields.Many2one('uom.uom', string='单位', domain="[('category_id', '=', product_uom_category_id)]")
    product_id = fields.Many2one('product.product', string='产品', ondelete='restrict')
    product_uom_category_id = fields.Many2one('uom.category', related='product_id.uom_id.category_id', string='单位分类', )
    categ_id = fields.Many2one('product.category', string='产品分类', related='product_id.categ_id')
    price_subtotal_signed = fields.Monetary(string='金额签署', currency_field='company_currency_id',
                                            store=True, readonly=True, compute='_compute_price')
    exclude_from_invoice_tab = fields.Boolean(string="排除")
    recompute_tax_line = fields.Boolean(store=False, readonly=True,
        help="Technical field used to know on which lines the taxes must be recomputed.")
    is_auto = fields.Boolean('系统自动产生', default=False)
    sequence = fields.Integer(default=1)
    name = fields.Char(string='标签', tracking=True)
    quantity = fields.Float(string='数量',
                            default=1.0, digits='Product Unit of Measure')
    price_unit = fields.Float(string='单价', digits='Product Price')
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0)
    account_statement_line_id = fields.Many2one('account.statement.line', '对帐明细')
    stock_move_id = fields.Many2one('stock.move', '出入库明细', related='account_statement_line_id.stock_move_id',
                                    store=True, readonly=True, )
    tax_amount = fields.Float('税额', digits='Product Price', store=True, compute='_compute_price',
                              default=0.00)
    tax_amount_signed = fields.Float('本币税额', digits='Product Price', store=True, compute='_compute_price',
                                     default=0.00)
    total_amount = fields.Float('总额', digits='Product Price', store=True, compute='_compute_price',
                                default=0.00)
    total_amount_signed = fields.Float('本币总额', digits='Product Price', store=True, compute='_compute_price',
                                       default=0.00)
    statement_amount = fields.Float('对帐金额', digits='Product Price', readonly=True,
                                    related='account_statement_line_id.amount')
    freight_amount = fields.Float('运费金额', digits='Product Price', default=0.00,
                                  related='account_statement_line_id.freight_amount', readonly=True, )
    remaining_invoiced_amount = fields.Float('未开票额', digits='Product Price', )
    remaining_invoiced_qty = fields.Float('未开票数', digits='Product Unit of Measure')
    move_type = fields.Selection([('out_invoice', 'Customer Invoice'),
                                  ('in_invoice', 'Supplier Invoice'),
                                  ('out_refund', 'Customer Refund'),
                                  ('in_refund', 'Supplier Refund'),
                                  ], string='发票类型', readonly=True,
                                 related='move_id.move_type', tracking=True)
    statement_source = fields.Selection(base_cw.public.STATEMENT_SOURCE, '对帐类型',
                                        related='account_statement_line_id.statement_source', readonly=True, )
    picking_type_id = fields.Many2one('stock.picking.type', '交易类型',
                                      related='account_statement_line_id.picking_type_id', store=True, readonly=True)
    payment_amount = fields.Float('累计收付款金额', digits='Product Price', readonly=True)
    lc_payment_amount = fields.Float('累计收付款金额(本币)', digits='Product Price', readonly=True)
    payment_date = fields.Date('付款日期', help='最后一次付款日期', related='move_id.payment_date', readonly=False, store=True)
    invoice_date = fields.Date('开票日期', help='开票日期', related='move_id.date', readonly=True, store=True)
    state = fields.Selection([
        ('draft', '草稿'),
        ('proforma', '发票形式1'),
        ('proforma2', '发票形式2'),
        ('open', '开票'),
        ('paid', '确认支付'),
        ('cancel', '取消'),
    ], string='Status', related='move_id.state', readonly=True)
    invalid_amount = fields.Float(string='作废金额', digits='Product Price', )
    invalid_qty = fields.Float(string='作废数量', digits='Product Unit of Measure')
    origin_invoice_line_id = fields.Many2one('cncw.invoice.move.line', '原发票明细')
    account_id = fields.Many2one('cncw.account', '税额科目', required=False, default='_default_account')

    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', default='D')
    account1_id = fields.Many2one('cncw.account', '收入/支出科目', help='default 为主档的account_id,在xml中写')

    account2_id = fields.Many2one('cncw.account', '应收/付科目', help='default 为主档的account_id,在xml中写')
    sub_account_type = fields.Selection(base_cw.public.SUB_ACCOUNT_TYPE, '辅助核算类型',
                                        related='account2_id.sub_account_type', readonly=True, )
    sub_account_id = fields.Many2one('res.partner', '辅助核算')
    sub_account_lines = fields.One2many('sub.account.line', 'cncw_invoice_move_line_id', '辅助核算')
    sub_account_lines_str = fields.Char(string='会计辅助核算', compute='compute_sub_account_lines_str')

    purchase_line_id = fields.Many2one('purchase.order.line', '采购明细', ondelete='set null', index=True)
    purchase_order_id = fields.Many2one('purchase.order', '采购单', related='purchase_line_id.order_id', readonly=True)
    sale_line_ids = fields.Many2many(
        'sale.order.line',
        'sale_order_line_cncw_invoice_rel',
        'invoice_line_id', 'order_line_id',
        string='销售明细', readonly=True, copy=False)
    # ==== Tax fields ====
    tax_ids = fields.Many2many('account.tax', string="税率")

    def _copy_data_extend_business_fields(self, values):
        ''' Hook allowing copying business fields under certain conditions.
        E.g. The link to the sale order lines must be preserved in case of a refund.
        '''
        self.ensure_one()
        values['sale_line_ids'] = [(6, None, self.sale_line_ids.ids)]
        values['purchase_line_id'] = self.purchase_line_id.id

    def edit_sub_account_lines(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "cncw.invoice.move.line",
            'view_mode': 'form',
            'view_id': self.env.ref('cncw_statement.view_cncw_invoice_move_line_form2').id,
            "res_id": self.id,
            "name": "编辑辅助核算",
            "target": 'new'
        }

    @api.depends('move_id', 'sequence')
    def name_get(self):
        res = []
        for record in self:
            name = "%s - %s" % (record.move_id.name, record.sequence)
            res.append((record.id, name))
        return res

    def _set_taxes(self):
        """ Used in on_change to set taxes and price."""
        if self.move_id.move_type in ('out_invoice', 'out_refund'):
            taxes = self.product_id.taxes_id or self.account_id.tax_ids
        else:
            taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids

        # Keep only taxes of the company
        company_id = self.company_id or self.env.user.company_id
        taxes = taxes.filtered(lambda r: r.company_id == company_id)

        self.tax_ids = self.move_id.fiscal_position_id.map_tax(taxes)

    @api.depends('price_unit', 'discount', 'tax_ids', 'quantity',
                 'product_id', 'move_id.partner_id',
                 'move_id.currency_id', 'move_id.company_id')
    def _compute_price(self):
        for record in self:
            currency = record.move_id and record.move_id.currency_id or None
            price = record.price_unit * (1 - (record.discount or 0.0) / 100.0)
            # price_signed = record.move_id.currency_id.compute(price, record.move_id.company_id.currency_id)
            taxes = False
            taxes2 = False
            # taxes_signed = False
            amount_discount_signed = record.amount_discount_signed if record.amount_discount_signed else 0
            amount_discount = record.amount_discount if record.amount_discount else 0
            tax_amount = record.tax_amount if record.tax_amount else 0
            tax_amount_signed = record.tax_amount_signed if record.tax_amount_signed else 0
            total_amount = record.total_amount if record.total_amount else 0
            price_subtotal_signed = record.price_subtotal_signed if record.price_subtotal_signed else 0
            total_amount_signed = record.total_amount_signed if record.total_amount_signed else 0
            price_subtotal = record.price_subtotal if record.price_subtotal else 0
            # sign = record.move_id.type in ['in_refund', 'out_refund'] and -1 or 1
            if not record.origin_invoice_line_id:
                if record.move_id.tax_id:
                    taxes = record.move_id.tax_id.compute_all(price, currency, record.quantity,
                                                              product=record.product_id,
                                                              partner=record.move_id.partner_id)
                    taxes2 = record.move_id.tax_id.compute_all(record.price_unit, currency, record.quantity,
                                                               product=record.product_id,
                                                               partner=record.move_id.partner_id)
                if taxes:
                    # 未税金额
                    price_subtotal = price_subtotal_signed = taxes[
                        'total_excluded'] if taxes else record.quantity * price
                    # 含税金额
                    total_amount = total_amount_signed = taxes['total_included'] if taxes else record.quantity * price
                    # 金额
                    tax_amount = tax_amount_signed = sum([t.get('amount', 0.0) for t in taxes.get('taxes', {})])
                    # TODO 待确认数据传递
                    if record.move_id.currency_id and record.move_id.currency_id != record.move_id.company_id.currency_id:
                        price_subtotal_signed = record.move_id.currency_id.compute(price_subtotal_signed,
                                                                                   record.move_id.company_id.currency_id)
                        total_amount_signed = record.move_id.currency_id.compute(total_amount_signed,
                                                                                 record.move_id.company_id.currency_id)
                        tax_amount_signed = total_amount_signed - price_subtotal_signed
                    sign = record.move_id.move_type in ['in_refund', 'out_refund'] and -1 or 1
                    price_subtotal_signed = price_subtotal_signed * sign
                    total_amount_signed = total_amount_signed * sign
                if taxes2:
                    total_amount = total_amount_signed = taxes2[
                        'total_included'] if taxes else record.quantity * record.price_unit
                    # 折扣金额
                    amount_discount = total_amount - record.total_amount
                    # TODO 待确认数据传递
                    if record.move_id.currency_id and record.move_id.currency_id != record.move_id.company_id.currency_id:
                        total_amount_signed = record.move_id.currency_id.compute(total_amount_signed,
                                                                                 record.move_id.company_id.currency_id)
                    amount_discount_signed = total_amount_signed - record.total_amount_signed

            if record.move_id.origin_invoice_id:
                fun = record.with_context(check_move_validity=False)
            elif record._context.get('check_move_validity') == False:
                fun = record.with_context(check_move_validity=False)
            else:
                fun = record
            fun.write({
                'amount_discount_signed': amount_discount_signed,
                'amount_discount': amount_discount,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
                'price_subtotal_signed': price_subtotal_signed,
                'total_amount_signed': total_amount_signed,
                'price_subtotal': price_subtotal,
                'tax_amount_signed': tax_amount_signed
            })

    @api.model
    def _default_account(self):
        return False

    def get_invoice_line_account(self, type, product, fpos, company):
        accounts = product.product_tmpl_id.get_product_accounts(fpos)
        if type in ('out_invoice', 'out_refund'):
            return accounts['income']
        return accounts['expense']

    @api.depends('account_id')
    def _get_sub_account_ids(self):
        for record in self:
            account_obj = self.env['cncw.account']
            record.sub_account_ids = account_obj.get_sub_account_ids(record.account2_id)

    def compute_sub_account_lines_str(self):
        for record in self:
            sub_account_lines_str = ''
            for line in record.sub_account_lines.filtered(lambda r: r.sub_account_id):
                sub_account_lines_str += ' | '+line.sub_account_id.name
                if line.category_id.code == 'cash_flow':
                    record.sub_account_id = line.sub_account_id
            record.sub_account_lines_str = sub_account_lines_str

    @api.model_create_multi
    def create(self, vals):
        base_cw.public.generate_sequence(self, vals[0], master_column='move_id')
        res_id = super(AccountInvoiceLine, self).create(vals)
        return res_id

    def update_move_invoiced_amount_date(self):
        """
        更新 move 上的 累计开票金额 最后一次开票日期
        :return:
        """
        for x in self.filtered(lambda k: k.stock_move_id):
            x.stock_move_id.update_move_invoiced_amount_date()
            # 更新订单相关
            x.stock_move_id.sale_line_id._get_cncw_invoice_qty()
            x.stock_move_id.sale_line_id._get_to_cncw_invoice_qty()

    def unlink(self):
        '''
        删除前更新对帐中的开票数量
        :return:
        '''
        for r in self:
            if r.state == 'draft':
                r.state = 'cancel'
                if r.account_statement_line_id:
                    r.account_statement_line_id.compute_invoiced_amount_qty()
                    r.account_statement_line_id.state = 'confirmed'
        res = super(AccountInvoiceLine, self).unlink()
        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        domain = {}
        if not self.move_id:
            return

        part = self.move_id.partner_id
        fpos = self.move_id.fiscal_position_id
        company = self.move_id.company_id
        currency = self.move_id.currency_id
        move_type = self.move_id.move_type

        if not part:
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select a partner!'),
            }
            return {'warning': warning}

        if not self.product_id:
            if move_type not in ('in_invoice', 'in_refund'):
                self.price_unit = 0.0
            domain['product_uom_id'] = []
        else:
            if part.lang:
                product = self.product_id.with_context(lang=part.lang)
            else:
                product = self.product_id

            self.name = product.partner_ref
            account = self.get_invoice_line_account(move_type, product, fpos, company)
            if account:
                self.account_id = account.id
            self._set_taxes()

            if move_type in ('in_invoice', 'in_refund'):
                if product.description_purchase:
                    self.name += '\n' + product.description_purchase
            else:
                if product.description_sale:
                    self.name += '\n' + product.description_sale
        return {'domain': domain}


class AccountInvoiceTax(models.Model):
    _name = "account.invoice.tax"
    _description = "Invoice Tax"
    _order = 'sequence'

    def _compute_base_amount(self):
        tax_grouped = {}
        for invoice in self.mapped('invoice_id'):
            tax_grouped[invoice.id] = invoice.get_taxes_values()
        for tax in self:
            tax.base = 0.0
            if tax.tax_id:
                key = tax.tax_id.get_grouping_key({
                    'tax_id': tax.tax_id.id,
                    'account_id': tax.account_id.id,
                })
                if tax.invoice_id and key in tax_grouped[tax.invoice_id.id]:
                    tax.base = tax_grouped[tax.invoice_id.id][key]['base']
                else:
                    _logger.warning('Tax Base Amount not computable probably due to a change in an underlying tax (%s).', tax.tax_id.name)

    invoice_id = fields.Many2one('cncw.invoice.move', string='发票', ondelete='cascade', index=True)
    name = fields.Char(string='发票说明', required=True)
    tax_id = fields.Many2one('account.tax', string='税率', ondelete='restrict')
    account_id = fields.Many2one('cncw.account', string='税科目', required=True, domain=[('deprecated', '=', False)])
    amount = fields.Monetary()
    manual = fields.Boolean(default=True)
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of invoice tax.")
    company_id = fields.Many2one('res.company', string='公司', related='account_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True, readonly=True)
    base = fields.Monetary(string='基础合计', compute='_compute_base_amount')