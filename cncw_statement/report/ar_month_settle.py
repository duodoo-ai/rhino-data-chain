# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_compare


class ar_monthly_settle(models.Model):
    _name = 'ar.monthly.settle'
    _description = '供应商帐款查询'

    @api.depends('period_id', 'partner_id')
    def name_get(self):
        res = []
        for record in self:
            name = ''
            if record.period_id:
                name = '%s' % (record.period_id.name,)
            if record.partner_id:
                name = '%s-%s' % (name, record.partner_id.name)
            res.append((record.id, name))
        return res

    # master_id = fields.Many2one('ap.ar.settle', '主档', ondelete="cascade")
    period_id = fields.Many2one('account.period', '期别', ondelete="restrict")
    partner_id = fields.Many2one('res.partner', '客户', ondelete="restrict")
    currency_id = fields.Many2one('res.currency', '币别', ondelete="restrict")
    code = fields.Char('客户编号', default=False)

    begin_stock = fields.Float('期初应收款(销售)',  digits='Product Price',)
    in_stock = fields.Float('本期应收款(销售)',  digits='Product Price',)
    out_stock = fields.Float('本期已收款(销售)',  digits='Product Price',)
    end_stock = fields.Float('期末应收款(销售)',  digits='Product Price',)
    year_begin_stock = fields.Float('年初应收款(销售)',  digits='Product Price',)
    year_in_stock = fields.Float('年累应收款(销售)',  digits='Product Price',)
    year_out_stock = fields.Float('年累已收款(销售)',  digits='Product Price',)

    begin_invoice = fields.Float('期初应收(发票)',  digits='Product Price',)
    in_invoice = fields.Float('本期应收款(发票)',  digits='Product Price',)
    out_invoice = fields.Float('本期已收款(发票)',  digits='Product Price',)
    end_invoice = fields.Float('期末应收款(发票)',  digits='Product Price',)
    year_begin_invoice = fields.Float('年初应收款(发票)',  digits='Product Price',)
    year_in_invoice = fields.Float('年累应收款(发票)',  digits='Product Price',)
    year_out_invoice = fields.Float('年累已收款(发票)',  digits='Product Price',)

    def init(self):
        self._cr.execute("""
                CREATE OR REPLACE FUNCTION ar_monthly_settle(
                     period_id_t integer,
                    preperiod_id_t integer,
                    uid_t integer)
                  RETURNS void AS
                $BODY$
                --DROP FUNCTION ar_monthly_settle_zj(integer,integer,integer)
                -- select ar_monthly_settle_zj(10,9,1)
                declare date_start_t TIMESTAMP;
                    date_stop_t  TIMESTAMP;
                begin

                select date_start,date_stop into date_start_t,date_stop_t from account_period where id=period_id_t;
                create temp table ar_monthly_settle_t(
                        period_id integer,
                        partner_id integer,
                        currency_id integer,
                        begin_stock numeric,--期初应收(入库)
                        in_stock numeric,--本期应收款(入库)
                        out_stock numeric,--本期已收款(入库)
                        end_stock numeric,--期末应收款(入库)
                        year_begin_stock numeric,--年初应收款(入库)
                        year_in_stock numeric,--年累应收款(入库)
                        year_out_stock numeric,--年累已收款(入库)

                        begin_invoice numeric,--期初应收(发票)
                        in_invoice numeric,--本期应收款(发票)
                        out_invoice numeric,--本期已收款(发票)
                        end_invoice numeric,--期末应收款(发票)
                        year_begin_invoice numeric,--年初应收款(发票)
                        year_in_invoice numeric,--年累应收款(发票)
                        year_out_invoice numeric,--年累已收款(发票)

                        adjust_amount numeric,--调整金额(发票)
                        create_date TIMESTAMP,
                        create_uid integer
                        );
                  ---一、从发票角度
                  ---1.取上期期末数作为本期初 及年初数 年累计货款 年累计收款
                  insert into ar_monthly_settle_t(year_begin_invoice,year_in_invoice,year_out_invoice,begin_invoice,
                              year_begin_stock,year_in_stock,year_out_stock,begin_stock,
                              partner_id,currency_id)
                  select case when EXTRACT(MONTH from  date_start_t)=1 then end_invoice  else year_begin_invoice end as year_begin_invoice,
                     case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_in_invoice end as year_in_invoice,
                     case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_invoice end as year_out_invoice,
                     end_invoice,
                     case when EXTRACT(MONTH from  date_start_t)=1 then end_stock else year_begin_stock end as year_begin_stock,
                     case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_in_stock end as year_in_stock,
                     case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_stock end as year_out_stock,
                     end_stock,
                     partner_id,currency_id
                from ar_monthly_settle
                   where period_id=preperiod_id_t;

                  ---2.本月开票数
                   insert into ar_monthly_settle_t(partner_id,currency_id,in_invoice,adjust_amount)
                   select partner_id,currency_id,
                      sum(coalesce(amount_total_signed,0)+coalesce(adjust_amount,0)) as in_invoice,sum(coalesce(adjust_amount,0)) as adjust_amount
                 from cncw_invoice_move
                where state in ('open','paid')
                  and date between date_start_t and date_stop_t
                  and move_type in ('out_invoice','out_refund')
                group by partner_id,currency_id;

                  ---3.本月收款数
                   insert into ar_monthly_settle_t(partner_id,currency_id,out_invoice,out_stock)
                   select partner_id,currency_id,
                      sum(coalesce(receive_amount,0)) as out_invoice,
                      sum(coalesce(receive_amount,0)) as out_stock
                 from account_receive
                where state='done'
                  and date between date_start_t and date_stop_t
                group by partner_id,currency_id;

                ---3-2.本月付款数(从供应商发票款冲销)
                       insert into ar_monthly_settle_t(partner_id,currency_id,out_invoice,out_stock)
                           select a.sub_account_id as partner_id,b.currency_id,
                          sum(coalesce(a.amount,0)) as out_invoice,
                          sum(coalesce(a.amount,0)) as out_stock
                     from account_pay_offset_line a
                     left join account_pay b on a.master_id=b.id
                     left join cncw_invoice_move c on c.id=a.invoice_id
                    where b.state='done' and c.move_type in ('out_invoice','in_refund')
                      and b.date between date_start_t and date_stop_t
                    group by a.sub_account_id,b.currency_id;

                  ---4.计算期末未收数
                  -- update  ar_monthly_settle_t set end_invoice=coalesce(begin_invoice,0)+coalesce(in_invoice,0)-coalesce(out_invoice,0);


                  ---二、从销售出库明细角度
                 ---2.本月出库数
                 /*
                 # insert into ar_monthly_settle_t(partner_id,currency_id,in_stock)
                 # select b.partner_id,e.currency_id,coalesce(a.amount_total,0)+coalesce(a.adjust_amount,0)+coalesce(a.freight_amount,0) as amount_total
                 #   from stock_move a left join  stock_picking b on a.picking_id=b.id
                 #             left join  stock_picking_type c on b.picking_type_id=c.id
                 #             left join  sale_order_line d on a.sale_line_id=d.id
                 #             left join  sale_order e on d.order_id=e.id
                 #  where c.table_name in ('sale_return_storage','stock_delivery','stock_sample','sale_rebate')
                 #    and to_date(to_char(b.date_done,'yyyy-mm-dd'),'yyyy-mm-dd') between date_start_t and date_stop_t
                 #    and b.state='done';
                 */

                 insert into ar_monthly_settle_t(partner_id,currency_id,in_stock)
                 select b.partner_id,f.currency_id,coalesce(a.amount_total,0) as amount_total
                   from stock_move a left join  stock_picking b on a.picking_id=b.id
                             left join  stock_picking_type c on b.picking_type_id=c.id
                             left join  sale_order_line d on a.sale_line_id=d.id
                             left join  sale_order e on d.order_id=e.id
                             left join  product_pricelist f on e.pricelist_id=f.id
                  where c.table_name in ('sale_return_storage','stock_delivery','stock_sample','sale_rebate')
                    and to_date(to_char(b.date_done,'yyyy-mm-dd'),'yyyy-mm-dd') between date_start_t and date_stop_t
                    and b.state='done' and a.is_gift is not True;
                  --调整费用
                insert into ar_monthly_settle_t(partner_id,currency_id,in_stock)
                select b.partner_id,b.currency_id,coalesce(a.adjust_amount,0) as in_stock
                  from account_statement_line a left join account_statement b on a.master_id=b.id
                 where to_date(to_char(b.date,'yyyy-mm-dd'),'yyyy-mm-dd') between date_start_t and date_stop_t
                   and b.state='done'
                   and b.statement_type='S'
                   and coalesce(a.adjust_amount,0)<>0.0;
                 --运费
                insert into ar_monthly_settle_t(partner_id,currency_id,in_stock)
                select b.partner_id,b.currency_id,coalesce(a.amount,0) as in_stock
                  from account_statement_line a left join account_statement b on a.master_id=b.id
                 where to_date(to_char(b.date,'yyyy-mm-dd'),'yyyy-mm-dd') between date_start_t and date_stop_t
                   and b.state='done'
                   and b.statement_type='S'
                   and a.statement_source='statement_source'
                   and coalesce(a.amount,0)<>0;

                update ar_monthly_settle_t set period_id=period_id_t,create_uid=uid_t,create_date=now() at time zone 'UTC';
                delete from ar_monthly_settle where period_id=period_id_t;
                insert into ar_monthly_settle(period_id,partner_id,currency_id,create_uid,create_date,
                    begin_stock,in_stock,out_stock,end_stock,year_begin_stock,year_in_stock,year_out_stock,
                    begin_invoice,in_invoice,out_invoice,end_invoice,year_begin_invoice,year_in_invoice,year_out_invoice
                    )

                select period_id,partner_id,currency_id,uid_t,create_date,
                   sum(coalesce(begin_stock,0)) as begin_stock,
                   sum(coalesce(in_stock,0)) as in_stock,
                   sum(coalesce(out_stock,0)) as out_stock,
                   sum(coalesce(begin_stock,0)+coalesce(in_stock,0)-coalesce(out_stock,0)) as end_stock,
                   sum(coalesce(year_begin_stock,0)) as year_begin_stock,

                   case when EXTRACT(MONTH from  date_start_t)=1 then sum(coalesce(in_stock,0)) else sum(coalesce(year_in_stock,0)) + sum(coalesce(in_stock,0)) end as year_in_stock,
                   case when EXTRACT(MONTH from  date_start_t)=1 then sum(coalesce(out_stock,0)) else sum(coalesce(year_out_stock,0)) + sum(coalesce(out_stock,0)) end as year_out_stock,

                   -- sum(coalesce(year_in_stock,0)) as year_in_stock,
                   -- sum(coalesce(year_out_stock,0)) as year_out_stock,

                   sum(coalesce(begin_invoice,0)) as begin_invoice,
                   sum(coalesce(in_invoice,0)) as in_invoice,
                   sum(coalesce(out_invoice,0)) as out_invoice,
                   sum(coalesce(begin_invoice,0)+coalesce(in_invoice,0)-coalesce(out_invoice,0)-coalesce(adjust_amount,0)) as end_invoice,
                   sum(coalesce(year_begin_invoice,0)) as year_begin_invoice,

                   case when EXTRACT(MONTH from  date_start_t)=1 then sum(coalesce(in_invoice,0)) else sum(coalesce(year_in_invoice,0)) + sum(coalesce(in_invoice,0)) end as year_in_invoice,
                   case when EXTRACT(MONTH from  date_start_t)=1 then sum(coalesce(out_invoice,0)) else sum(coalesce(year_out_invoice,0)) + sum(coalesce(out_invoice,0)) end as year_out_invoice

                   --sum(coalesce(year_in_invoice,0)) as year_in_invoice,
                   --sum(coalesce(year_out_invoice,0)) as year_out_invoice,
                   --sum(coalesce(begin_stock,0)+coalesce(in_stock,0)-coalesce(out_stock,0))-sum(coalesce(begin_invoice,0)+coalesce(in_invoice,0)-coalesce(out_invoice,0)) as end_no_invoice_in_stock,
                   --sum(coalesce(adjust_amount,0)) as adjust_amount --调整金额


                  from ar_monthly_settle_t
                 group by period_id,partner_id,currency_id,uid_t,create_date;

                 --update ar_monthly_settle a set partner_user_id=coalesce(b.user_id,null)
                 --from res_partner b where b.id = a.partner_id;

                drop table ar_monthly_settle_t;
                end;
                $BODY$
                LANGUAGE plpgsql VOLATILE
                COST 100;
        """)



