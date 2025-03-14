# -*- encoding: utf-8 -*-
from .. import public
from odoo import models, fields, api, _
from odoo.exceptions import UserError


# ===============================================================================
# # 类名:ir_model
# # Copyright(c):
# # 功能描述: 横组划分
# # 创 建 人:
# # 创建日期:
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
class ir_model(models.Model):
    _inherit = 'ir.model'

    belongs_to_module = fields.Selection([('stock', 'Stock Module'),
                                          ('mrp', 'Produce'),
                                          ('hr', 'Human Resources'),
                                          ('gl', 'Gereral Ledger'),
                                          ('other', 'Other'),
                                          ], '所属模组', index=True, default='other')

    def init(self):
        self._cr.execute("""
            update ir_model set belongs_to_module='stock'
             where model in ('sale.return','sale.return.storage','stock.delivery','stock.sample','purchase.receive',
                    'purchase.receive.return','purchase.storage','purchase.storage.return','stock.allot',
                    'stock.discard','stock.other.in','stock.other.out','stock.repair.out','stock.repair.in');
         """)
