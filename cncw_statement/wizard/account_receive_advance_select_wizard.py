# -*- encoding: utf-8 -*-
import time
from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.tools import float_compare, float_round
from odoo.addons import base_cw
from odoo.exceptions import UserError



class account_receive_advance_select_wizard(models.TransientModel):
    _name = 'account.receive.advance.select.wizard'

    name = fields.Char(string=u"单据编号")
    active_id = fields.Integer(u"ActiveId")
    active_model = fields.Char(string=u"主档对象名", )
    is_all_check = fields.Boolean('全选', default=False)
    wizard_ids = fields.One2many('account.receive.advance.select.wizard.line', 'wizard_id', '明细', )

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(account_receive_advance_select_wizard, self).default_get(fields)
        active_id = self._context.get('active_id', False)
        active_model = self._context.get('active_model')
        if not active_id:
            return res
        if not active_model:
            return res
        res.update(name=self._context.get('name', False))
        res.update(active_id=active_id)
        res.update(active_model=active_model)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    def action_query(self):
        self.ensure_one()
        master_id = self.env[self.active_model].browse(self.active_id)
        domain = [('offset_state', '!=', 'A'), ('currency_id', '=', master_id.currency_id.id)]
        domain += [('partner_id', '=', master_id.partner_id.id)]
        exists = master_id.line_ids.mapped('advance_id')
        if exists:
            domain += [('id', 'not in', exists.ids)]
        results = self.env['account.advance'].search(domain)
        items = []
        for x in results:
            items.append((0, 0, dict(advance_id=x.id)))
        self.wizard_ids = False
        if items:
            self.write(dict(wizard_ids=items))
        return self.wizard_view()

    def action_confirm(self):
        self.ensure_one()
        selects = self.wizard_ids.filtered(lambda m: m.is_check == True)
        if not selects:
            raise UserError(_(u"提示!请选预收！"))
        master_id = self.env[self.active_model].browse(self.active_id)
        items = []
        category_id = self.env.ref('cncw_statement.account_receive_category_advance_use')
        for line in selects:
            item = dict(advance_id=line.advance_id.id,
                        amount=line.remaining_amount,
                        receive_category_id=category_id and category_id.id or False,
                        account_id=line.account_id.id,
                        sub_account_id=line.sub_account_id and line.sub_account_id.id or False,
                        dc_type='D' if line.dc_type == 'C' else 'D')
            items.append((0, 0, item))
        if items:
            master_id.write(dict(line_ids=items))
        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_receive_advance_select_wizard')
        return {
            'name': _('预收使用选择向导'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.receive.advance.select.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


# ===============================================================================
# # 类名:account_pay_add_invoice_wizard_line
# # Copyright(c): Hailun
# # 功能描述: 收款加明细向导
# # 创 建 人: Sunshine
# # 创建日期: 2023-03-03
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class account_receive_advance_select_wizard_line(models.TransientModel):
    _name = 'account.receive.advance.select.wizard.line'

    @api.depends('date_due')
    def _compute_overdue_days(self):
        for record in self:
            record.overdue_days = 0
            if record.date_due:
                record.overdue_days = base_cw.public.get_days_between_date(time.strftime("%Y-%m-%d"),
                                                                     fields.Datetime.to_string(record.date_due))

    is_check = fields.Boolean('选择', default=False)
    wizard_id = fields.Many2one('account.receive.advance.select.wizard', '主档', ondelete="cascade")
    advance_id = fields.Many2one('account.advance', '预收单号')
    receive_line_id = fields.Many2one('account.receive.line', string='收款单号', related='advance_id.res_id',
                                      store=False, readonly=True, copy=False)
    date = fields.Date('预收单日期', related='advance_id.date', readonly=True)
    amount = fields.Float('原币金额',  digits='Product Price', related='advance_id.amount', readonly=True)
    lc_amount = fields.Float('本币金额',  digits='Product Price', related='advance_id.lc_amount', readonly=True)
    received_amount = fields.Float('原币累计冲销',  digits='Product Price', related='advance_id.received_amount',
                                   readonly=True)
    lc_received_amount = fields.Float('本币累计冲销',  digits='Product Price',
                                      related='advance_id.lc_received_amount', readonly=True)
    remaining_amount = fields.Float('原币未冲销余额',  digits='Product Price',
                                    related='advance_id.remaining_amount', readonly=True)
    lc_remaining_amount = fields.Float('本币未冲销余额',  digits='Product Price',
                                       related='advance_id.lc_remaining_amount',
                                       readonly=True)
    offset_state = fields.Selection([('N', '未冲销'),
                                     ('P', '部分冲销'),
                                     ('A', '已完全冲销')],
                                    '冲销状态', related='advance_id.offset_state', readonly=True)
    account_id = fields.Many2one('cncw.account', '科目', related='advance_id.account_id', readonly=True)
    sub_account_id = fields.Many2one('res.partner', '科目辅助核算', related='advance_id.sub_account_id', readonly=True)
    dc_type = fields.Selection(base_cw.public.DC_TYPE, '借贷', related='advance_id.dc_type', readonly=True)
