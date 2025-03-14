# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.addons.base_cw.public import merge_line
from odoo.exceptions import UserError


class SubAccountLine(models.Model):
    _inherit = 'sub.account.line'

    account_pay_line_id = fields.Many2one('account.pay.line')
    account_receive_line_id = fields.Many2one('account.receive.line')
    cncw_invoice_move_line_id = fields.Many2one('cncw.invoice.move.line')
    account_pay_offset_line_id = fields.Many2one('account.pay.offset.line')
    account_pay_receive_line_id = fields.Many2one('account.receive.offset.line')
    account_prepaid_id = fields.Many2one('account.prepaid')
