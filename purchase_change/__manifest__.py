# -*- coding: utf-8 -*-
{
    'name': '采购订单变更',
    'version': '1.0',
    'summary' : """
        采购订单变更
    """,
    'depends': ['hr','purchase','purchase_requisition','purchase_stock'],#继承
    'category': '中国进销存/采购变更',
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'data/purchase_change_data.xml',
        'security/purchase_change_groups.xml',
        'security/ir.model.access.csv',
        'views/purchase_change_view.xml',
        'wizard/download_select.xml',
        'report/purchase_change_report.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",

}