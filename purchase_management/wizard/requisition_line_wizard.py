# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class RequisitionLineWizard(models.Model):
    _name="requisition.line.wizard"
    _description="采购申请单生成询价单"
    
    line_ids=fields.Many2many('purchase.requisition.line',string='采购申请单明细',required=True)
    vendor_id = fields.Many2one('res.partner', string=u"供应商", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",required=True)
    company_id = fields.Many2one('res.company', string='公司', required=True, default=lambda self: self.env.company)
        
        
    def action_new_quotation(self):
        partner = self.vendor_id
        if not partner.partner_currency_id:
            raise UserError(u"供应商资料币别不可为空!")
        if not partner.account_tax_id:
            raise UserError(u"供应商资料税别不可为空!")
        
        payment_term = partner.property_supplier_payment_term_id
        # FiscalPosition = self.env['account.fiscal.position']
        # fpos = FiscalPosition.with_context(force_company=self.company_id.id).get_fiscal_position(partner.id)
        # fpos = FiscalPosition.browse(fpos)
        vals={
            'partner_id':partner.id,
            # 'fiscal_position_id':fpos.id,
            'payment_term_id':payment_term.id,
            'company_id':self.env.company.id,
            'currency_id':self.vendor_id.property_purchase_currency_id.id or self.env.company.currency_id.id,
            'date_order':fields.Datetime.now(),
            'tax_id':partner.account_tax_id.id,
            'exchange_rate':partner.partner_currency_id.rate
            }
        origin=''
        purchase_order=self.env['purchase.order'].create(vals)
        for line in self.line_ids:
            requisition = line.requisition_id
            #如果申请单状态为草稿，在这里做确认操作，目的为了生成采购申请单号
            if requisition.state=='draft':
                requisition.action_in_progress()
            if  requisition.name not in origin.split(', '):
                if origin:
                    if requisition.name:
                        origin = origin + ', ' + requisition.name
                else:
                    origin = requisition.name
                purchase_order.write({'origin':origin})
#             self.notes = requisition.description
#     
#             if requisition.type_id.line_copy != 'copy':
#                 return
    
            product_lang = line.product_id.with_context(
                lang=partner.lang,
                partner_id=partner.id
            )
            name = product_lang.display_name
            if product_lang.description_purchase:
                name += '\n' + product_lang.description_purchase

#             if fpos:
#                 taxes_ids = fpos.map_tax(line.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == requisition.company_id)).ids
#             else:
#                 taxes_ids = line.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == requisition.company_id).ids

            if line.product_uom_id != line.product_id.uom_po_id:
                actual_qty = line.product_uom_id._compute_quantity(line.actual_qty, line.product_id.uom_po_id)
                price_unit = line.product_uom_id._compute_price(line.price_unit, line.product_id.uom_po_id)
            else:
                actual_qty = line.actual_qty
                price_unit = line.price_unit
            
            if not price_unit:
                supplier_infos = self.env['product.supplierinfo'].search([
                    ('product_id', '=', vals.get('product_id')),('partner_id', '=', partner.id),
                ],order="create_date desc",limit=1)
                if supplier_infos:
                    price_unit = line.product_uom_id._compute_price(supplier_infos.price, supplier_infos.product_uom)
                    
#             if requisition.schedule_date:
#                 date_planned = datetime.combine(requisition.schedule_date, time.min)
#             else:
#                 date_planned = datetime.now()
            self.env['purchase.order.line'].create({
                'order_id':purchase_order.id,
                'name': name,
                'product_id': line.product_id.id,
                'product_uom': line.product_id.uom_po_id.id,
                'product_qty': actual_qty,
                'price_unit': price_unit,
                'taxes_id': [(6, 0, partner.account_tax_id.ids)],
                'date_planned': line.schedule_date or datetime.now(),
                # 'account_analytic_id': line.account_analytic_id.id,
                # 'analytic_tag_ids': line.analytic_tag_ids.ids,
                })
            line.line_state='done'
            #查看该采购申请下的明细是否全部生成询价单，如果全部生成状态变为关闭
            is_done=True
            for requisition_line in requisition.line_ids:
                if requisition_line.line_state=='draft':
                    is_done=False
                    break
            if is_done:
                requisition.state='done'
        return {
                'view_mode': 'form',
                'res_model': 'purchase.order',
                'type': 'ir.actions.act_window',
                'res_id': purchase_order.id,
            }