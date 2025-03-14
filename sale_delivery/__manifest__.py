# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': '销售发货通知单',
    'version': '1.0',
    'summary': '销售发货通知单，修改产品预测数量',
    'description': "Sale Delivery",
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'category': '中国进销存/销售发货',
    'sequence': 1,
    'images': [],
    'depends': ['sale', 'sale_management', 'sale_stock', 'sale_function'],
    'data': [
        'security/sale_delivery_security.xml',
        'security/ir.model.access.csv',
        'data/sale_delivery_data.xml',
        'views/sale_delivery.xml',
        'views/stock_view_inherit.xml',
        'wizard/download_select.xml',
        'report/sale_delivery_report.xml'
    ],
    'demo': [
    ],
    'qweb': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",
}
