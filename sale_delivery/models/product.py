# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import pycompat,float_is_zero
from odoo.tools.float_utils import float_round
from datetime import datetime

# class Product(models.Model):
#     _inherit = "product.product"
#
#     @api.depends('stock_move_ids.product_qty', 'stock_move_ids.state','sales_count')
#     @api.depends_context(
#         'lot_id', 'owner_id', 'package_id', 'from_date', 'to_date',
#         'company_owned', 'force_company',
#     )
#     def _compute_quantities(self):
#         products = self.filtered(lambda p: p.type != 'service')
#         res = products._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'), self._context.get('from_date'), self._context.get('to_date'))
#         for product in products:
#             product.qty_available = res[product.id]['qty_available']
#             product.incoming_qty = res[product.id]['incoming_qty']
#             product.outgoing_qty = res[product.id]['outgoing_qty']
#             product.virtual_available = res[product.id]['virtual_available']
#             product.free_qty = res[product.id]['free_qty']
#         # Services need to be set with 0.0 for all quantities
#         services = self - products
#         services.qty_available = 0.0
#         services.incoming_qty = 0.0
#         services.outgoing_qty = 0.0
#         services.virtual_available = 0.0
#         services.free_qty = 0.0
#
#     def _compute_quantities_dict(self, lot_id, owner_id, package_id, from_date=False, to_date=False):
#         domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
#         domain_quant = [('product_id', 'in', self.ids)] + domain_quant_loc
#         dates_in_the_past = False
#         # only to_date as to_date will correspond to qty_available
#         to_date = fields.Datetime.to_datetime(to_date)
#         if to_date and to_date < fields.Datetime.now():
#             dates_in_the_past = True
#
#         domain_move_in = [('product_id', 'in', self.ids)] + domain_move_in_loc
#         domain_move_out = [('product_id', 'in', self.ids)] + domain_move_out_loc
#         if lot_id is not None:
#             domain_quant += [('lot_id', '=', lot_id)]
#         if owner_id is not None:
#             domain_quant += [('owner_id', '=', owner_id)]
#             domain_move_in += [('restrict_partner_id', '=', owner_id)]
#             domain_move_out += [('restrict_partner_id', '=', owner_id)]
#         if package_id is not None:
#             domain_quant += [('package_id', '=', package_id)]
#         if dates_in_the_past:
#             domain_move_in_done = list(domain_move_in)
#             domain_move_out_done = list(domain_move_out)
#         if from_date:
#             date_date_expected_domain_from = [
#                 '|',
#                     '&',
#                         ('state', '=', 'done'),
#                         ('date', '<=', from_date),
#                     '&',
#                         ('state', '!=', 'done'),
#                         ('date_expected', '<=', from_date),
#             ]
#             domain_move_in += date_date_expected_domain_from
#             domain_move_out += date_date_expected_domain_from
#         if to_date:
#             date_date_expected_domain_to = [
#                 '|',
#                     '&',
#                         ('state', '=', 'done'),
#                         ('date', '<=', to_date),
#                     '&',
#                         ('state', '!=', 'done'),
#                         ('date_expected', '<=', to_date),
#             ]
#             domain_move_in += date_date_expected_domain_to
#             domain_move_out += date_date_expected_domain_to
#
#         Move = self.env['stock.move']
#         Quant = self.env['stock.quant']
#         Outsource=self.env['mrp.outsource']
#
#         domain_move_in_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_in
#         domain_move_out_todo = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available'))] + domain_move_out
#
#         domain_move_out_sale_done = [('state', '=', 'done'),('sale_line_id','!=',None)] + domain_move_out
#         domain_move_out_without_sale = [('state', 'in', ('waiting', 'confirmed', 'assigned', 'partially_available')),('sale_line_id','=',None)] + domain_move_out
#         moves_in_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#         moves_out_res = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_todo, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#         moves_out_res_sale_done = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_sale_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#         moves_out_res_without_sale = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_without_sale, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#
#         outsource = dict((item['product_id'][0], item['product_qty']) for item in Outsource.read_group([('state','!=','done')], ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#
#         quants_res = dict((item['product_id'][0], (item['quantity'], item['reserved_quantity'])) for item in Quant.read_group(domain_quant, ['product_id', 'quantity', 'reserved_quantity'], ['product_id'], orderby='id'))
#         if dates_in_the_past:
#             # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
#             domain_move_in_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_in_done
#             domain_move_out_done = [('state', '=', 'done'), ('date', '>', to_date)] + domain_move_out_done
#             moves_in_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_in_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#             moves_out_res_past = dict((item['product_id'][0], item['product_qty']) for item in Move.read_group(domain_move_out_done, ['product_id', 'product_qty'], ['product_id'], orderby='id'))
#
#         res = dict()
#         for product in self.with_context(prefetch_fields=False):
#             product_id = product.id
#             if not product_id:
#                 res[product_id] = dict.fromkeys(
#                     ['qty_available', 'free_qty', 'incoming_qty', 'outgoing_qty','outgoing_qty_without_sale', 'virtual_available'],
#                     0.0,
#                 )
#                 continue
#             rounding = product.uom_id.rounding
#             res[product_id] = {}
#             if dates_in_the_past:
#                 qty_available = quants_res.get(product_id, [0.0])[0] - moves_in_res_past.get(product_id, 0.0) + moves_out_res_past.get(product_id, 0.0)
#             else:
#                 qty_available = quants_res.get(product_id, [0.0])[0]
#             reserved_quantity = quants_res.get(product_id, [False, 0.0])[1]
#             outgoing_qty_sale_done = float_round(moves_out_res_sale_done.get(product_id, 0.0), precision_rounding=rounding)
#             outgoing_qty_without_sale = float_round(moves_out_res_without_sale.get(product_id, 0.0), precision_rounding=rounding)
#             res[product_id]['qty_available'] = float_round(qty_available, precision_rounding=rounding)
#             res[product_id]['free_qty'] = float_round(qty_available - reserved_quantity, precision_rounding=rounding)
#             res[product_id]['incoming_qty'] = float_round(moves_in_res.get(product_id, 0.0), precision_rounding=rounding)
#             res[product_id]['outgoing_qty'] = float_round(moves_out_res.get(product_id, 0.0), precision_rounding=rounding)
#             outsource_qty = float_round(outsource.get(product_id, 0.0), precision_rounding=rounding)
#             #预测数量=在手数量-（已售数量-已发货的销售数量)+在途数量-销售以外将要出货数量
#             res[product_id]['virtual_available'] = float_round(
#                 qty_available - (product.sales_count-outgoing_qty_sale_done)+ res[product_id]['incoming_qty']-outgoing_qty_without_sale+outsource_qty,
#                 precision_rounding=rounding)
#
#         return res


# class ProductTemplate(models.Model):
#     _inherit = 'product.template'
#     _check_company_auto = True
#
#     @api.depends(
#         'product_variant_ids',
#         'product_variant_ids.stock_move_ids.product_qty',
#         'product_variant_ids.stock_move_ids.state',
#         'product_variant_ids.sales_count'
#     )
#     @api.depends_context('company_owned', 'force_company')
#     def _compute_quantities(self):
#         res = self._compute_quantities_dict()
#         for template in self:
#             template.qty_available = res[template.id]['qty_available']
#             template.virtual_available = res[template.id]['virtual_available']
#             template.incoming_qty = res[template.id]['incoming_qty']
#             template.outgoing_qty = res[template.id]['outgoing_qty']

