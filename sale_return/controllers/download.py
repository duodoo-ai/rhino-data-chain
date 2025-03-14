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

class SaleReturnXlsRrport(http.Controller):
    
    @http.route('/web/export/sale_return_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)
        if data['type'] == 'return':
            return_objs = request.env['sale.return'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook=xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty= workbook.add_format({'font_size': 14,'valign': 'vcenter','align':'center','font':'Arial','bold':True})
            font_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'Arial'})
            table_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'center','font':'Arial','border':1,'bold':True})
            right_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'right','font':'Arial','valign' : 'vcenter'})
            left_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'left','font':'Arial','valign' : 'vcenter'})
            
            for sale_return in return_objs:
                worksheet = workbook.add_worksheet(sale_return.name or "销售退货单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                
                worksheet.merge_range(0,0, 1, 7, '销售退货单',title_sty)
                worksheet.write(2,0, "退货单号："+(sale_return.name or ''),font_sty)
                worksheet.write(3,0, "源销售订单："+(sale_return.sale_id.name or ''),font_sty)
                worksheet.write(4,0, "客户："+(sale_return.partner_id.name or ''),font_sty)
                worksheet.write(5,0, "退货说明："+(sale_return.note or ''),font_sty)
                
                worksheet.write(2,5, "单据日期："+str(sale_return.return_date or ''),font_sty)
                worksheet.write(3,5, "人员："+(sale_return.user_id.name or ''),font_sty)
                worksheet.write(4,5, "部门："+(sale_return.department_id.name or ''),font_sty)
                
                worksheet.write('A8', "产品", table_sty)
                worksheet.write('B8', "说明", table_sty)
                worksheet.write('C8', "已送货", table_sty)
                worksheet.write('D8', "退货数量", table_sty)
                worksheet.write('E8', "单位", table_sty)
                worksheet.write('F8', "单价", table_sty)
                worksheet.write('G8', "税率", table_sty)
                worksheet.write('H8', "小计", table_sty)
                
                row_count=8
                for line in sale_return.lines:
                    tax_name=','.join([tax.name for tax in line.tax_id])
                    worksheet.write(row_count, 0, line.product_id.name or '',left_sty)                    
                    worksheet.write(row_count, 1, line.name or '',left_sty)
                    worksheet.write(row_count, 2, line.qty_delivered,right_sty)
                    worksheet.write(row_count, 3, line.return_qty,right_sty)
                    worksheet.write(row_count, 4, line.product_uom.name,right_sty)
                    worksheet.write(row_count, 5, line.price_unit,right_sty)
                    worksheet.write(row_count, 6, tax_name,left_sty)
                    worksheet.write(row_count, 7, line.price_subtotal,right_sty)
                    row_count+=1
                worksheet.write(row_count, 2, "未税金额：",font_sty) 
                worksheet.write(row_count, 3, sale_return.amount_untaxed,font_sty)
                worksheet.write(row_count, 4, "税率设置：",font_sty) 
                worksheet.write(row_count, 5, sale_return.amount_tax,font_sty)
                worksheet.write(row_count, 6, "合计：",font_sty) 
                worksheet.write(row_count, 7, sale_return.amount_total,font_sty)
                worksheet.set_column('A:H', 12)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '销售退货'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.xls'
            httpheaders = [
                ('Content-Type', 'application/vnd.ms-excel'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            response=request.make_response(None, headers=httpheaders)
            response.stream.write(generated_file)
            response.set_cookie('fileToken', token)
            return response
            