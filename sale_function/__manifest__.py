# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': '销售扩展管理',
    'version': '1.0',
    'summary' : """
        销售订单添加附件下载
    """,
    'depends': ['sale','sale_management'],#继承
    'category': '中国进销存/销售扩展',
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'security/ir.model.access.csv',
        # 'security/sale_function_groups.xml',
        'views/sale_view_inherit.xml',
        'wizard/download_select.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",

}