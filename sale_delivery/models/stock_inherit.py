# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, fields, models, _
# from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_delivery_line_id = fields.Many2one('sale.delivery.line', string='发货通知单明细', index=True)
    sale_id = fields.Many2one('sale.order', string='销售订单', index=True)
    project_id = fields.Many2one('project.project', string='项目', index=True)
    cproduct_id = fields.Many2one('product.product', '所做产品', store=True, readonly=True)

    # def _prepare_move_split_vals(self, qty):
    #     res=super(StockMove, self)._prepare_move_split_vals(qty)
    #     if self.sale_line_id:
    #         res['sale_line_id']=self.sale_line_id.id,
    #     return res
    #
    # def _assign_picking(self):
    #     """ 因为销售订单确认时会删除销售订单生成的仓库发货单---- 重写此方法避免name跳号"""
    #     Picking = self.env['stock.picking']
    #     grouped_moves = groupby(sorted(self, key=lambda m: [f.id for f in m._key_assign_picking()]), key=lambda m: [m._key_assign_picking()])
    #     for group, moves in grouped_moves:
    #         moves = self.env['stock.move'].concat(*list(moves))
    #         new_picking = False
    #         # Could pass the arguments contained in group but they are the same
    #         # for each move that why moves[0] is acceptable
    #         picking = moves[0]._search_picking_for_assignation()
    #         if picking:
    #             if any(picking.partner_id.id != m.partner_id.id or
    #                     picking.origin != m.origin for m in moves):
    #                 # If a picking is found, we'll append `move` to its move list and thus its
    #                 # `partner_id` and `ref` field will refer to multiple records. In this
    #                 # case, we chose to  wipe them.
    #                 picking.write({
    #                     'partner_id': False,
    #                     'origin': False,
    #                 })
    #         else:
    #             new_picking = True
    #             """在这里将原方法重写"""
    #             picking_values=moves._get_new_picking_values()
    #             print('picking_values=========', picking_values)
    #             if moves.sale_line_id:
    #                 picking_values.update({'name':'DIRTY_DELIVERY'})
    #                 dirty_picking=self.env['stock.picking'].search([('name','=','DIRTY_DELIVERY')])
    #                 if dirty_picking:
    #                     dirty_picking.unlink()
    #             picking = Picking.create(picking_values)
    #
    #         moves.write({'picking_id': picking.id})
    #         moves._assign_picking_post_process(new=new_picking)
    #     return True

    def _action_assign(self, force_qty=False):
        res = super(StockMove, self)._action_assign(force_qty=force_qty)
        assigned_moves = self.env['stock.move']
        partially_available_moves = self.env['stock.move']
        # Read the `reserved_availability` field of the moves out of the loop to prevent unwanted
        # cache invalidation when actually reserving the move.
        # reserved_availability = {move: move.reserved_availability for move in self}
        roundings = {move: move.product_id.uom_id.rounding for move in self}
        for move in self.filtered(lambda m: m.state in ['confirmed', 'waiting', 'partially_available']):
            rounding = roundings[move]
            # missing_reserved_uom_quantity = move.product_uom_qty - reserved_availability[move]
            # missing_reserved_quantity = move.product_uom._compute_quantity(missing_reserved_uom_quantity,
            #                                                                move.product_id.uom_id,
            #                                                                rounding_method='HALF-UP')
            if float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                assigned_moves |= move
            else:
                # If we don't need any quantity, consider the move assigned.
                # need = missing_reserved_quantity
                # if float_is_zero(need, precision_rounding=rounding):
                #     assigned_moves |= move
                #     continue
                # Reserve new quants and create move lines accordingly.
                forced_package_id = move.package_level_id.package_id or None
                available_quantity = self.env['stock.quant']._get_available_quantity(move.product_id, move.location_id,
                                                                                     package_id=forced_package_id)
                if available_quantity <= 0:
                    continue
                taken_quantity = move._update_reserved_quantity(need, available_quantity, move.location_id,
                                                                package_id=forced_package_id, strict=False)
                if float_is_zero(taken_quantity, precision_rounding=rounding):
                    continue
                if float_compare(need, taken_quantity, precision_rounding=rounding) == 0:
                    assigned_moves |= move
                else:
                    partially_available_moves |= move

        partially_available_moves.write({'state': 'partially_available'})
        assigned_moves.write({'state': 'assigned'})
        return res

    def _prepare_procurement_values(self):
        res = super()._prepare_procurement_values()
        if self.sale_id:
            res['sale_id'] = self.sale_id.id
        if self.sale_line_id:
            res['sale_line_id'] = self.sale_line_id.id
        if self.project_id:
            res['project_id'] = self.project_id.id
        if self.cproduct_id:
            res['cproduct_id'] = self.cproduct_id.id
        return res


class StockRule(models.Model):
    _inherit = 'stock.rule'

    # is_deduction=fields.Boolean(string='扣减库存')

    @api.model
    def _run_pull(self, procurements):
        moves_values_by_company = defaultdict(list)
        for procurement, rule in procurements:
            if not rule.location_src_id:
                msg = _('No source location defined on stock rule: %s!') % (rule.name,)
                raise UserError(msg)
        for procurement, rule in procurements:
            procure_method = rule.procure_method
            product_uom_qty = procurement.product_qty
            virtual_available = sum(self.env['mrp.production'].search([
                ('state', 'not in', ('done', 'cancel')),
                ('product_id', '=', procurement.product_id.id)
            ])
            .mapped(
                'product_qty')) or 0
            sale_available = sum(self.env['sale.order.line'].search([
                ('order_id.state', '!=', 'cancel'),
                ('product_id', '=', procurement.product_id.id)]).mapped('product_uom_qty')) or 0
            pro_qty_available = procurement.product_id.qty_available # 在手
            fact_production_qty = virtual_available + pro_qty_available #  现有数量
            # virtual_available = procurement.product_id.with_context(location=False).virtual_available
            # if rule.is_deduction:
            #     if virtual_available>0:
            #         product_uom_qty -= virtual_available
            #     elif virtual_available<0:
            #         product_uom_qty = -virtual_available
            # 待生产= 总销售-（总在制+在手） 350-150》=200
            if rule.procure_method == 'mts_else_mto':
                if sale_available == 0 or (sale_available-fact_production_qty)>=product_uom_qty:
                    procure_method = 'make_to_order'
                    product_uom_qty = product_uom_qty
                elif fact_production_qty>= sale_available:
                    procure_method = 'make_to_stock'
                    product_uom_qty = 0
                elif fact_production_qty < sale_available:
                    procure_method = 'make_to_order'
                    product_uom_qty = sale_available - fact_production_qty
            # if rule.procure_method == 'mts_else_mto':
            #     if virtual_available > 0:
            #         product_uom_qty -= virtual_available
            #     elif virtual_available < 0:
            #         product_uom_qty = -virtual_available
            #     if product_uom_qty > 0:
            #         procure_method = 'make_to_order'
            #     else:
            #         procure_method = 'make_to_stock'
            if product_uom_qty > 0:
                move_values = rule._get_stock_move_values(*procurement)
                move_values['procure_method'] = procure_method
                move_values['product_uom_qty'] = product_uom_qty
                move_values['sale_id'] = procurement.values.get('sale_id', False)
                move_values['sale_line_id'] = procurement.values.get('sale_line_id', False)
                move_values['project_id'] = procurement.values.get('project_id', False)
                move_values['cproduct_id'] = procurement.values.get('cproduct_id', False)
                moves_values_by_company[procurement.company_id.id].append(move_values)

        for company_id, moves_values in moves_values_by_company.items():
            moves = self.env['stock.move'].sudo().with_company(company_id).create(moves_values)
            moves._action_confirm()
        return True


class StockPickingInherit(models.Model):
    _inherit = "stock.picking"

    sale_delivery_id = fields.Many2one('sale.delivery', string=u"发货通知单")
    delivery_address = fields.Char(string='发货地址', related="sale_delivery_id.delivery_address")
    receiver = fields.Many2one('res.partner', string='收货人', related="sale_delivery_id.receiver")
    phone = fields.Char(string='联系电话', related="sale_delivery_id.phone")

    def action_done(self):
        # result=super(StockPickingInherit, self).action_done()
        # 验证发货通知是否都已发完
        if self.sale_delivery_id:
            self.sale_delivery_id.state = 'done'
        return True
