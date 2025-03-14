# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from odoo import tools
from .. import public
from odoo.exceptions import UserError


class sale_order(models.Model):
    _inherit = 'sale.order'
    _description = '销售订单'

    @api.depends('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            # if not self.partner_id.partner_currency_id:
            #     raise  UserError("提示!客户资料币别不可为空!")
            self.partner_currency_id = self.partner_id.partner_currency_id
            # if not self.partner_id.account_tax_id:
            #     raise UserError("提示!客户资料税别不可为空!")
            self.tax_id = self.partner_id.account_tax_id
        else:
            self.tax_id = False

    exchange_rate = fields.Float('汇率', digits=(16, 3), default=1.0)
    partner_currency_id = fields.Many2one('res.currency', '币别')
    tax_id = fields.Many2one('account.tax', '税别',compute='onchange_partner_id',store=True,readonly=False,)
    payment_mode_id = fields.Many2one('payment.mode', '付款方式', ondelete="restrict")

    @api.onchange('tax_id')
    def onchange_tax_id(self):
        if self.tax_id:
            for line in self.order_line:
                line.tax_id = [(6, 0, (self.tax_id.id,))]

    def check_credit_limit(self):
        # if 参数判断，需要信用额度检查 才跑下一段：
        # 最好能移植到 partner 对象下
        for x in self:
            self._cr.execute("""
                                select partner_id,sum(coalesce(out_stock,0)) as out_stock_amount
						     ,sum(coalesce(return_amount,0)) as return_amount
						     ,sum(coalesce(rebate_amount,0)) as rebate_amount
						     ,sum(coalesce(fandian_amount,0)) as fandian_amount
						     ,sum(coalesce(policy_amount,0)) as policy_amount
						       ,sum(coalesce(local_checked_amount,0)) as checked_amount
						       ,sum(coalesce(invoiced_amount,0)) as invoiced_amount
						       ,sum(coalesce(received_amount,0)) as received_amount

                                               --,currency_id
						from (
								 select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
								     ,sum(coalesce(a.amount_total,0.0)) as out_stock

								   ,0.0::numeric as  return_amount
								   ,0.0::numeric as  rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								   ,0.0::numeric as local_checked_amount
								   ,0.0::numeric as invoiced_amount
								   ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('stock_delivery')

								    and b.state='done' and a.is_gift is not True
								    and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id
								   union

                                                                   select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
                                                                     ,0.0::numeric as  out_stock
								     ,sum(coalesce(a.amount_total,0.0)) as return_amount
								   ,0.0::numeric as  rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								   ,0.0::numeric as local_checked_amount
								   ,0.0::numeric as invoiced_amount
								   ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('sale_return_storage')

								    and b.state='done' and a.is_gift is not True
								   and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id

								   union
								   select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
                                                                     ,0.0::numeric as  out_stock
                                                                     ,0.0::numeric as  return_amount
								     ,sum(coalesce(a.amount_total,0.0)) as rebate_amount

								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								   ,0.0::numeric as local_checked_amount
								   ,0.0::numeric as invoiced_amount
								   ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('sale_rebate')

								    and b.state='done' and a.is_gift is not True
								   and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id
								   union

								    select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
                                                                     ,0.0::numeric as  out_stock
                                                                     ,0.0::numeric as  return_amount
								     , 0.0::numeric as rebate_amount

								   ,sum(coalesce(a.amount_total,0.0)) as  fandian_amount
								   ,0.0::numeric as  policy_amount
								   ,0.0::numeric as local_checked_amount
								   ,0.0::numeric as invoiced_amount
								   ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('sale_fandian')

								    and b.state='done' and a.is_gift is not True
								    and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id
								   union
                                                                  select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
                                                                     ,0.0::numeric as  out_stock
                                                                     ,0.0::numeric as  return_amount
								     , 0.0::numeric as rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,sum(coalesce(a.amount_total,0.0)) as  policy_amount
								   ,0.0::numeric as local_checked_amount
								   ,0.0::numeric as invoiced_amount
								   ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('customer_support_policy')

								    and b.state='done' and a.is_gift is not True
								    and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id
								   union

								   select b.partner_id,coalesce(e.partner_currency_id,8) as currency_id
								   ,0.0::numeric as  out_stock
								   ,0.0::numeric as  return_amount
								   ,0.0::numeric as  rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								 ,sum(coalesce(a.local_checked_amount,0.0)) as local_checked_amount
								 ,sum(coalesce(a.invoiced_amount,0.0)) as invoiced_amount
								 ,0.0::numeric received_amount
								   from stock_move a left join  stock_picking b on a.picking_id=b.id
										      left join  stock_picking_type c on b.picking_type_id=c.id
										      left join  sale_order_line d on a.sale_line_id=d.id
										      left join  sale_order e on d.order_id=e.id
								  where c.table_name in ('sale_return_storage','stock_delivery','customer_support_policy','sale_rebate','sale_fandian')
								   -- and to_date(to_char(b.date_done,'yyyy-mm-dd'),'yyyy-mm-dd') between date_start_t and date_stop_t
								    and b.state='done' and a.is_gift is not True
								    and b.partner_id={partner_id}
								  group by b.partner_id,e.partner_currency_id
								   union

								   ---3.本月收款数
								select partner_id,currency_id
								          ,0.0::numeric as  out_stock
								   ,0.0::numeric as  return_amount
								   ,0.0::numeric as  rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								          ,0.0::numeric as local_checked_amount
								          ,0.0::numeric as invoiced_amount
								       ,sum(coalesce(receive_amount,0)) as received_amount
								 from account_receive
								where state='done'
								  and partner_id={partner_id}
								group by partner_id,currency_id
								 union
								---3-2.本月付款数(从供应商发票款冲销)
								   select a.sub_account_id as partner_id,b.currency_id
								          ,0.0::numeric as  out_stock
								   ,0.0::numeric as  return_amount
								   ,0.0::numeric as  rebate_amount
								   ,0.0::numeric as  fandian_amount
								   ,0.0::numeric as  policy_amount
								          ,0.0::numeric as local_checked_amount
								          ,0.0::numeric as invoiced_amount
									  ,sum(coalesce(a.amount,0)) as received_amount
								     from account_pay_offset_line a
								     left join account_pay b on a.master_id=b.id
								     left join cncw_invoice_move c on c.id=a.invoice_id
								    where b.state='done' and c.type in ('out_invoice','in_refund')
								      and a.sub_account_id={partner_id}
								    group by a.sub_account_id,b.currency_id
						    ) bb
                                group by partner_id--,currency_id
            """.format(partner_id=x.partner_id.id))
            result = self._cr.fetchone()
            if result:
                x.partner_id.write(dict(
                                        out_stock_amount=result[1],
                                        return_amount=result[2],
                                        rebate_amount=result[3],
                                        fandian_amount=result[4],
                                        policy_amount=result[5],
                                        checked_amount=result[6],
                                        invoiced_amount=result[7],
                                        received_amount=result[8]
                                        ))

class sale_order_line(models.Model):
    _inherit = 'sale.order.line'

    real_price = fields.Float(compute='compute_real_price', string='真实价格', store=True)

    @api.depends('price_unit',)
    def compute_real_price(self):
        for line in self:
            line.real_price = line.price_unit

    def _compute_tax_id(self):
        for line in self:
            if line.order_id.partner_id and line.order_id.partner_id.account_tax_id:
                line.tax_id = [(6, 0, (line.order_id.partner_id.account_tax_id.id,))]
            else:
                super(sale_order_line, self)._compute_tax_id()
