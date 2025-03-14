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

class PurchaseChangeXlsRrport(http.Controller):
    
    @http.route('/web/export/purchase_change_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)
        if data['type'] == 'purchase_change':
            change_objs = request.env['purchase.change'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook=xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty= workbook.add_format({'font_size': 14,'valign': 'vcenter','align':'center','font':'Arial','bold':True})
            
            
            font_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'Arial'})
            
            table_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'center','font':'Arial','border':1,'bold':True})
            right_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'right','font':'Arial','valign' : 'vcenter'})
            left_sty = workbook.add_format({'text_wrap':True,'border': 1, 'font_size': 10, 'align': 'left','font':'Arial','valign' : 'vcenter'})
            
            for change in change_objs:
                worksheet = workbook.add_worksheet(change.name or "采购变更单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                
                worksheet.merge_range(0,0, 1, 8, '采购变更单',title_sty)
                worksheet.write(2,0, "采购变更单号："+(change.name or ''),font_sty)
                worksheet.write(3,0, "源采购订单："+(change.old_order_id.name or ''),font_sty)
                worksheet.write(4,0, "供应商："+(change.partner_id.name or ''),font_sty)
                worksheet.write(5,0, "供应商参考："+(change.partner_ref or ''),font_sty)
                worksheet.write(6,0, "变更人："+(change.change_user_id.name or ''),font_sty)
                
                worksheet.write(2,5, "单据日期："+str(change.date_order or ''),font_sty)
                worksheet.write(3,5, "原接收日期 ："+str(change.date_planned or ''),font_sty)
                worksheet.write(4,5, "变更接受日期："+str(change.change_date_planned or ''),font_sty)
                worksheet.write(5,5, "采购员："+(change.user_id.name or ''),font_sty)
                
                
                worksheet.write('A9', "产品", table_sty)
                worksheet.write('B9', "说明", table_sty)
                worksheet.write('C9', "原数量", table_sty)
                worksheet.write('D9', "变更后数量", table_sty)
                worksheet.write('E9', "单位", table_sty)
                worksheet.write('F9', "单价", table_sty)
                worksheet.write('G9', "变更后单价", table_sty)
                worksheet.write('H9', "税率", table_sty)
                worksheet.write('I9', "小计", table_sty)
                
                row_count=9
                for line in change.order_line:
                    tax_name=','.join([tax.name for tax in line.taxes_id])
                    worksheet.write(row_count, 0, line.product_id.name or '',left_sty)                    
                    worksheet.write(row_count, 1, line.name or '',left_sty)
                    worksheet.write(row_count, 2, line.product_qty,right_sty)
                    worksheet.write(row_count, 3, line.change_product_qty,right_sty)
                    worksheet.write(row_count, 4, line.product_uom.name,left_sty)
                    worksheet.write(row_count, 5, line.price_unit,right_sty)
                    worksheet.write(row_count, 6, line.change_price_unit,right_sty)
                    worksheet.write(row_count, 7, tax_name,left_sty)
                    worksheet.write(row_count, 8, line.price_subtotal,right_sty)
                    row_count+=1
                worksheet.write(row_count, 3, "未税金额：",font_sty) 
                worksheet.write(row_count, 4, change.amount_untaxed,font_sty)
                worksheet.write(row_count, 5, "税率设置：",font_sty) 
                worksheet.write(row_count, 6, change.amount_tax,font_sty)
                worksheet.write(row_count, 7, "合计：",font_sty) 
                worksheet.write(row_count, 8, change.amount_total,font_sty)
                worksheet.set_column('A:I', 12)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '采购变更'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.xls'
            httpheaders = [
                ('Content-Type', 'application/vnd.ms-excel'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            response=request.make_response(None, headers=httpheaders)
            response.stream.write(generated_file)
            response.set_cookie('fileToken', token)
            return response
    def IIf(self, b, s1, s2):
        if b:
            return s1
        return s2

    def num2chn(self, nin=None):
        cs = ('零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖', '◇', '分', '角', '圆', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿',
        '拾', '佰', '仟', '万')
        st = ''
        st1 = ''
        s = '%0.2f' % (nin)
        sln = len(s)
        if sln > 15:
            return None
        fg = (nin < 1)
        for i in range(0, sln - 3):
            ns = ord(s[sln - i - 4]) - ord('0')
            st = self.IIf((ns == 0) and (fg or (i == 8) or (i == 4) or (i == 0)), '', cs[ns]) + self.IIf(
                (ns == 0) and ((i != 8) and (i != 4) and (i != 0) or fg and (i == 0)), '', cs[i + 13]) + st
            fg = (ns == 0)
        fg = False
        for i in [1, 2]:
            ns = ord(s[sln - i]) - ord('0')
            st1 = self.IIf((ns == 0) and ((i == 1) or (i == 2) and (fg or (nin < 1))), '', cs[ns]) + self.IIf((ns > 0),
                            cs[i + 10],self.IIf((i == 2) or fg,'','整')) + st1
            fg = (ns == 0)
        st.replace('亿万', '万')
        return self.IIf(nin == 0, '零', st + st1)