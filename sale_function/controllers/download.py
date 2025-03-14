# -*- encoding: utf-8 -*-
from odoo.http import request
import io
import os
import datetime
try:
    import json
except ImportError:
    import simplejson as json
from odoo.http import content_disposition
from odoo import http
import xlsxwriter

class XlsRrport(http.Controller):
    
    @http.route('/web/export/sale_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)
        if data['type'] == 'industrial':
            sale_objs = request.env['sale.order'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook=xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty= workbook.add_format({'font_size': 14,'valign': 'vcenter','align':'center','font':'Arial','bold':True})
            
            
            font_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'Arial'})
            text_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'Arial','text_wrap':True})
            table_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'center','font':'Arial','border':1,'bold':True})
            right_sty = workbook.add_format({'border': 1, 'font_size': 10, 'align': 'right','font':'Arial','valign' : 'vcenter','text_wrap':True})
            left_sty = workbook.add_format({'border': 1, 'font_size': 10, 'align': 'left','font':'Arial','valign' : 'vcenter','text_wrap':True})
            img_path=os.path.join(os.path.join(os.path.dirname(os.path.dirname(__file__)),'img'),'logo.png')
            
            for sale in sale_objs:
                worksheet = workbook.add_worksheet(sale.name or "销售订单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                
                worksheet.set_row(0, 13.8)
                worksheet.insert_image('A2', img_path, {'x_scale': 0.08, 'y_scale': 0.08})
                worksheet.merge_range(1,0, 3, 8, '工业品销售合同',title_sty)
                

                first_val='合同编号：'+(sale.name or '')+'                                    签订地点：'+'                                    签订日期：    '+datetime.datetime.now().strftime('%Y-%m-%d')
                worksheet.merge_range(4,0, 4, 8, first_val,font_sty)
                
                double_line_sty = workbook.add_format({'top':1,'bottom':1})
                worksheet.set_row(5, 3.65)
                worksheet.merge_range(5,0, 5, 8, '',double_line_sty)
                
                partner_id=sale.partner_id
                worksheet.write('A7', "买方："+(partner_id.name or ''), font_sty)
                bank_name=''
                bank_account=''
                if partner_id.bank_ids:
                    bank_name=partner_id.bank_ids[0].bank_id.name or ''
                    bank_account=partner_id.bank_ids[0].acc_number or ''
                worksheet.write('A8', "开户银行："+bank_name, font_sty)
                partner_address=(partner_id.state_id.name or '')+(partner_id.city or '')+(partner_id.street or '')+(partner_id.street2 or '')
                worksheet.write('A9', "办公地址："+partner_address, font_sty)
                worksheet.write('A10', "电话："+(partner_id.phone or ''), font_sty)
                worksheet.write('A11', "E-Mail："+(partner_id.email or ''), font_sty)
                
                worksheet.write('E7', "税号："+(partner_id.vat or ""), font_sty)
                worksheet.write('E8', "账号："+bank_account, font_sty)
                worksheet.write('E9', "注册地址："+(partner_address or ""), font_sty)
                worksheet.write('E10', "注册电话："+(partner_id.phone or ''), font_sty)
                worksheet.write('E11', "邮编："+(partner_id.zip or ""), font_sty)
                
                top_line_sty = workbook.add_format({'top':1})
                worksheet.set_row(11, 3.65)
                worksheet.merge_range(11,0, 11, 8, '',top_line_sty)
                
                company_id=sale.company_id
                worksheet.write('A13', "卖方："+(company_id.name or ''), font_sty)
                worksheet.write('A14', "开户银行：", font_sty)
                company_address=(company_id.state_id.name or '')+(company_id.city or '')+(company_id.street or '')+(company_id.street2 or '')
                worksheet.write('A15', "联系地址："+(company_address or ''), font_sty)
                worksheet.write('A16', "电话："+(company_id.phone or ''), font_sty)
                worksheet.write('A17', "第一条  合同标的物、数量、价款及交（提）货时间：", font_sty)
                
                worksheet.write('E13', "税号："+(company_id.vat or ""), font_sty)
                worksheet.write('E14', "账号：", font_sty)
                worksheet.write('E15', "邮编："+(company_id.zip or ""), font_sty)
                worksheet.write('E16', "E-Mail："+(company_id.email or ''), font_sty)
                
                worksheet.write('A18', "图号", table_sty)
                worksheet.write("B18", '名称',table_sty)
                worksheet.merge_range(17,2, 17, 3, '规格',table_sty)
                worksheet.write('E18', "数量", table_sty)
                worksheet.write('F18', "单位", table_sty)
                worksheet.write('G18', "单价", table_sty)
                worksheet.write('H18', "金额", table_sty)
                worksheet.write('I18', "交货时间", table_sty)
                
                row_count=18
                for line in sale.order_line:
                    worksheet.write(row_count, 0, line.diagram or '',left_sty)
                    worksheet.write(row_count, 1, line.product_id.name or '',left_sty)
                    worksheet.merge_range(row_count,2, row_count, 3, line.spec or '',left_sty)
                    worksheet.write(row_count, 4, line.product_uom_qty,right_sty)                    
                    worksheet.write(row_count, 5, line.product_uom.name or '',left_sty)
                    worksheet.write(row_count, 6, line.price_unit,right_sty)
                    worksheet.write(row_count, 7, line.price_total,right_sty)
                    commitment_date=''
                    if sale.commitment_date:
                        commitment_date=str(sale.commitment_date)[0:10]
                    worksheet.write(row_count, 8, commitment_date,right_sty)
                    row_count+=1
                    
                worksheet.merge_range(row_count,0, row_count, 5, '合计人民币金额（大写）：'+self.num2chn(sale.amount_total),left_sty)
                worksheet.write(row_count, 6, '',right_sty)
                worksheet.write(row_count, 7, sale.amount_total,right_sty)
                worksheet.write(row_count, 8, '',right_sty)
                row_count+=1
                if sale.print_note:
                    for term in sale.print_note.split('\n'):
                        worksheet.merge_range(row_count,0,row_count, 8, term, text_sty)
                        row_count+=1
                    row_count+=1
                
                worksheet.write(row_count,0, "买方名称(章):"+(partner_id.name or ''), font_sty)
                worksheet.write(row_count,4, "卖方名称(章):"+(company_id.name or ''), font_sty)
                row_count+=2
                worksheet.write(row_count,0, "买方代表签字：", font_sty)
                worksheet.write(row_count,4, "卖方代表签字：", font_sty)
                row_count+=2
                worksheet.write(row_count,0, "日期：", font_sty)
                worksheet.write(row_count,4, "日期：", font_sty)
                
                worksheet.set_column('A:C', 12)
                worksheet.set_column('D:D', 17)
                worksheet.set_column('I:I', 10)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '销售'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.xls'
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