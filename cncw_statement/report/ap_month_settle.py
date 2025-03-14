# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_compare



class ap_monthly_settle(models.Model):
    _name = 'ap.monthly.settle'
    _rec_name='partner_id'
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
    # master_id = fields.Many2one('ap.ar.settle', '主档',ondelete="cascade")
    period_id = fields.Many2one('account.period', '期别', ondelete="restrict")
    partner_id = fields.Many2one('res.partner', '供应商', ondelete="restrict")
    currency_id = fields.Many2one('res.currency', '币别', ondelete="restrict")
    code = fields.Char('供应商', help='导资料用')

    begin_stock = fields.Float('期初应付(入库)',  digits='Product Price',)
    in_stock = fields.Float('本期应付款(入库)',  digits='Product Price',)
    out_stock = fields.Float('本期已付款(入库)',  digits='Product Price',)
    end_stock = fields.Float('期末应付款(入库)',  digits='Product Price',)
    year_begin_stock = fields.Float('年初应付款(入库)',  digits='Product Price',)
    year_in_stock = fields.Float('年累应付款(入库)',  digits='Product Price',)
    year_out_stock = fields.Float('年累已付款(入库)',  digits='Product Price',)

    begin_invoice = fields.Float('期初应付(发票)',  digits='Product Price',)
    in_invoice = fields.Float('本期应付款(发票)',  digits='Product Price',)
    out_invoice = fields.Float('本期已付款(发票)',  digits='Product Price',)
    end_invoice = fields.Float('期末应付款(发票)',  digits='Product Price',)
    year_begin_invoice = fields.Float('年初应付款(发票)',  digits='Product Price',)
    year_in_invoice = fields.Float('年累应付款(发票)',  digits='Product Price',)
    year_out_invoice = fields.Float('年累已付款(发票)',  digits='Product Price',)

    def init(self):
        self._cr.execute("""
                    CREATE OR REPLACE FUNCTION ap_monthly_settle(
                    period_id_t integer,
                    preperiod_id_t integer,
                    uid_t integer)
                      RETURNS void AS
                    $BODY$
                    --DROP FUNCTION ap_monthly_settle_zj(integer,integer,integer)
                    -- select ap_monthly_settle_zj(10,9,1)
                    declare date_start_t TIMESTAMP;
                        date_stop_t  TIMESTAMP;
                    begin

                    select date_start,date_stop into date_start_t,date_stop_t from account_period where id=period_id_t;
                    create temp table ap_monthly_settle_t(
                            period_id integer,
                            partner_id integer,
                            currency_id integer,
                            begin_stock numeric,--期初应付(入库)
                            in_stock numeric,--本期应付款(入库)
                            out_stock numeric,--本期已付款(入库)
                            end_stock numeric,--期末应付款(入库)
                            year_begin_stock numeric,--年初应付款(入库)
                            year_in_stock numeric,--年累应付款(入库)
                            year_out_stock numeric,--年累已付款(入库)

                            begin_invoice numeric,--期初应付(发票)
                            in_invoice numeric,--本期应付款(发票)
                            out_invoice numeric,--本期已付款(发票)
                            end_invoice numeric,--期末应付款(发票)
                            year_begin_invoice numeric,--年初应付款(发票)
                            year_in_invoice numeric,--年累应付款(发票)
                            year_out_invoice numeric,--年累已付款(发票)
                            create_date TIMESTAMP,
                            create_uid integer
                            );
                      ---一、从发票角度
                      ---1.取上期期末数作为本期初 及年初数 年累计货款 年累计付款
                      insert into ap_monthly_settle_t(year_begin_invoice,year_in_invoice,year_out_invoice,begin_invoice,
                          year_begin_stock,year_in_stock,year_out_stock,begin_stock,
                          partner_id,currency_id)
                      select case when EXTRACT(MONTH from  date_start_t)=1 then end_invoice  else year_begin_invoice end as year_begin_invoice,
                         case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_invoice end as year_in_invoice,
                         case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_invoice end as year_out_invoice,
                         end_invoice,
                         case when EXTRACT(MONTH from  date_start_t)=1 then end_stock else year_begin_stock end as year_begin_stock,
                         case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_stock end as year_in_stock,
                         case when EXTRACT(MONTH from  date_start_t)=1 then 0 else year_out_stock end as year_out_stock,
                         end_stock,
                         partner_id,currency_id
                    from ap_monthly_settle
                       where period_id=preperiod_id_t;

                      ---2.本月开票数
                       insert into ap_monthly_settle_t(partner_id,currency_id,in_invoice)
                       select partner_id,currency_id,
                          sum(coalesce(total_invoice_amount,0)) as in_invoice
                     from cncw_invoice_move
                    where state in ('open','paid')
                      and date between date_start_t and date_stop_t
                      and move_type in ('in_invoice','out_refund')
                    group by partner_id,currency_id;

                      ---3.本月付款数
                       insert into ap_monthly_settle_t(partner_id,currency_id,out_invoice,out_stock)
                       select partner_id,currency_id,
                          sum(coalesce(payment_amount,0)) as out_invoice,
                          sum(coalesce(payment_amount,0)) as out_stock
                     from account_pay
                    where state='done'
                      and date between date_start_t and date_stop_t
                    group by partner_id,currency_id;

                      ---4.计算期末未付数



                      ---二、从采购入库明细角度
                     ---2.本月入库数
                     insert into ap_monthly_settle_t(partner_id,currency_id,in_stock)
                     select b.partner_id,e.currency_id,coalesce(a.amount_total,0)+coalesce(a.adjust_amount,0)+coalesce(a.freight_amount,0) as amount_total
                       from stock_move a left join  stock_picking b on a.picking_id=b.id
                                 left join  stock_picking_type c on b.picking_type_id= c.id
                                 left join  purchase_order_line d on a.purchase_line_id=d.id
                                 left join  purchase_order e on d.order_id=e.id
                      where c.table_name in ('purchase_half_storage',
                                    'purchase_half_storage_return',
                                    'purchase_product_storage',
                                    'purchase_product_storage_return',
                                    'purchase_storage',
                                    'purchase_storage_return',
                                    'purchase_wire_storage',
                                    'purchase_wire_storage_return',
                                    'purchase_outsourcing_storage',
                                    'purchase_outsourcing_storage_return',
                                    'purchase_rebate',
                                    'mrp_outsourcing_storage_return',
                                    'mrp_outsourcing_storage')
                        and b.date_done between date_start_t and date_stop_t
                        and b.state='done';


                    update ap_monthly_settle_t set period_id=period_id_t,create_uid=uid_t,create_date=now() at time zone 'UTC';
                    delete from ap_monthly_settle where period_id=period_id_t;
                    insert into ap_monthly_settle(period_id,partner_id,currency_id,create_uid,create_date,
                        begin_stock,in_stock,out_stock,end_stock,year_begin_stock,year_in_stock,year_out_stock,
                        begin_invoice,in_invoice,out_invoice,end_invoice,year_begin_invoice,year_in_invoice,year_out_invoice)
                    select period_id,partner_id,currency_id,uid_t,create_date,
                       sum(coalesce(begin_stock,0)) as begin_stock,
                       sum(coalesce(in_stock,0)) as in_stock,
                       sum(coalesce(out_stock,0)) as out_stock,
                       sum(coalesce(begin_stock,0)+coalesce(in_stock,0)-coalesce(out_stock,0)) as end_stock,
                       sum(coalesce(year_begin_stock,0)) as year_begin_stock,
                       sum(coalesce(year_in_stock,0)) as year_in_stock,
                       sum(coalesce(year_out_stock,0)) as year_out_stock,

                       sum(coalesce(begin_invoice,0)) as begin_invoice,
                       sum(coalesce(in_invoice,0)) as in_invoice,
                       sum(coalesce(out_invoice,0)) as out_invoice,
                       sum(coalesce(begin_invoice,0)+coalesce(in_invoice,0)-coalesce(out_invoice,0)) as end_invoice,
                       sum(coalesce(year_begin_invoice,0)) as year_begin_invoice,
                       sum(coalesce(year_in_invoice,0)) as year_in_invoice,
                       sum(coalesce(year_out_invoice,0)) as year_out_invoice
                      from ap_monthly_settle_t
                     group by period_id,partner_id,currency_id,uid_t,create_date;

                    drop table ap_monthly_settle_t;
                    end;
                    $BODY$
                    LANGUAGE plpgsql VOLATILE
                    COST 100;

                """)


