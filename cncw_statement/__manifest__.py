# -*- encoding: utf-8 -*-
{
    "name": "财务应收应付扩展模组",
    "version": "1.0",
    "summary": """
    财务应收应付扩展模组
    """,
    "description": """
        修改、增加的内容：\n
        * 1. 增加预收款单模块；\n
        * 2. 费用类别设置模块；\n
        * 3. 修改发票模块，适配中国企业习惯；\n
        * 4. 增加付款单模块；\n
        * 5. 增加收款单模块；\n
        * 6. 修改公司模块，增加信息；\n
        * 7. 增加对帐单模块；\n
        * 8. 修改销售团队模块，增加银行、编号等信息；\n
        * 9. 增加权限;\n
        
    """,

    "category": "中国化财务/应收应付",
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    "depends": ["base","stock", "base_cw",
                "purchase", "sale", 'product','crm',
                ],
    "data": [
        "data/account_statement_data.xml",
        "data/account_move_data.xml",
        "data/account_statement_menu.xml",
        'data/base_period_control_data.xml',
        'data/account_payment_receive_data.xml',
        'security/ir.model.access.csv',
        'wizard/account_statement_receive_wizard.xml',
        'wizard/account_statement_delivery_wizard.xml',
        'wizard/account_invoice_select_statement.xml',
        'wizard/account_pay_add_invoice_wizard.xml',
        'wizard/account_pay_prepaid_select_wizard.xml',
        'wizard/account_receive_advance_select_wizard.xml',
        'wizard/invalid_invoice_select_wizard.xml',
        'wizard/sale_rebate_wizard.xml',  # 采购单
        'views/account_statement_purchase_view.xml',
        'views/account_statement_sale_view.xml',
        'views/account_in_invoice_view.xml',
        'views/account_in_refund_invoice_view.xml',
        'views/account_out_invoice_view.xml',
        'views/account_out_refund_invoice_view.xml',
        'views/account_expense_category_view.xml',
        'views/account_pay_view.xml',
        # 收款单
        'views/account_receive_view.xml',
        # 预付款申请
        'views/advance_payment_apply_view.xml',
        # 预收款申请
        'views/advance_receive_apply_view.xml',
        # 采购订单扩展
        'views/purchase_order_views_inherit.xml',
        # 销售订单扩展
        'views/sale_order_views_inherit.xml',
        'views/account_payment_category_view.xml',
        'views/account_receive_category_view.xml',
        'views/product_category_view.xml',
        'views/account_voucher_template_view.xml',
        'report/account_prepaid_view.xml',
        'report/account_advance_view.xml',
        'report/account_invoice_supplier_query_view.xml',
        'report/account_received_report_view.xml',
        'report/account_sale_invoice_delivery_report_view.xml',
        'report/account_shipment_statement_invoice_report.xml',
        'report/account_receivable_report_view.xml',
        'report/ap_ar_settle_view.xml',
        'report/ar_month_settle_view.xml',
        'report/ap_month_settle_view.xml',
        'report/account_payable_report_view.xml',
        'report/account_puchaser_invoice_delivery_report_view.xml',
    ],
    "assets": {
        "web.assets_backend": {
            # "base_cw/static/src/css/*.css",
            # "base_cw/static/src/css/*.js",
        },
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",
}
