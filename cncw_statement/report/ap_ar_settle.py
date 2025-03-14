# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.addons import base_cw
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_compare



class ap_ar_settle(models.TransientModel):
    _name = 'ap.ar.settle'
    _description = '供应商、客户帐款处理'

    period_id = fields.Many2one('account.period', '期别', ondelete="restrict")

    def action_confirm(self):
        self.ensure_one()
        if self.period_id:
            self._cr.execute("""
                    select ap_monthly_settle(%d,%d,%s);
                    select ar_monthly_settle(%s,%s,%s);
            """%(self.period_id.id, self.period_id.pre_period_id.id, self._uid, self.period_id.id, self.period_id.pre_period_id.id, self._uid,))
