# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': '销售退货单',
    'version': '1.0',
    'summary' : """
        销售退货单
    更多支持：
    18951631470
    zou.jason@qq.com
    """,
    'depends': ['hr','sale','sale_stock','sale_management','sale_function'],#继承
    'category': '中国进销存/销售退货',
    'author': "Jason Zou",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'data/sale_return_data.xml',
        'security/ir.model.access.csv',
        'security/sale_return_groups.xml',
        'views/sale_return_view.xml',
        'views/return_sale_select.xml',
        'wizard/download_select.xml',
        'report/sale_return_report.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",

}