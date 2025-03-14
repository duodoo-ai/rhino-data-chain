# -*- coding: utf-8 -*-
{
    'name': '采购管理',
    'version': '1.0',
    'summary' : """
        采购管理
    """,
    'depends': ['purchase','purchase_requisition'],#继承
    'category': '中国进销存/采购管理',
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    'sequence': 2,
    'data': [
        'security/ir.model.access.csv',
        'security/purchase_management_groups.xml',
        'views/purchase_view_inherit.xml',
        'views/requisition_line_view.xml',
        'views/product_view_inherit.xml',
        'views/print_note.xml',
        'views/purchase_order_line_view_inherit.xml',
        'wizard/requisition_line_wizard.xml',
        'wizard/requisition_line_audit_wizard.xml',
        'wizard/download_select.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",
}