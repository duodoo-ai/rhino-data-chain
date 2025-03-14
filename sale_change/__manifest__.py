# -*- coding: utf-8 -*-
{
    'name': '销售订单变更',
    'version': '1.0',
    'summary' : """
        销售变更单
    """,
    'depends': ['sale','sale_management','sale_stock','sale_delivery','sale_function'],
    'category': '中国进销存/销售变更',
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'data/sale_change_data.xml',
        'security/sale_change_groups.xml',
        'security/ir.model.access.csv',
        'views/sale_change_view.xml',
        'wizard/download_select.xml',
        'report/sale_change_report.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",
}