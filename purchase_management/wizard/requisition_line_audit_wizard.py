# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time
from odoo.exceptions import UserError
import json
import werkzeug
import logging
_logger = logging.getLogger(__name__)

class RequisitionLineAuditWizard(models.Model):
    _name="requisition.line.audit.wizard"
    _description="采购申请单明细审核"
    
    line_ids=fields.Many2many('purchase.requisition.line',string='采购申请单明细',required=True)
    
    
    def action_confirm(self):
        self.line_ids.write({
            'audit_state':'yes',
            'audit_date':datetime.utcnow()
        })
