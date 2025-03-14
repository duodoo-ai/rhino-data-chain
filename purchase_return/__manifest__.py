# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': '采购退货',
    'version': '1.0',
    'summary' : """
        采购退货单
    """,
    'category': '中国进销存/采购退货',
    'depends': ['hr','stock','purchase','purchase_stock'],#继承
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'data/purchase_return_data.xml',
        'security/purchase_return_groups.xml',
        'security/ir.model.access.csv',
        'views/purchase_return_view.xml',
        'views/return_select.xml',
        'wizard/download_select.xml',
        'report/purchase_return_report.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",

}