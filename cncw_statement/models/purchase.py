# -*- coding: utf-8 -*-
from odoo import api,fields,models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # def action_view_invoice(self):
    #     '''
    #     This function returns an action that display existing vendor bills of given purchase order ids.
    #     When only one found, show the vendor bill immediately.
    #     '''
    #     action = self.env.ref('account.action_move_in_invoice_type')
    #     result = action.read()[0]
    #     create_bill = self.env.context.get('create_bill', False)
    #     # override the context to get rid of the default filtering
    #     result['context'] = {
    #         'default_type': 'in_invoice',
    #         'default_company_id': self.company_id.id,
    #         'default_purchase_id': self.id,
    #         'default_partner_id':self.partner_id.id
    #     }
    #     # choose the view_mode accordingly
    #     if len(self.invoice_ids) > 1 and not create_bill:
    #         result['domain'] = "[('id', 'in', " + str(self.invoice_ids.ids) + ")]"
    #     else:
    #         res = self.env.ref('cncw_statement.view_account_invoice_supplier_query_form', False)
    #         form_view = [(res and res.id or False, 'form')]
    #         if 'views' in result:
    #             result['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
    #         else:
    #             result['views'] = form_view
    #         # Do not set an invoice_id if we want to create a new bill.
    #         if not create_bill:
    #             result['res_id'] = self.invoice_ids.id or False
    #     result['context']['default_origin'] = self.name
    #     result['context']['default_reference'] = self.partner_ref
    #     return result

    # def action_view_picking(self):
    #     result = super(PurchaseOrder, self).action_view_picking()
    #     result['context']['default_to_checked_qty'] =