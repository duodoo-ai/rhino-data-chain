# -*- encoding: utf-8 -*-
from odoo import models, fields, api, _

class account_financial_period_wizard(models.TransientModel):
      _name = 'account.financial.period.wizard'

      period_id = fields.Many2one('account.period', string='period', help='',domain=[('special','=',False),('state','=','draft')])

      @api.multi
      def _get_period(self):
        periods = self.env['account.period'].find(dt=None)
        if periods:
            return periods[0].id
        return False

      _defaults = {
        'period_id': _get_period,
      }

      @api.multi
      def cost_compute(self):
          ##现金流表
          cashflow=self.env["account.cash.flow.report"]
          cashflow.generate(self.period_id)
          ##结转损益

          self._cr.execute("""
                           select account_month_settle(%s,%s)
                           """,(self.period_id.id,self._uid));
          return {
            'name': "总帐月结查询",
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.general.ledger.month.settle',
            'view_id': False,
            'domain': [('period_id','=',self.period_id.id)],
            'type': 'ir.actions.act_window',
        }
