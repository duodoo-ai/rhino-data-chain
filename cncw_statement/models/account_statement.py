# -*- encoding: utf-8 -*-
import datetime
import time

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools import float_round
from torch.optim.optimizer import required


class res_company(models.Model):
    _inherit = 'res.company'
    _description = '公司信息'

    statement_start_day = fields.Integer('对帐起始日', default=1)


class account_statement(models.Model):
    _name = 'account.statement'
    _description = '对帐单'
    _order = 'name desc'

    @api.model
    def name_search(self, name, args=None, operator='ilike', context=None, limit=80):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('name', 'ilike', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('name', operator, name)] + args, limit=limit)
        return recs.name_get()

    @api.model
    def _get_settlement_type(self):
        if self._context is None:
            return {}
        self.statement_type = self._context.get('default_statement_type', 'S')

    @api.model
    def _default_start_date(self):
        return datetime.date.today().replace(day=1)
        company_id = self.env.user.company_id
        statement_start_day = 1
        if company_id.statement_start_day:
            statement_start_day = company_id.statement_start_day
        year = datetime.datetime.now().year
        month = datetime.datetime.now().month
        if company_id.statement_start_day > datetime.datetime.now().day:
            if month > 1:
                month -= 1
            else:
                year -= 1
                month = 12
        day = 1 if statement_start_day == 1 else statement_start_day + 1
        return datetime.datetime(*time.strptime('%s-%s-%s' % (year, month, day), '%Y-%m-%d')[:6])

    @api.model
    def _default_end_date(self):
        next_date = fields.Date.from_string(fields.Date.context_today(self))
        next_date += relativedelta(day=31, months=0)
        return next_date
        company_id = self.env.user.company_id
        statement_start_day = 1
        if company_id.statement_start_day:
            statement_start_day = company_id.statement_start_day
        year = datetime.datetime.now().year
        month = datetime.datetime.now().month
        if statement_start_day <= datetime.datetime.now().day:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
        day = 1 if statement_start_day == 1 else statement_start_day
        if day == 1:
            end_date = datetime.datetime(
                *time.strptime('%s-%s-%s' % (year, month, day), '%Y-%m-%d')[:6]) - datetime.timedelta(days=-1)
        else:
            end_date = datetime.datetime(*time.strptime('%s-%s-%s' % (year, month, day), '%Y-%m-%d')[:6])
        return end_date

    # 取得部门
    @api.depends('user_id')
    def _compute_department(self):
        self.department_id = self.user_id.department_id and self.user_id.department_id.id or False

    @api.depends('line_ids', 'line_ids.amount', 'line_ids.adjust_amount')
    def _compute_total_amount(self):
        self.freight_amount = sum(
            self.line_ids.filtered(lambda x: x.statement_source == 'B').mapped('amount'))
        self.amount = sum(self.line_ids.filtered(lambda x: x.statement_source != 'B').mapped('amount'))
        self.total_amount = sum(self.line_ids.mapped('total_amount'))
        self.adjust_amount = sum(self.line_ids.mapped('adjust_amount'))
        self.line_count = len(self.line_ids)

    @api.depends('total_amount')
    def _compute_amount_total_by_chinese(self):
        self.total_chinese_amount = '零'
        self.amount_total_by_chinese = base_cw.public.get_chinese_money(self.total_amount)

    @api.depends('total_amount')
    def _compute_amount_total_chinese(self):
        self.total_chinese_amount = base_cw.public.get_chinese_money(self.total_amount)

    @api.depends('line_ids')
    def _compute_is_invoiced(self):
        invoiced_qty = sum(self.line_ids.mapped('invoiced_qty'))
        if self.state == 'confirmed':
            if abs(invoiced_qty) > 0:
                self.is_invoiced = True
            else:
                self.is_invoiced = False
        else:
            self.is_invoiced = True

    name = fields.Char('单据编号', required=True, default='New')
    date = fields.Date('单据日期', default=lambda self: fields.Date.context_today(self), readonly=True)
    partner_id = fields.Many2one('res.partner', '往来单位')
    partner_currency_id = fields.Many2one('res.currency', '币别', help='厂商默认币别', ondelete="restrict")
    partner_exchange_rate = fields.Float('币别汇率', digits='Exchange Rate')

    currency_id = fields.Many2one('res.currency', '对帐币别', required=True, )
    exchange_rate = fields.Float('对帐汇率', digits='Exchange Rate', )
    tax_id = fields.Many2one('account.tax', string='税别', required=True)

    statement_type = fields.Selection(base_cw.public.STATEMENT_TYPE, '对帐类型', default=_get_settlement_type, )
    start_date = fields.Date('对帐起日', required=True, default=_default_start_date, )
    end_date = fields.Date('对帐迄日', required=True, default=_default_end_date, )
    user_id = fields.Many2one('res.users', '对帐人', default=lambda self: self.env.user, required=True)
    department_id = fields.Many2one('hr.department', '对账部门', required=False, readonly=True,
                                    default=lambda self: self.env.user.department_id)
    origin = fields.Char('来源单号')
    confirm_date = fields.Datetime('确认日', readonly=True)
    confirm_user_id = fields.Many2one('res.users', '确认人', readonly=True)
    done_date = fields.Datetime('完成日', readonly=True)
    done_user_id = fields.Many2one('res.users', '完成人', readonly=True)
    note = fields.Text('备注')
    company_id = fields.Many2one('res.company', string='公司', change_default=True,
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env.company)
    state = fields.Selection(base_cw.public.VOUCHER_STATE, '状态', default='draft')
    line_ids = fields.One2many('account.statement.line', 'master_id', '申请明细', )
    freight_amount = fields.Float('运费金额', digits='Product Price', compute='_compute_total_amount',
                                  store=True)
    amount = fields.Float('对帐金额', digits='Product Price', compute='_compute_total_amount', store=True)
    total_amount = fields.Float('总金额', digits='Product Price', compute='_compute_total_amount', store=True)
    adjust_amount = fields.Float('调整金额', digits='Product Price', compute='_compute_total_amount',
                                 store=True)
    total_chinese_amount = fields.Char(compute='_compute_amount_total_chinese', string='大写总金额',
                                       digits='Product Price',
                                       store=True, help="The total amount of Chinese capital")
    line_count = fields.Integer('明细笔数', compute='_compute_total_amount', store=True)
    invoice_id = fields.Many2one('cncw.invoice.move', '发票', )
    payment_mode_id = fields.Many2one('payment.mode', '付款方式', required=False, ondelete="restrict")
    stock_incoterms_id = fields.Many2one('stock.incoterms', '价格条款 ', required=False, ondelete="restrict")
    payment_term_id = fields.Many2one('account.payment.term', '付款条件', required=False, ondelete="restrict")
    is_invoiced = fields.Boolean('已开发票', default=False, compute='_compute_is_invoiced')
    categ_id = fields.Many2one('product.category', string='产品分类', related='line_ids.categ_id')

    def open_lines(self):
        self.ensure_one()
        view_id = self.env.ref('cncw_statement.view_account_statement_line_sale_tree').id
        return {
            'name': _('对账明细表'),
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'account.statement.line',
            'view_id': view_id,
            'domain': [('master_id', '=', self.id)]
        }

    def create(self, vals):
        if vals.get('statement_type') == 'S':
            base_cw.public.generate_voucher_no(self, vals, code='sale.account.statement')
        elif vals.get('statement_type') == 'P':
            base_cw.public.generate_voucher_no(self, vals, code='purchase.account.statement')
        return super(account_statement, self).create(vals)

    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            self.department_id = self.user_id.department_id and self.user_id.department_id.id or False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_currency_id = self.currency_id = self.partner_id.partner_currency_id and self.partner_id.partner_currency_id.id or False
            self.tax_id = self.partner_id.account_tax_id and self.partner_id.account_tax_id.id or False
            self.payment_mode_id = self.partner_id.payment_mode_id and self.partner_id.payment_mode_id.id or False
            self.payment_term_id = self.partner_id.payment_term_id and self.partner_id.payment_term_id.id or False

    @api.onchange('partner_currency_id')
    def _onchange_partner_currency_id(self):
        if self.partner_currency_id:
            self.exchange_rate = self.currency_id.rate

    @api.onchange('currency_id')
    def _onchange_currency_id(self):
        if self.currency_id:
            self.exchange_rate = self.currency_id.rate

    @api.model
    def check_data(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self.line_ids:
            if float_round(line.adjust_qty, precision_digits=precision) > 0 \
                    or float_round(line.adjust_qty, precision_digits=precision) > 0:
                if not line.adjust_reason:
                    raise UserError(_('操作提示!有调整数量或金额，调整原因必须输入！'))
        if len(self.line_ids) == 0:
            raise UserError(_('操作提示!对帐明细不可为空'))
        if self.statement_type == "P":
            for line in self.line_ids:
                if line.statement_source == "B":
                    if line.price_unit <= 0.0:
                        raise UserError(_('操作提示!运费单价不可小于等于0'))
                    if line.amount <= 0.0:
                        raise UserError(_('操作提示!运费金额不可小于等于0'))

    def action_confirm(self):
        self.ensure_one()
        self.check_data()
        self.write(dict(confirm_user_id=self._uid,
                        confirm_date=fields.Date.context_today(self),
                        state='confirmed'))
        self.line_ids._lot_compute_local_amount()
        self.update_line_state(state='confirmed')
        self.update_move_purchase_state()

    # 取消对账确认
    def action_cancel_confirm(self):
        self.ensure_one()
        for line in self.line_ids:
            if len(line.invoice_line_ids.filtered(lambda x: x.state != 'cancel')) > 0:
                raise UserError(_('操作提示!对账明细已开发票，不可以取消确认!'))
        self.write(dict(confirm_user_id=False,
                        confirm_date=None,
                        state='draft'))
        self.update_line_state(state='draft')
        self.update_move_purchase_state()

    # 产生发票
    def action_done(self):
        self.ensure_one()
        for line in self.line_ids:
            if len(line.invoice_line_ids.filtered(lambda x: x.state != 'cancel')) > 0:
                raise UserError(_('操作提示!对账明细已开发票，不可以再产生发票!'))
        self.action_create_invoice()
        self.write(dict(done_user_id=self._uid,
                        done_date=fields.Date.context_today(self),
                        state='done'))
        self.update_line_state(state='done')

    def action_cancel_done(self):
        self.ensure_one()
        if self.invoice_id and self.invoice_id.state not in ('draft', 'cancel'):
            raise UserError(_('提示!发票已开启或者已付款不可以取消发票.'))
        else:
            if self.invoice_id:
                self.invoice_id.state = 'cancel'
                self.invoice_id.unlink()
            for line in self.line_ids:
                line.compute_invoiced_amount_qty()
        state = 'confirmed'
        self.write(dict(state=state,
                        done_user_id=False,
                        done_date=None, ))
        self.update_line_state(state=state)

    @api.model
    def update_line_state(self, state='draft'):
        """
        更新 明细 状态
        :param state:
        :return:
        """
        self.line_ids.write(dict(state=state))

    @api.model
    def update_move_purchase_state(self):
        """
        更新 move/purchase 状态
        :return:
        """
        for line in self.line_ids:
            line.update_move_purchase_state()

    @api.onchange('exchange_rate')
    def onchange_exchange_rate(self):
        if self.exchange_rate:
            for line in self.line_ids:
                line.price_unit = base_cw.public.compute_amount(line.currency_id, self.currency_id,
                                                                from_currency_rate=line.exchange_rate,
                                                                to_currency_rate=self.exchange_rate)
                line.unchecked_amount = float_round(line.unchecked_qty * line.price_unit, precision_digits=2)
                line.amount = line.compute_amount()
                line.onchange_is_done()

    @api.model
    def check_invocie_data(self):
        if self.invoice_id:
            raise UserError(_('提示!已开发票'))
        for line in self.line_ids:
            if len(line.invoice_line_ids.filtered(lambda s: s.state != 'cancel')) > 0:
                raise UserError(_('提示!对账明细已开发票，不可以取消!'))

    # 产生发票
    def action_create_invoice(self):
        self.ensure_one()
        self.check_invocie_data()
        user_id = self.user_id

        invoice_type = 'in_invoice'
        if self.statement_type == 'P':
            if self.total_amount >= 0.0:
                invoice_type = 'in_invoice'
            else:
                invoice_type = 'in_refund'
        elif self.statement_type == 'S':
            if self.total_amount >= 0.0:
                invoice_type = 'out_invoice'
            else:
                invoice_type = 'out_refund'
        invoice_obj = self.env['cncw.invoice.move']
        account2_id = invoice_obj.get_account(invoice_type)
        tax_account_id = invoice_obj.get_tax_account(invoice_type)
        invoice_data = dict(partner_id=self.partner_id.id,
                            payment_term_id=self.partner_id.payment_term_id and self.partner_id.payment_term_id.id or False,
                            payment_mode_id=self.partner_id.payment_mode_id and self.partner_id.payment_mode_id.id or False,

                            categ_id=self.line_ids[0].product_id.categ_id and self.line_ids[
                                0].product_id.categ_id.id or False,
                            move_type=invoice_type,
                            currency_id=self.currency_id.id,
                            exchange_rate=self.exchange_rate,
                            tax_id=self.tax_id.id,
                            company_id=self.company_id.id,
                            user_id=user_id and user_id.id or False,
                            account_statement_id=self.id,
                            account1_id=account2_id,
                            account_id=tax_account_id,
                            invoice_partner_bank_id=self.partner_id.bank_ids and self.partner_id.bank_ids[
                                0].id or False,
                            date_invoice=fields.Date.context_today(self)
                            )
        invoice = self.env['cncw.invoice.move'].create(invoice_data)
        invoice._onchange_invoice_date()
        items = []
        seq = 1
        for x in self.line_ids.filtered(lambda y: y.state == 'confirmed'):
            account1_id = invoice.get_pay_account_product_type(invoice.move_type,x.product_id.product_type)
            digits = self.env['decimal.precision'].search([('name', '=', 'Product Price')], limit=1).digits
            price_unit = float_round(x.amount / x.qty, precision_digits=digits)
            item = dict(
                sequence=seq,
                is_auto=True,
                purchase_line_id=x.purchase_line_id and x.purchase_line_id.id or False,
                name=x.product_id.name or '',
                product_uom_id=x.product_id.uom_id and x.product_id.uom_id.id or x.product_uos.id,
                product_id=x.product_id.id,
                account_id=tax_account_id,
                account1_id=account1_id or False,  # 收入/支出 科目
                account2_id=account2_id,
                price_unit=price_unit,
                tax_ids=[(4, x.master_id.tax_id.id)],
                price_subtotal=x.remaining_invoiced_amount,
                quantity=x.qty,
                remaining_invoiced_qty=x.qty,
                remaining_invoiced_amount=x.remaining_invoiced_amount,
                move_id=invoice.id,
                account_statement_line_id=x.id,
            )
            if self.env['cncw.account'].browse(account2_id).sub_account_type == 'has':
                sub_account_lines_data = []
                for line in self.env['cncw.account'].browse(account2_id).subaccount_category_ids:
                    line_data = {'category_id': line.id,
                                 'sub_account_id': self.partner_id and self.partner_id.id or False}
                    sub_account_lines_data.append((0, 0, line_data))
                item.update(dict(sub_account_id=self.partner_id and self.partner_id.id or False, ))
            if x.sale_line_id:
                item['sale_line_ids'] = [(4, x.sale_line_id.id)]
            items.append((0, 0, item))
            seq += 1
        if items:
            ##jon 发票明细计算返点的默认值，需要在环境中提供客户字段
            invoice.with_context(partner_id=self.partner_id.id).write(dict(invoice_line_ids=items))
        self.invoice_id = invoice.id
        self.invoice_id._onchange_invoice_line_ids()
        self.invoice_id.action_statement_invoiced_amount()

    def unlink(self):
        for r in self:
            if r.state != 'draft':
                raise UserError(_('提示'), _('只能删除草稿或取消状态的资料!'))
            for line in r.line_ids:
                if line.stock_move_id:
                    line.stock_move_id.statement_state = "N"
        return super(account_statement, self).unlink()

    def action_open_account_statement_receive_wizard(self):
        """
        打开 采购收货对帐明细 窗口
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       active_id=self.id,
                       statement_source='A')  # 货款
        self.env.context = context
        data = dict(master_id=self.id)
        if self.partner_id:
            picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'incoming')], limit=1)
            data['partner_id'] = self.partner_id.id
            data['picking_type_id'] = picking_type_id.ids
        self._cr.execute("delete from account_statement_receive_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.statement.receive.wizard'].create(data)
        return wizard_id.wizard_view()

    def action_open_account_statement_receive_freight_wizard(self):
        """
        打开 采购 运费  对帐明细 窗口
        :return:
        """
        self.ensure_one()
        self._cr.commit()
        context = {}
        context.update(active_model=self._name,
                       active_ids=self.ids,
                       active_id=self.id,
                       statement_source='B'  # 运费
                       )
        self.env.context = context
        data = dict(master_id=self.id)
        if self.partner_id:
            data['partner_id'] = self.partner_id.id
        self._cr.execute("delete from account_statement_receive_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.statement.receive.wizard'].create(data)
        return wizard_id.freight_wizard_view()

    def action_open_account_statement_delivery_wizard(self):
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
                       statement_source='A'
                       )
        self.env.context = context
        self._cr.execute("delete from account_statement_delivery_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.statement.delivery.wizard'].create(dict(master_id=self.id))
        return wizard_id.wizard_view()

    # 增加销售运费对帐过程
    def action_create_sale_freight(self):
        # if self.statement_type == 'S':
        if self.line_ids.filtered(lambda x: x.statement_source == 'B'):
            raise UserError(_('错误提示!销售运费每个对帐单只能增加一次！'))
        product = self.env.ref('cncw_statement.product_product_freight')
        if not product:
            raise UserError(_('错误提示!没有找到对应的运费的产品基本资料，请确认是否启用！'))
        item = dict(product_id=product.id,
                    product_uom=product.uom_id and product.uom_id.id or False,
                    product_uos=product.uom_id and product.uom_id.id or False,
                    statement_source='B',
                    statement_method='1',
                    qty=1,
                    unchecked_qty=1,
                    product_uos_qty=1,
                    currency_id=self.currency_id.id,
                    exchange_rate=self.exchange_rate,
                    master_id=self.id
                    )
        self.env['account.statement.line'].create(item)

    # 增加 操作费 对帐过程
    def action_create_sale_operation(self):
        if self.statement_type == 'S':
            if self.line_ids.filtered(lambda x: x.statement_source == 'G'):
                raise UserError(_('错误提示!操作费 每个对帐单只能增加一次！'))
            product = self.env.ref('cncw_statement.product_product_operation')
            if not product:
                raise UserError(_('错误提示!没有找到对应的 操作费 的产品基本资料，请确认是否启用！'))
            item = dict(product_id=product.id,
                        product_uom=product.uom_id and product.uom_id.id or False,
                        product_uos=product.uom_id and product.uom_id.id or False,
                        statement_source='G',
                        statement_method='1',
                        qty=1,
                        unchecked_qty=1,
                        product_uos_qty=1,
                        currency_id=self.currency_id.id,
                        exchange_rate=self.exchange_rate,
                        master_id=self.id
                        )
            self.env['account.statement.line'].create(item)

    def action_open_account_statement_order_cost_wizard(self):
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
                       master_id=self.id,
                       statement_source='B'
                       )
        self.env.context = context
        self._cr.execute("delete from account_statement_order_cost_wizard where create_uid=%s" % (self._uid,))
        wizard_id = self.env['account.statement.order.cost.wizard'].create(dict(master_id=self.id))
        return wizard_id.wizard_view()


class account_statement_line(models.Model):
    _name = 'account.statement.line'
    _description = '对帐单明细'

    @api.depends('master_id.name', 'sequence')
    def name_get(self):
        res = []
        for record in self:
            name = '%s - %s' % (record.master_id.name, (record.sequence and str(record.sequence) or ''))
            res.append((record.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', context=None, limit=80):
        args = args or []
        recs = self.browse()
        if name:
            recs = self.search([('master_id.name', 'ilike', name)] + args, limit=limit)
        if not recs:
            recs = self.search([('master_id.name', operator, name)] + args, limit=limit)
        return recs.name_get()

    def compute_amount(self):
        for record in self:
            record.amount = float_round(record.qty * record.price_unit, precision_digits=2)

    def _compute_customer_order_no(self):
        for record in self:
            customer_order_no = ''
            if record.sale_line_id:
                customer_order_no = record.sale_line_id.order_id.customer_order_no
            record.customer_order_no = customer_order_no

    @api.depends('amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount  # + self.freight_amount

    @api.depends('unchecked_qty', 'qty', 'adjust_qty')
    def _compute_remaining_qty(self):
        for record in self:
            record.remaining_qty = record.unchecked_qty - record.qty + record.adjust_qty

    @api.depends('unchecked_amount', 'amount', 'adjust_amount')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = record.unchecked_amount - record.amount + record.adjust_amount

    @api.depends('amount', 'invoice_line_ids', 'qty', 'invoice_line_ids.price_subtotal',
                 'invoice_line_ids.quantity')
    def compute_invoiced_amount_qty(self):
        """
        发票金额+折扣金额
        @return:
        """
        for record in self:
            record.invoiced_amount = sum(
                [(x.total_amount + x.amount_discount) * (1 if x.move_type in ('out_invoice', 'in_invoice') else -1) for x in
                 record.invoice_line_ids if
                 x.state != 'cancel'])
            record.invoiced_qty = sum(
                [x.quantity * (1 if x.move_type in ('out_invoice', 'in_invoice') else -1) for x in record.invoice_line_ids if
                 x.state != 'cancel'])
            record.remaining_invoiced_amount = record.amount - record.invoiced_amount
            record.remaining_invoiced_qty = record.qty - record.invoiced_qty

    master_id = fields.Many2one('account.statement', '对帐单', ondelete="cascade", )
    sequence = fields.Integer('项次', default=1)
    statement_source = fields.Selection([('A', '货款'),
                                         ('B', '运费'),
                                         ('C', '模具费'),
                                         ('D', 'PPAP费用'),
                                         ('E', '第三方检测费用'),
                                         ('F', '内部调整'),
                                         ('G', '操作费')], '对帐类型', readonly=True, default='A')
    origin = fields.Char('来源单号', )
    note = fields.Text('备注')
    date = fields.Date('交易日期', default=fields.Date.context_today)
    stock_move_id = fields.Many2one('stock.move', '出入库明细')
    delivery_no = fields.Char('采购单号')
    picking_type_id = fields.Many2one('stock.picking.type', '交易类型', related='stock_move_id.picking_type_id',
                                      store=True,
                                      readonly=True)
    name = fields.Char('单号', related='stock_move_id.picking_id.name', store=True, readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', '订单明细')
    customer_order_no = fields.Char('客户订单编号', compute="_compute_customer_order_no")
    purchase_line_id = fields.Many2one('purchase.order.line', '采购订单明细')
    product_id = fields.Many2one('product.product', '货品编码', required=True)
    product_type = fields.Selection(base_cw.public.PRODUCT_TYPE, related='product_id.product_type',
                                    string='成本类型', readonly=True, copy=False)
    customer_product_code = fields.Char(string='客户产品编码', readonly=True)
    statement_method = fields.Selection(base_cw.public.STATEMENT_METHOD, '结算类型', )
    # 交易xxx begin
    product_uom = fields.Many2one('uom.uom', '单位', help='库存单位')
    price_unit_uos = fields.Float('采购单价(采购单位)', digits=(16, 4), help='源头来自于采购订单or销售订单')
    currency_id = fields.Many2one('res.currency', '币别', related='master_id.currency_id', store=True, readonly=True,
                                  help='源头来自于采购订单or销售订单-->出入库单')
    exchange_rate = fields.Float('汇率', digits='Exchange Rate', default=1.0,
                                 help='源头来自于采购订单or销售订单')
    # 交易xxx end
    # 不同采购单位的采购数量（由采购单转入的数量）
    product_uos = fields.Many2one('uom.uom', '采购单位')
    product_uos_qty = fields.Float('采购数量', digits='Product Unit of Measure')
    product_uos_amount = fields.Float('采购金额', digits='Product Price', )

    # 对帐xxx begin
    unchecked_qty = fields.Float('未对帐数量', digits='Product Unit of Measure',
                                 help='来自于出入库交易unchecked_qty')
    unchecked_amount = fields.Float('未对帐金额', digits='Product Price',
                                    help='未对帐金额=未对帐数量*对帐单价')
    qty = fields.Float('对帐数量', digits='Product Unit of Measure')
    price_unit = fields.Float('对帐单价', digits='Product Price',
                              help='对帐单价=采购单价(采购单位)*币别转换率')
    amount = fields.Float('对帐金额', digits='Product Price', )
    freight_price = fields.Float('运费单价', digits='Product Price', )
    freight_amount = fields.Float('运费金额', digits='Product Price', )
    total_amount = fields.Float('总金额', digits='Product Price', compute='_compute_total_amount', store=True)
    # 调整： 负为调减  正为调加
    adjust_qty = fields.Float('调整数量', digits='Product Unit of Measure')
    adjust_amount = fields.Float('调整金额', digits='Product Price', )
    adjust_reason = fields.Char('调整原因')

    remaining_qty = fields.Float('剩余对帐数量', digits='Product Unit of Measure',
                                 compute='_compute_remaining_qty')
    remaining_amount = fields.Float('剩余对帐金额', digits='Product Price', compute='_compute_remaining_amount')
    remaining_tran_amount = fields.Float('剩余对帐金额', digits='Product Price', )
    # 对帐xxx end

    is_done = fields.Boolean('结案', default=False, help='工作性栏位,将剩余对帐金额及数量值写入调整金额及数量栏位')
    state = fields.Selection(base_cw.public.VOUCHER_STATE, '单据状态', default='draft')

    # 本位币begin
    local_checked_amount = fields.Float('本币对帐金额', digits='Product Price', )
    local_freight_amount = fields.Float('本币运费金额', digits='Product Price', )
    local_adjust_amount = fields.Float('本币调整金额', digits='Product Price', )
    local_total_amount = fields.Float('本币总金额', digits='Product Price', )
    # 本位币 end
    exchange_diff_amount = fields.Float(string='汇差', digits='Product Price', help='汇差金额')

    invoice_line_ids = fields.One2many('cncw.invoice.move.line', 'account_statement_line_id', '发票明细')
    invoiced_amount = fields.Float('已开发票金额', digits='Product Price', compute='compute_invoiced_amount_qty',
                                   store=True)
    invoiced_qty = fields.Float('已开发票数量', digits='Product Unit of Measure',
                                compute='compute_invoiced_amount_qty', store=True)
    invalid_amount = fields.Float(string='作废金额', digits='Product Price', )
    invalid_qty = fields.Float(string='作废数量', digits='Product Unit of Measure')
    invoice_state = fields.Selection(base_cw.public.STATEMENT_STATE, '开票状态', default='A')

    remaining_invoiced_amount = fields.Float('未开票额', digits='Product Price',
                                             compute='compute_invoiced_amount_qty',
                                             store=True)
    remaining_invoiced_qty = fields.Float('未开票数', digits='Product Unit of Measure',
                                          compute='compute_invoiced_amount_qty',
                                          store=True)
    categ_id = fields.Many2one('product.category', string='产品分类', related='product_id.categ_id')

    @api.constrains('adjust_qty', 'adjust_amount')
    def _check_adjust_qty(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        if float_round(self.adjust_qty, precision_digits=precision) > 0 \
                or float_round(self.adjust_qty, precision_digits=precision) > 0:
            if not self.adjust_reason:
                raise UserError(_('有调整数量或金额，调整原因必须输入！'))

    @api.constrains('qty', 'amount')
    def _check_qty_amount(self):
        if self.statement_source == 'A':
            if self.qty == 0.0:
                raise UserError(_('对帐数量不可为0'))
            if abs(self.qty) > abs(self.unchecked_qty):
                raise UserError(_('对帐数量不可大于未对帐数量'))
        else:
            # 对账类型B,G
            if self.amount != self.price_unit:
                raise UserError(_('系统提示!对帐单价乘以对帐数量不等于对账金额!'))

    @api.onchange('adjust_qty')
    def onchange_adjust_qty(self):
        if self.statement_source == 'A':
            amount = self.unchecked_amount
            if not self.is_done:
                amount = float_round((self.qty - self.adjust_qty) * self.price_unit,
                                     precision_rounding=self.master_id.currency_id.rounding)
            self.adjust_amount = -(amount - self.amount)
        else:
            self.adjust_amount = 0

    @api.onchange('amount')
    def onchange_amount(self):
        if self.statement_source == 'A' and self.is_done:
            self.adjust_amount = -(self.unchecked_amount - self.amount)
            self.adjust_qty = -(self.unchecked_qty - self.qty)
        else:
            self.adjust_amount = 0
            self.adjust_qty = 0

    @api.model_create_multi
    def create(self, vals):
        base_cw.public.generate_sequence(self, vals[0])
        return super(account_statement_line, self).create(vals)

    @api.constrains('adjust_amount', 'adjust_reason')
    def _check_adjust_reason(self):
        if self.master_id.statement_type == 'S' and self.adjust_amount != 0.0 and not self.adjust_reason:
            raise UserError(_('调整原因不可为空!'))

    @api.onchange('is_done')
    def onchange_is_done(self):
        self.adjust_qty = 0
        self.adjust_amount = 0
        if self.is_done and self.statement_source == 'A':
            self.amount = float_round(self.qty * self.price_unit,
                                      precision_rounding=self.master_id.currency_id.rounding)
            self.adjust_qty = -(self.unchecked_qty - self.qty)
            self.adjust_amount = -(self.unchecked_amount - self.amount)
            self.adjust_reason = '尾差调整'
        else:
            self.adjust_qty = 0
            self.adjust_amount = 0
            self.adjust_reason = ''

    @api.onchange('qty', 'price_unit')
    def onchange_price_unit(self):
        self.amount = float_round(self.qty * self.price_unit, precision_rounding=self.master_id.currency_id.rounding)
        self._lot_compute_local_amount()

    @api.model
    def update_move_purchase_state(self):
        """
        更新 move/purchase 状态
        :return:
        """
        if self.stock_move_id:
            print(self.statement_source)
            self.stock_move_id.compute_checked_qty(statement_source=self.statement_source)
        if self.purchase_line_id:
            self.purchase_line_id.compute_statement_state()

    def _lot_compute_local_amount(self):
        for x in self:
            x._compute_local_amount()

    def _compute_local_amount(self):
        """
        计算本位币别金额
        :return:
        """
        exchange_rate = self.master_id.exchange_rate
        if exchange_rate<1 and exchange_rate>0:
            self.local_checked_amount = self.master_id.currency_id.round(self.amount / self.master_id.exchange_rate)
            self.local_freight_amount = self.master_id.currency_id.round(
                self.freight_amount / self.master_id.exchange_rate)
            self.local_adjust_amount = self.master_id.currency_id.round(
                self.adjust_amount / self.master_id.exchange_rate)
            self.local_total_amount = self.master_id.currency_id.round(
                self.total_amount / self.master_id.exchange_rate)
        else:
            self.local_checked_amount = self.master_id.currency_id.round(self.amount * self.master_id.exchange_rate)
            self.local_freight_amount = self.master_id.currency_id.round(
                self.freight_amount * self.master_id.exchange_rate)
            self.local_adjust_amount = self.master_id.currency_id.round(
                self.adjust_amount * self.master_id.exchange_rate)
            self.local_total_amount = self.master_id.currency_id.round(
                self.total_amount * self.master_id.exchange_rate)

    def unlink(self):
        for line in self:
            if line.stock_move_id:
                line.stock_move_id.statement_state = "N"
        return super(account_statement_line, self).unlink()

    def write(self, vals, ):
        res = super(account_statement_line, self).write(vals)
        for r in self:
            state = 'draft'
            if not r.master_id.line_ids.filtered(lambda x: x.state != 'done'):
                state = 'done'
            elif r.master_id.line_ids.filtered(lambda x: x.state == 'confirmed'):
                state = 'confirmed'
            r.master_id.state = state
        return res
