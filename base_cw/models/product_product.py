# -*- encoding: utf-8 -*-
from odoo import models, fields, api

from ..public import PRODUCT_TYPE


class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'

    categ_id = fields.Many2one('product.category', string='产品分类',)
    product_type = fields.Selection(PRODUCT_TYPE, '成本类型', index=True)
    supplier_taxes_id = fields.Many2many('account.tax', 'product_supplier_taxes_rel', 'prod_id', 'tax_id',
                                         string='Vendor Taxes', help='Default taxes used when buying the product.',
                                         domain=[('type_tax_use', 'in', ['purchase', 'all'])],
                                         default=lambda self: self.env.company.account_purchase_tax_id)

    taxes_id = fields.Many2many('account.tax', 'product_taxes_rel', 'prod_id', 'tax_id',
                                help="Default taxes used when selling the product.", string='Customer Taxes',
                                domain=[('type_tax_use', 'in', ['sale', 'all'])],
                                default=lambda self: self.env.company.account_sale_tax_id)
    avg_price = fields.Float('平均单价', digits='Product Price')


class ProductCategory(models.Model):
    _inherit = 'product.category'

    product_type = fields.Selection(PRODUCT_TYPE, '成本类型')

    account_id = fields.Many2one('cncw.account', string='会计科目')

    def get_account_id(self):
        if self.account_id:
            return self.account_id
        elif self.parent_id:
            return self.parent_id.get_account_id()
        else:
            return self.env['cncw.account']

    @api.onchange('product_type')
    def onchange_product_type(self):
        if hasattr(self, '_origin'):
            product_template = self.env['product.template'].search(
                [('categ_id', '=', self._origin.id), '|', ('company_id', '=', self.env.user.company_id.id),
                 ('company_id', '=', False)])
            for product in product_template:
                product.write({'product_type': self.product_type})


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_account_id(self):
        return self.categ_id.get_account_id()
