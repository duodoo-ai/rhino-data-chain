# -*- encoding: utf-8 -*-
from odoo.http import request
import io
import datetime
try:
    import json
except ImportError:
    import simplejson as json
from odoo.http import content_disposition
from odoo import http
import xlsxwriter

class SaleChangeXlsRrport(http.Controller):
        
    @http.route('/web/export/sale_change_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)
        if data['type'] == 'change':
            change_objs = request.env['sale.change'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook=xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty= workbook.add_format({'font_size': 14,'valign': 'vcenter','align':'center','font':'Arial','bold':True})
            
            font_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'Arial'})
            
            table_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'center','font':'Arial','border':1,'bold':True})
            right_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'right','font':'Arial','valign' : 'vcenter'})
            left_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'left','font':'Arial','valign' : 'vcenter'})
            
            for change in change_objs:
                worksheet = workbook.add_worksheet(change.name or "销售变更单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                
                worksheet.merge_range(0,0, 1, 12, '销售变更单',title_sty)
                worksheet.write(2,0, "变更单号："+(change.name or ''),font_sty)
                worksheet.write(3,0, "源销售订单："+(change.old_order_id.name or ''),font_sty)
                worksheet.write(4,0, "客户："+(change.partner_id.name or ''),font_sty)
                worksheet.write(5,0, "开票地址："+(change.partner_invoice_id.name or ''),font_sty)
                worksheet.write(6,0, "交货地址："+(change.partner_shipping_id.name or ''),font_sty)
                worksheet.write(7,0, "变更人："+(change.change_user_id.name or ''),font_sty)
                
                
                worksheet.write(2,7, "单据日期："+str(change.date_order or ''),font_sty)
                worksheet.write(3,7, "原付款条款："+(change.payment_term_id.name or ''),font_sty)
                worksheet.write(4,7, "变更付款条款："+(change.change_payment_term_id.name or ''),font_sty)
                worksheet.write(5,7, "原交货日期："+str(change.commitment_date or ''),font_sty)
                worksheet.write(6,7, "变更交货日期："+str(change.change_commitment_date or ''),font_sty)
                worksheet.write(7,7, "变更说明："+(change.note or ''),font_sty)
                
                worksheet.write('A10', "产品", table_sty)
                worksheet.write('B10', "说明", table_sty)
                worksheet.write('C10', "原数量", table_sty)
                worksheet.write('D10', "变更后数量", table_sty)
                worksheet.write('E10', "已发货", table_sty)
                worksheet.write('F10', "已开票", table_sty)
                worksheet.write('G10', "单位", table_sty)
                worksheet.write('H10', "单价", table_sty)
                worksheet.write('I10', "变更后单价", table_sty)
                worksheet.write('J10', "税率", table_sty)
                worksheet.write('K10', "变更后税率", table_sty)
                worksheet.write('L10', "折扣", table_sty)
                worksheet.write('M10', "小计", table_sty)
                
                row_count=10
                for line in change.order_line:
                    tax_name=','.join([tax.name for tax in line.tax_id])
                    change_tax_name=','.join([tax.name for tax in line.change_tax_id])
                    worksheet.write(row_count, 0, line.product_id.name or '',left_sty)                    
                    worksheet.write(row_count, 1, line.name or '',left_sty)
                    worksheet.write(row_count, 2, line.product_uom_qty,right_sty)
                    worksheet.write(row_count, 3, line.change_product_uom_qty,right_sty)
                    worksheet.write(row_count, 4, line.qty_delivered,right_sty)
                    worksheet.write(row_count, 5, line.qty_invoiced,right_sty)
                    worksheet.write(row_count, 6, line.product_uom.name,left_sty)
                    worksheet.write(row_count, 7, line.price_unit,right_sty)
                    worksheet.write(row_count, 8, line.change_price_unit,right_sty)
                    worksheet.write(row_count, 9, tax_name,left_sty)
                    worksheet.write(row_count, 10, change_tax_name,left_sty)
                    worksheet.write(row_count, 11, line.discount,right_sty)
                    worksheet.write(row_count, 12, line.price_subtotal,right_sty)
                    row_count+=1
                worksheet.write(row_count, 7, "未税金额：",font_sty) 
                worksheet.write(row_count, 8, change.amount_untaxed,font_sty)
                worksheet.write(row_count, 9, "税率设置：",font_sty) 
                worksheet.write(row_count, 10, change.amount_tax,font_sty)
                worksheet.write(row_count, 11, "合计：",font_sty) 
                worksheet.write(row_count, 12, change.amount_total,font_sty)
                worksheet.set_column('A:A', 13)
                worksheet.set_column('B:B', 15)
                worksheet.set_column('C:I', 8)
                worksheet.set_column('J:K', 17)
                worksheet.set_column('L:M', 7)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '销售变更'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.xls'
            httpheaders = [
                ('Content-Type', 'application/vnd.ms-excel'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            response=request.make_response(None, headers=httpheaders)
            response.stream.write(generated_file)
            response.set_cookie('fileToken', token)
            return response