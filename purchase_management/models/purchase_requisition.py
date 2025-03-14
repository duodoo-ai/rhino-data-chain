# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class PurchaseRequisitionType(models.Model):
    _name = "purchase.requisition.type"
    _description = "Purchase Requisition Type"
    _order = "sequence"

    name = fields.Char(string='Agreement Type', required=True, translate=True)
    sequence = fields.Integer(default=1)
    exclusive = fields.Selection([
        ('exclusive', 'Select only one RFQ (exclusive)'), ('multiple', 'Select multiple RFQ (non-exclusive)')],
        string='Agreement Selection Type', required=True, default='multiple',
            help="""Select only one RFQ (exclusive):  when a purchase order is confirmed, cancel the remaining purchase order.\n
                    Select multiple RFQ (non-exclusive): allows multiple purchase orders. On confirmation of a purchase order it does not cancel the remaining orders""")
    quantity_copy = fields.Selection([
        ('copy', 'Use quantities of agreement'), ('none', 'Set quantities manually')],
        string='Quantities', required=True, default='none')
    line_copy = fields.Selection([
        ('copy', 'Use lines of agreement'), ('none', 'Do not create RfQ lines automatically')],
        string='Lines', required=True, default='copy')
    active = fields.Boolean(default=True, help="Set active to false to hide the Purchase Agreement Types without removing it.")


class PurchaseRequisitionInherit(models.Model):
    _inherit = "purchase.requisition"

    def _get_type_id(self):
        return self.env['purchase.requisition.type'].search([], limit=1)

    department_id = fields.Many2one('hr.department', string='部门')
    origin = fields.Char(string='源单据')
    type_id = fields.Many2one('purchase.requisition.type',
                              string="申请类型", required=True, default=_get_type_id)
    date_end = fields.Date(string='申请截至日期', tracking=True)
    description_purchase = fields.Text(string='采购说明')
    schedule_date = fields.Date(string='计划交货日期', index=True,
                                help="收到所有产品的预期和计划交付日期",
                                tracking=True)

    
    @api.onchange('user_id')
    def onchange_user_id(self):
        if self.user_id:
            employee_id=self.env['hr.employee'].search([('user_id','=',self.user_id.id)],limit=1)
            if employee_id:
                self.department_id=employee_id.department_id.id

class PurchaseRequisitionLineInherit(models.Model):
    _inherit = "purchase.requisition.line"

    name = fields.Char(string='编号',related='requisition_id.name')
    origin = fields.Char(string='源单据',related='requisition_id.origin')
    vendor_id = fields.Many2one('res.partner',
                                string="供应商",
                                domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                related='requisition_id.vendor_id')
    type_id = fields.Many2one('purchase.requisition.type', string="申请类型",related='requisition_id.type_id')
    ordering_date = fields.Date(string="订购日期",related='requisition_id.date_start')
    date_end = fields.Date(string='申请截至日期',related='requisition_id.date_end')
    user_id = fields.Many2one('res.users', string='申请人',related='requisition_id.user_id',store=True)
    department_id = fields.Many2one('hr.department', related="requisition_id.department_id",string='部门',store=True)
    description_purchase=fields.Text(string='采购说明',related="product_id.description_purchase")
    actual_qty=fields.Float(string='实际数量')
    audit_state=fields.Selection([('yes','是'),('no','否')],string='已审核',default='no')
    schedule_date = fields.Date(string='计划交货日期',related="requisition_id.schedule_date")
    audit_date=fields.Datetime(string='审核时间')
    line_state=fields.Selection([('draft','草稿'),('done','已生成询价单')],string='是否已生成询价单',default='draft')
    
    def create(self,vals):
        if 'product_qty' in vals.keys():
            vals['actual_qty']=vals['product_qty']
        return super(PurchaseRequisitionLineInherit, self).create(vals)
    
    @api.onchange('product_qty')
    def onchange_product_qty(self):
        self.actual_qty=self.product_qty
        
    def action_new_quotation_form(self):
        for line in self:
            if line.audit_state=='no':
                raise UserError(_("含有未审核的申请单明细，请联系管理员审核单据!"))
        view = self.env.ref('purchase_management.view_requisition_line_wizard_form')
        return {
            'name': _('新的询价单'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'requisition.line.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': {'default_line_ids':self.ids},  
        }
    
    