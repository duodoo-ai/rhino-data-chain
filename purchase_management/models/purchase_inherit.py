# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from datetime import datetime, time
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderInherit(models.Model):
    _inherit = "purchase.order"

    file = fields.Binary(string='附件')
    file_name = fields.Char(string='文件名')
    print_note_id = fields.Many2one('purchase.print.note', string='打印条款')
    print_note = fields.Text(string="条款")
    amount_untaxed = fields.Float(string='未税金额', store=True, readonly=True, compute='_amount_all', tracking=True,
                                  digits=(16, 6))
    amount_tax = fields.Float(string='税', store=True, readonly=True, compute='_amount_all', digits=(16, 6))
    amount_total = fields.Float(string='合计', store=True, readonly=True, compute='_amount_all', digits=(16, 6))

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrderInherit, self)._prepare_picking()
        res['user_id'] = self.user_id.id
        res['department_id'] = self.sudo().user_id.department_id.id
        return res

    @api.onchange('print_note_id')
    def onchange_print_note_id(self):
        if self.print_note_id:
            self.print_note = self.print_note_id.print_note

    def _add_supplier_to_product(self):
        # Add the partner in the supplier list of the product if the supplier is not registered for
        # this product. We limit to 10 the number of suppliers for a product to avoid the mess that
        # could be caused for some generic products ("Miscellaneous").
        for line in self.order_line:
            # Do not add a contact as a supplier
            partner = self.partner_id if not self.partner_id.parent_id else self.partner_id.parent_id
            if line.product_id:
                # Convert the price in the right currency.
                currency = partner.property_purchase_currency_id or self.env.company.currency_id
                price = self.currency_id._convert(line.price_unit, currency, line.company_id,
                                                  line.date_order or fields.Date.today(), round=False)
                # Compute the price for the template's UoM, because the supplier's UoM is related to that UoM.
                if line.product_id.product_tmpl_id.uom_po_id != line.product_uom:
                    default_uom = line.product_id.product_tmpl_id.uom_po_id
                    price = line.product_uom._compute_price(price, default_uom)

                supplierinfo = {
                    'partner_id': partner.id,
                    'sequence': max(
                        line.product_id.seller_ids.mapped('sequence')) + 1 if line.product_id.seller_ids else 1,
                    'min_qty': 0.0,
                    'price': price,
                    'currency_id': currency.id,
                    'delay': 0,
                }
                # In case the order partner is a contact address, a new supplierinfo is created on
                # the parent company. In this case, we keep the product name and code.
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    quantity=line.product_qty,
                    date=line.order_id.date_order and line.order_id.date_order.date(),
                    uom_id=line.product_uom)
                if seller:
                    supplierinfo['product_name'] = seller.product_name
                    supplierinfo['product_code'] = seller.product_code
                vals = {
                    'seller_ids': [(0, 0, supplierinfo)],
                }
                try:
                    line.product_id.write(vals)
                except AccessError:  # no write access rights -> just ignore
                    break


class PurchaseOrderLineInherit(models.Model):
    _inherit = "purchase.order.line"

    price_unit = fields.Float(string='单价', required=True, digits=(16, 6))
    price_subtotal = fields.Float(compute='_compute_amount', string='小计', store=True, digits=(16, 6))
    price_total = fields.Float(compute='_compute_amount', string='总计', store=True, digits=(16, 6))
    price_tax = fields.Float(compute='_compute_amount', string='税', store=True, digits=(16, 6))

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        res = super(PurchaseOrderLineInherit, self)._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        res.pop('move_dest_ids')
        return res
