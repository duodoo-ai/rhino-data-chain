# -*- encoding: utf-8 -*-
import time
from lxml import etree
from odoo import models, fields, api, _
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.translate import _
from odoo.exceptions import except_orm
from odoo.tools import float_compare, float_round
from odoo.exceptions import UserError
#import odoo.addons.decimal_precision as dp

class account_statement_order_cost_wizard(models.TransientModel):
    _name = 'account.statement.order.cost.wizard'
    _description = '订单费用向导'

    master_id = fields.Many2one('account.statement', '对帐单', )
    is_all_check = fields.Boolean('全选', default=False)
    partner_id = fields.Many2one('res.partner', string='客户编码', related='master_id.partner_id', readonly=True, )
    statement_source = fields.Selection([('C', '模具费'),
                                         ('D', 'PPAP费用'),
                                         ('E', '第三方检测费用')], '对帐类型', )
    wizard_ids = fields.One2many('account.statement.order.cost.wizard.line', 'wizard_id', '明细', )

    @api.model
    def default_get(self, fields):
        if self._context is None:
            self._context = {}
        res = super(account_statement_order_cost_wizard, self).default_get(fields)
        master_id = self._context.get('active_id', [])
        active_model = self._context.get('active_model')

        if not master_id:
            return res
        assert active_model in ('account.statement'), '不是正确的来源对象！'
        res.update(active_id=master_id)
        items = []
        res.update(wizard_ids=items)
        return res

    @api.onchange('is_all_check')
    def onchange_is_all_check(self):
        self.ensure_one()
        for line in self.wizard_ids:
            line.is_check = self.is_all_check

    @api.onchange('statement_source')
    def _onchange_data(self):
        items = []
        domain = [('state', 'not in', ('draft', 'cancel')),
                  ('order_id.partner_id', '=', self.partner_id.id)]
        order_line_ids = self.env['sale.order.line'].search(domain)
        if self.statement_source and order_line_ids > 0:
            if self.statement_source == 'C':
                for r in order_line_ids.filtered(
                        lambda x: x.surplus_mold_cost > 0.00 and x.order_id.partner_id == self.partner_id):
                    item = dict(sale_line_id=r.id,
                                product_id=r.product_id and r.product_id.id or False,
                                surplus_mold_cost=r.surplus_mold_cost)
                    items.append(item)
            elif self.statement_source == 'D':
                for r in order_line_ids.filtered(
                        lambda x: x.surplus_ppap_cost > 0.00 and x.order_id.partner_id == self.partner_id):
                    item = dict(sale_line_id=r.id,
                                product_id=r.product_id and r.product_id.id or False,
                                surplus_ppap_cost=r.surplus_ppap_cost)
                    items.append(item)
            elif self.statement_source == 'E':
                for r in order_line_ids.filtered(
                        lambda x: x.surplus_third_inspection_cost > 0.00 and x.order_id.partner_id == self.partner_id):
                    item = dict(sale_line_id=r.id,
                                product_id=r.product_id and r.product_id.id or False,
                                surplus_third_inspection_cost=r.surplus_third_inspection_cost)
                    items.append(item)
        self.wizard_ids = items

    def action_confirm(self):
        self.ensure_one()
        statement_ids = []
        selects = self.wizard_ids.filtered(lambda x: x.is_check ==True)
        if not selects:
            raise UserError(_('错误提示!未选择对账数据，请选择完成后再确认。'))
        amount = 0
        for line in selects:
            if self.statement_source == 'C':
                self.amount = line.sale_line_id.mold_cost
                unchecked_amount = line.sale_line_id.remaining_mold_cost
            elif self.statement_source == 'D':
                unchecked__amount = line.sale_line_id.remaining_ppap_cost
                amount = line.sale_line_id.ppap_cost
            elif self.statement_source == 'E':
                unchecked__amount = line.sale_line_id.remaining_third_inspection_cost
                amount = line.sale_line_id.third_inspection_cost
            currency_rate = 1
            currency_rate = self.master_id.currency_rate
            item = dict()

        return {'type': 'ir.actions.act_window_close'}

    def wizard_view(self):
        view = self.env.ref('cncw_statement.form_account_statement_order_cost_wizard')
        return {
            'name': _('订单费用'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.statement.order.cost.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': self.env.context,
        }


class account_settlement_order_cost_wizard_line(models.TransientModel):
    _name = 'account.statement.order.cost.wizard.line'

    is_check = fields.Boolean('选择', default=False)
    wizard_id = fields.Many2one('account.statement.order.cost.wizard', '主档', ondelete="cascade")
    sale_line_id = fields.Many2one('sale.order.line', '订单明细')
    order_id = fields.Many2one('sale.order', related='sale_line_id.order_id', string='订单编号', readonly=True, )
    product_id = fields.Many2one('product.product', '产品编码')
    product_name = fields.Char(related='product_id.name', string='品名', readonly=True)
    # product_spec = fields.Char(related='product_id.spec', string='规格', readonly=True)
    mold_cost = fields.Float('模具费',  digits='Product Price', readonly=True)
    ppap_cost = fields.Float('PPAP费用',  digits='Product Price', readonly=True)
    third_inspection_cost = fields.Float('第三方检测费用', digits=(16, 2), readonly=True)
