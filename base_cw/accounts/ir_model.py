# -*- coding: utf-8 -*-
from odoo import api,models,fields


class IrModel(models.Model):
    _inherit = 'ir.model'

    period_control_id = fields.Many2one('base.period.control', string='会期控制')

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _description = '辅助核算'

    subaccount_category_id = fields.Many2one('subaccount.category', '辅助核算类别', required=False, ondelete="restrict")
    subaccount_category_code = fields.Char('辅助核算类别编码', related='subaccount_category_id.code', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ResPartner, self)
        for value in vals_list:
            if 'customer_rank' in value and value.get('customer_rank') > 0:
                value.update(dict(
                    subaccount_category_id=self.env.ref('base_cw.account_subaccount_category_customer').id
                ))
            if 'supplier_rank' in value and value.get('supplier_rank') > 0:
                value.update(dict(
                    subaccount_category_id=self.env.ref('base_cw.account_subaccount_category_supplier').id
                ))
        return res.create(vals_list)

    def write(self, vals):
        customer_rank = vals.get('customer_rank')
        supplier_rank = vals.get('supplier_rank')
        if customer_rank and customer_rank > 0:
            vals.update(dict(
                subaccount_category_id=self.env.ref('base_cw.account_subaccount_category_customer').id
            ))
        if supplier_rank and supplier_rank > 0:
            vals.update(dict(
                subaccount_category_id=self.env.ref('base_cw.account_subaccount_category_supplier').id
            ))
        return super(ResPartner, self).write(vals)
