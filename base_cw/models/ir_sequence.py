# -*- encoding: utf-8 -*-
import logging
import pytz
import time

from datetime import datetime, timedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons import base
import logging

_logger = logging.getLogger(__name__)


class ir_sequence(models.Model):
    _inherit = 'ir.sequence'
    _description = '单据编号规则'

    current_prefix = fields.Char('当前前缀',)
    is_renumber = fields.Boolean('是否重新编号', default=False)
    use_system_date = fields.Boolean('使用系统日期编码', default=True,
                                     help='如为False 并且在next_by_cod中给单据中某一栏位的值，如单据日期，这时即以单据日期栏位编码')

    def get_next_char(self, number_next):
        def _interpolate(s, d):
            if s:
                return s % d
            return ''

        def _interpolation_dict():
            now = range_date = effective_date = datetime.now()
            if self.env.context.get('ir_sequence_date'):
                effective_date = self.env.context.get('ir_sequence_date')
            if self.env.context.get('ir_sequence_date_range'):
                range_date = self.env.context.get('ir_sequence_date_range')

            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, sequence in sequences.items():
                res[key] = effective_date.strftime(sequence)
                res['range_' + key] = range_date.strftime(sequence)
                res['current_' + key] = now.strftime(sequence)

            return res

        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
            interpolated_suffix = _interpolate(self.suffix, d)
            if self.is_renumber:
                if interpolated_prefix != self.current_prefix:
                    seq_name = 'ir_sequence_%03d' % self.id
                    self._cr.execute("SELECT setval('%s', 1, false)" % seq_name)
                    self._cr.commit()
                    number_next = base.models.ir_sequence._select_nextval(self.env.cr, seq_name)
                    self.write({'current_prefix': interpolated_prefix})
        except ValueError:
            raise UserError(_('Invalid prefix or suffix for sequence \'%s\'') % (self.get('name')))
        return interpolated_prefix + '%%0%sd' % self.padding % number_next + interpolated_suffix
