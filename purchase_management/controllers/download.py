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

class PurchaseXlsRrport(http.Controller):
    @http.route('/web/export/purchase_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)

        if data['type'] == 'complete':
            purchase_objs = request.env['purchase.order'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook=xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty= workbook.add_format({'font_size': 14,'valign': 'vcenter','align':'center','font':'宋体','bold':True})
            first_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'宋体','bottom':6})
            font_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'宋体'})
            
            table_sty = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'center','font':'宋体','border':1,'bold':True})
            right_sty = workbook.add_format({'border': 1, 'font_size': 10, 'align': 'right','font':'宋体','valign' : 'vcenter','text_wrap':True})
            left_sty = workbook.add_format({'border': 1, 'font_size': 10, 'align': 'left','font':'宋体','valign' : 'vcenter','text_wrap':True})
            term_sty= workbook.add_format({'font_size': 9,'valign': 'vcenter','align':'left','font':'宋体'})
            note_sty=workbook.add_format({'font_size': 11,'valign': 'vcenter','align':'left','font':'宋体','border':1,'bold':True})
            bottom_border = workbook.add_format({'font_size': 10,'valign': 'vcenter','align':'left','font':'宋体','bottom':1})
            img_path=os.path.join(os.path.join(os.path.dirname(os.path.dirname(__file__)),'img'),'company_logo.png')
            
            for purchase in purchase_objs:
                worksheet = workbook.add_worksheet(purchase.name or "采购订单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                
                worksheet.insert_image('A1', img_path, {'x_scale': 0.07, 'y_scale': 0.07})
                company_id=purchase.company_id
                worksheet.merge_range(0,0, 0, 7, '买卖合同',title_sty)
                worksheet.set_row(0, 38.5)
                first_val='合同编号：'+(purchase.name or '')+'                签订日期：'+datetime.datetime.now().strftime('%Y-%m-%d')+'                签订地点：   烟台'
                worksheet.merge_range(1,0, 1, 7, first_val,first_sty)
                worksheet.set_row(2, 3.65)
                worksheet.write('A4', "甲方："+(company_id.name or ''), font_sty)
                company_address=(company_id.state_id.name or '')+(company_id.city or '')+(company_id.street or '')+(company_id.street2 or '')
                worksheet.write('A5', "联系地址："+(company_address or ''), font_sty)
                worksheet.write('A6', "联系电话："+(company_id.phone or ''), font_sty)
                worksheet.write('A7', "传真：0535-6919362", font_sty)
                worksheet.write('A8', "联系人："+(purchase.user_id.name or ''), bottom_border)
                
                worksheet.write('E4', "税号："+(company_id.vat or ""), font_sty)
                worksheet.write('E5', "开户银行：中国银行烟台莱山支行", font_sty)
                worksheet.write('E6', "账号：233811399748", font_sty)
                worksheet.write('E7', "注册地址："+(company_address or ""), font_sty)
                worksheet.write('E8', "电话："+(purchase.user_id.mobile_phone or ""), bottom_border)
                
                worksheet.write('B8', "", bottom_border)
                worksheet.write('C8', "", bottom_border)
                worksheet.write('D8', "", bottom_border)
                worksheet.write('F8', "", bottom_border)
                worksheet.write('G8', "", bottom_border)
                worksheet.write('H8', "", bottom_border)
                
                partner_id=purchase.partner_id
                bank_name=''
                bank_account=''
                if partner_id.bank_ids:
                    bank_name=partner_id.bank_ids[0].bank_id.name or ''
                    bank_account=partner_id.bank_ids[0].acc_number or ''
                worksheet.write('A9', "乙方："+(partner_id.name or ''), font_sty)
                partner_address=(partner_id.state_id.name or '')+(partner_id.city or '')+(partner_id.street or '')+(partner_id.street2 or '')
                worksheet.write('A10', "办公地址："+(partner_address or ''), font_sty)
                worksheet.write('A11', "联系电话："+(partner_id.phone or ''), font_sty)
                worksheet.write('A12', "联系传真："+(partner_id.fax or ''), font_sty)
    
                worksheet.write('E9', "税号："+(partner_id.vat or ""), font_sty)
                worksheet.write('E10', "开户银行："+bank_name, font_sty)
                worksheet.write('E11', "账号："+bank_account, font_sty)
                worksheet.write('E12', "注册地址："+(partner_address or ""), font_sty)
                
                worksheet.write('A13', "第一条  标的、数量及价款", term_sty)
                
                worksheet.write('A14', "名称", table_sty)
                worksheet.merge_range(13, 1,13, 3, "规格",table_sty)
                worksheet.write('E14', "数量", table_sty)
                worksheet.write('F14', "单位", table_sty)
                worksheet.write('G14', "单价", table_sty)
                worksheet.write('H14', "金额", table_sty)
                
                row_count=14
                total_qty=0
                for line in purchase.order_line:
                    worksheet.write(row_count, 0, line.product_id.name or '',left_sty)
                    worksheet.merge_range(row_count, 1,row_count, 3, line.product_id.description or '',left_sty)
                    worksheet.write(row_count, 4, line.product_qty,right_sty)
                    worksheet.write(row_count, 5, line.product_uom.name or '',left_sty)
                    worksheet.write(row_count, 6, line.price_unit,right_sty)
                    worksheet.write(row_count, 7, "￥"+str(line.price_total),right_sty)
                    total_qty+=line.product_qty
                    row_count+=1
                worksheet.merge_range(row_count,0, row_count, 3, '合计人民币（大写）：'+self.num2chn(purchase.amount_total),left_sty)
                worksheet.write(row_count, 4, total_qty,right_sty)
                worksheet.write(row_count, 5, '',table_sty)
                worksheet.write(row_count, 6, '',table_sty)
                worksheet.write(row_count, 7, "￥"+str(purchase.amount_total),right_sty)
                row_count+=1
                worksheet.merge_range(row_count,0, row_count, 7, '备注：送货清单箱内、箱外各一份；必须标注合同PO号； ',note_sty)
                worksheet.set_row(row_count, 32)
                row_count+=1
                if purchase.print_note:
                    for term in purchase.print_note.split('\n'):
                        worksheet.merge_range(row_count,0,row_count, 7, term, font_sty)
                        row_count+=1
                    row_count+=1
                
                worksheet.write(row_count,0, "买方(章):"+(company_id.name or ''), font_sty)
                worksheet.write(row_count,4, "卖方(章):"+(partner_id.name or ''), font_sty)
                row_count+=2
                worksheet.write(row_count,0, "经办人签字:", font_sty)
                worksheet.write(row_count,4, "经办人签字:", font_sty)
                row_count+=2
                worksheet.write(row_count,0, "日期:", font_sty)
                worksheet.write(row_count,4, "日期:", font_sty)
                
                # 设置列属性，把A到B列宽设置为20
                worksheet.set_column('A:A', 17)
                worksheet.set_column('B:C', 12)
                worksheet.set_column('D:I', 11)
                
                
                worksheet2 = workbook.add_worksheet(purchase.name+"送货清单" or "产品送货清单")
                worksheet.set_portrait()
                worksheet.center_horizontally()#中心打印
                worksheet.fit_to_pages(1, 1)
                worksheet2.merge_range(0,0, 0, 8, '产品送货清单',title_sty)
                worksheet2.write('A2', "收货单位", table_sty)
                worksheet2.merge_range(1,1, 1, 2, purchase.company_id.name or '', table_sty)#收货单位
                worksheet2.merge_range(1,3, 1, 4, '合同编号',table_sty)
                worksheet2.merge_range(1,5, 1, 8, purchase.name or '',table_sty)
                
                worksheet2.write('A3', "收货人", table_sty)
                worksheet2.merge_range(2,1, 2, 2, purchase.user_id.name or '', table_sty)#收货单位
                worksheet2.merge_range(2,3, 2, 4, '收货电话',table_sty)
                worksheet2.merge_range(2,5, 2, 8, '',table_sty)
                
                worksheet2.write('A4', "计划单号", table_sty)
                worksheet2.write('B4', "品号", table_sty)
                worksheet2.write('C4', "品名", table_sty)
                worksheet2.merge_range(3,3, 3, 5, '规格型号',table_sty)
                worksheet2.write('G4', "单位", table_sty)
                worksheet2.write('H4', "订购数量", table_sty)
                worksheet2.write('I4', "实送数量", table_sty)
                
                row_count=4
                for line in purchase.order_line:
                    worksheet2.write(row_count, 0, '',table_sty)
                    worksheet2.write(row_count, 1, line.product_id.default_code or '',table_sty)
                    worksheet2.write(row_count, 2, line.product_id.name or '',table_sty)
                    worksheet2.merge_range(row_count,3, row_count, 5, line.product_id.description or '',table_sty)
                    worksheet2.write(row_count, 6, line.product_uom.name or '',table_sty)
                    worksheet2.write(row_count, 7, line.product_qty or '',table_sty)
                    worksheet2.write(row_count, 8, line.qty_received or '',table_sty)
                    row_count+=1
                worksheet2.merge_range(row_count,0, row_count, 8, '发货单位：'+str(purchase.partner_id.name or ''),left_sty)
                row_count+=1
                worksheet2.merge_range(row_count,0, row_count, 8, '发货人：',left_sty)
                row_count+=1
                worksheet2.merge_range(row_count,0, row_count, 8, '货物异常联系电话：'+(purchase.partner_id.mobile or ''),left_sty)
                row_count+=1
                worksheet2.merge_range(row_count,0, row_count+2, 8, 
                                       '备注：我司以此送货清单为接收依据，到货物料没有送货清单或是送货清单信息不全，导致材料接收、报验、入库信息失真，并影响贵司发票核对的事宜，我司财务有权延迟支付货款，并将相关发票一并退回，由此所产生的一切损失由贵司自行承担。',left_sty)

                worksheet2.set_column('A:C', 13)
                worksheet2.set_column('D:I', 7)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '采购'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')+'.xls'
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