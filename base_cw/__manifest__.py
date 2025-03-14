# -*- encoding: utf-8 -*-
{
    "name": "ERP 财务基础",
    "version": "1.0",
    "summary": """
    ERP 基础模组
    """,
    "description": """
    修改内容：\n
    1.将一些源生模块放到设置下，并设置权限；\n
    2.修改源生模组基础信息，增加权限控制;\
    """,
    "category": "中国化财务/财务基础",
    "author": "zou.jason@qq.com",
    "website": "www.duodoo.tech",
    "depends": ["base", 'web', 'mail',"product", "sale","purchase","account","stock","hr"],
    "data": [
        'security/res_security.xml',
        'security/account_sercurity.xml',
        'accviews/account.xml',
        'data/account_account_type.xml',
        'data/res_data.xml',
        'data/ir_cron_data.xml',
        'data/base_period_control_data.xml',
        'security/ir.model.access.csv',
        'views/ir_sequence_view.xml',
        'views/base_view.xml',
        'views/res_groups.xml',
        'views/stock_picking_type_view.xml',
        'views/purchase_order_view.xml',
        'views/sale_order_view.xml',
        'views/product_product_view.xml',
        'views/res_company_view.xml',
        'views/stock.xml',
        'accviews/account_base_view.xml',
        'accviews/base_period_control_view.xml',
        'accviews/hr_employee_view.xml',
        'accviews/sub_account_line_view.xml',
        'views/res_partner_view.xml',
        'wizard/wizard_control_model_view.xml',
        'cn_standard_2015/account_chart_template.xml',
        'accviews/cncw_chart_template_views.xml',
        'accviews/res_config_settings_views.xml',
        'accviews/glob_org_view.xml',
        'data/base_menu_view.xml',
    ],
    'demo': [],
    "assets": {
        "web.assets_backend": [
            # "base_cw/static/src/css/*.css",
            # "base_cw/static/src/js/*.js",
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    "license": "AGPL-3",
}
