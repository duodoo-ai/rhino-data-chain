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


class SaleDeliveryXlsRrport(http.Controller):
    @http.route('/web/export/sale_delivery_xls', type='http', auth="user")
    def index(self, req, data, token, debug=False):
        data = json.loads(data)
        if data['type'] == 'sale_delivery':
            delivery_objs = request.env['sale.delivery'].browse(data['order_ids'])
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            title_sty = workbook.add_format(
                {'font_size': 14, 'valign': 'vcenter', 'align': 'center', 'font': 'Arial', 'bold': True})

            font_sty = workbook.add_format({'font_size': 10, 'valign': 'vcenter', 'align': 'left', 'font': 'Arial'})

            table_sty = workbook.add_format(
                {'font_size': 10, 'valign': 'vcenter', 'align': 'center', 'font': 'Arial', 'border': 1, 'bold': True})
            right_sty = workbook.add_format(
                {'text_wrap': True, 'border': 1, 'font_size': 10, 'align': 'right', 'font': 'Arial',
                 'valign': 'vcenter'})
            left_sty = workbook.add_format(
                {'text_wrap': True, 'border': 1, 'font_size': 10, 'align': 'left', 'font': 'Arial',
                 'valign': 'vcenter'})

            for delivery in delivery_objs:
                worksheet = workbook.add_worksheet(delivery.name or "发货通知单")
                worksheet.set_portrait()
                worksheet.center_horizontally()  # 中心打印
                worksheet.fit_to_pages(1, 1)

                worksheet.merge_range(0, 0, 1, 5, '发货通知单', title_sty)
                worksheet.write(2, 0, "发货通知单号：" + (delivery.name or ''), font_sty)
                worksheet.write(3, 0, "客户：" + (delivery.partner_id.name or ''), font_sty)
                worksheet.write(4, 0, "交货地址：" + (delivery.delivery_address or ''), font_sty)
                worksheet.write(5, 0, "联系人：" + (delivery.receiver.name or ''), font_sty)
                worksheet.write(6, 0, "联系电话：" + str(delivery.phone or ''), font_sty)

                worksheet.write(2, 3, "销售订单：" + (delivery.sale_id.name or ''), font_sty)
                worksheet.write(3, 3, "大合同：" + (
                            delivery.sale_id.big_contract_id and delivery.sale_id.big_contract_id.name or ''), font_sty)
                worksheet.write(4, 3, "单据日期：" + str(delivery.date_order or ''), font_sty)
                worksheet.write(5, 3, "交货日期：" + str(delivery.commitment_date or ''), font_sty)
                worksheet.write(6, 3, "人员：" + str(delivery.user_id.name or ''), font_sty)

                worksheet.write('A10', "产品", table_sty)
                worksheet.write('B10', "说明", table_sty)
                worksheet.write('C10', "订单数量", table_sty)
                worksheet.write('D10', "发货数量", table_sty)
                worksheet.write('E10', "已送货", table_sty)
                worksheet.write('F10', "单位", table_sty)

                row_count = 10
                for line in delivery.order_line:
                    worksheet.write(row_count, 0, line.product_id.name or '', left_sty)
                    worksheet.write(row_count, 1, line.name or '', left_sty)
                    worksheet.write(row_count, 2, line.product_uom_qty, right_sty)
                    worksheet.write(row_count, 3, line.delivery_qty, right_sty)
                    worksheet.write(row_count, 4, line.order_qty_delivered, right_sty)
                    worksheet.write(row_count, 5, line.product_uom.name, left_sty)
                    row_count += 1
                worksheet.set_column('A:F', 13)
                worksheet.set_column('B:B', 35)
            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()
            filename = '发货通知' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f') + '.xls'
            httpheaders = [
                ('Content-Type', 'application/vnd.ms-excel'),
                ('Content-Disposition', content_disposition(filename)),
            ]
            response = request.make_response(None, headers=httpheaders)
            response.stream.write(generated_file)
            response.set_cookie('fileToken', token)
            return response
