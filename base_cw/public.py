# -*- encoding: utf-8 -*-

import math
from operator import itemgetter
import time
from collections import defaultdict, OrderedDict
from itertools import groupby
from odoo import api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round
import calendar
from datetime import date,  timedelta,datetime

SUB_ACCOUNT_TYPE = [('view', '视图'),
                    ('has', '有辅助核算'),
                    ('none', '无辅助核算'), ]

# 对帐类型
STATEMENT_TYPE = [('S', '销售'), ('P', '采购')]

# 结算类型
STATEMENT_METHOD = [('1', '正常'), ('-1', '冲销'), ]
# 对帐状态
STATEMENT_SOURCE = [('A', '货款'),
                    ('B', '运费'),
                    ('C', '模具费'),
                    ('D', 'PPAP费用'),
                    ('E', '第三方检测费用'),
                    ('F', '内部调整'),
                    ('G', '操作费')]
DC_TYPE = [('D', '借'), ('C', '贷')]
# 对帐状态
STATEMENT_STATE = [('N', '未对帐'), ('P', '部分对帐'), ('A', '已对帐完毕'), ('R', '对帐中')]

# 发票状态
INVOICE_STATE = [('N', '未开发票'), ('P', '部分开发票'), ('A', '已开发票'), ('R', '发票中')]

def get_month_range(start_date=None):
    """获取当月开始日期和结束日期"""
    if start_date is None:
        # print(date.today())  # 2019-03-05  # 今天的日期
        start_date = date.today().replace(day=1)  # 修改当前时间。比如修改成当月1号
        # print(start_date)  # 2019-03-01  当月的第一天日期
    start_date = datetime.strptime(str(start_date.replace(day=1)), '%Y-%m-%d')
    _, days_in_month = calendar.monthrange(start_date.year, start_date.month)
    # print(days_in_month)  # 31   当月总天数31天
    end_date = start_date + timedelta(days=days_in_month)
    # print(end_date)  # 2019-04-01
    return (start_date, end_date)


def merge_line(self, items=None):
    # 以下处理相同科目不同项目 借贷方均有值 合并为一笔 如预收款科目与 应收帐款 用同一科目时
    # 如有备注 不同也要分开滴
    if items is None:
        items = []
    d1 = defaultdict(lambda: defaultdict(float))
    for a, b, k in items:
        key = (k['account_id'], k.get('sub_account_id', False), k['currency_id'], k['exchange_rate'], k.get('name', ''), str(k.get('sub_account_lines', [])))
        d1[key]['amount'] += k.get('credit', 0) * (1.0 if k['dc_type'] == 'D' else -1.0) \
                             + k.get('debit', 0) * (1.0 if k['dc_type'] == 'D' else -1.0)
        d1[key]['lc_amount'] += k.get('lc_credit', 0) * (1.0 if k['dc_type'] == 'D' else -1.0) \
                                + k.get('lc_debit', 0) * (1.0 if k['dc_type'] == 'D' else -1.0)
    dc_items = []
    for k, v in d1.items():
        credit = lc_credit = debit = lc_debit = 0.0
        if v['amount'] > 0.0:
            dc_type = 'D'
            debit = v['amount']
            lc_debit = v['lc_amount']
        elif v['amount'] < 0.0:
            dc_type = 'C'
            credit = -v['amount']
            lc_credit = -v['lc_amount']
        else:
            continue
        dc_item = dict(dc_type=dc_type,
                       account_id=k[0],
                       sub_account_id=k[1],
                       name=k[4],
                       credit=credit,
                       lc_credit=lc_credit,
                       debit=debit,
                       lc_debit=lc_debit,
                       currency_id=k[2],
                       exchange_rate=k[3],
                       )
        if k[5] != '[]':
            dc_item['sub_account_lines'] = eval(k[5])

        dc_items.append((0, 0, dc_item))
    dc_items.sort(key=lambda x: x[2]['dc_type'], reverse=True)
    return dc_items


@api.model
def multi_get_letter(self, str_input):
    if isinstance(str_input, bytes):
        unicode_str = str_input
    else:
        try:
            unicode_str = str_input.decode('utf8')
        except:
            try:
                unicode_str = str_input.decode('gbk')
            except:
                print('unknown coding')
        return
    return_list = []
    for one_unicode in unicode_str:
        return_list.append(single_get_first(self, one_unicode))
    return (''.join(return_list)).upper()


VOUCHER_STATE = [
    ('draft', '草稿'),
    ('in_progress', '等待中'),
    ('quality', '待检验'),
    ('audited', '已审核'),
    ('approved', '已核准'),
    ('confirmed', '已确认'),
    ('assigned', '待审批'),
    ('done', '已完成'),
    ('cancel', '已取消'),
    ('paid', '已付款'),
    ('invoiced', '已开票'),
]

# 状态（客户所处开发状态）
PARTNER_TYPE = [
    ('A', '潜在伙伴'),
    ('B', '正式伙伴'),
]

# 销售方向
SALES_ORIENTATION = [
    ('A', '内销'),
    ('B', '外销'),
]

# 工艺流程类型
MRP_ROUTING_TYPE = [('A', '成品'), ('B', '部件')]

# 制造类型
MANUFACTURE_TYPE = [('A', '冷打'), ('B', '热打')]

# 流程分类
ROUTING_CATEG = [('A', u"线材"), ('B', '成型')]

BUSINESS_TYPE = [
    ('sale', '销售'),
    ('purchase', '采购')
]
# 产品类型
PRODUCT_TYPE = [
    ('A', '原料'),
    ('B', '半成品'),
    ('C', '成品'),
    ('D', '商品'),
    ('E', '耗材'),
    ('F', '设备'),
    ('G', '模具'),
    ('H', '费用'),
    ('Z', '残料'),
]
# 1.原料
# 2.半成品
# 3.製成品  成品
# 4.商品存貨
# 5.耗用材料
# 6.費用
# 7.設備
# 8.其他
# 9.殲料
# 99.未定義

# 采购类型
PURCHASE_ORDER_TYPE = [
    ('A', '产品采购'),
    ('B', '物料采购'),
    ('C', '设备采购'),
    ('D', '模具采购'),
    ('E', '包材采购'),
    ('G', '原材料采购'),
    ('AO', '产品外协采购'),
    ('GO', '线材外协采购'),
    ('DO', '模具外协采购')]
# 请购类型
REQUISITION_TYPE = [
    ('A', '产品请购'),
    ('B', '物料请购'),
    ('C', '设备请购'),
    ('D', '模具请购'),
    ('E', '包材请购'),
    ('G', '原材料请购'),
    ('AO', '产品外协请购'),
    ('GO', '线材外协请购'),
    ('DO', '模具外协请购')]
# 销售类型
SALE_ORDER_TYPE = [
    ('A', '销售内销订单'),
    ('B', '销售外销订单'),
    ('C', '销售库存订单'),
    ('D', '销售样品订单'),
    ('E', '产品代工订单'),
    ('G', '线材销售订单'),
    ('H', '线材库存订单')
]
# 制造属性
MANUFACTURE_ATTRIBUTE = [('A', '仅自制'),
                         ('B', '可自制可委外'),
                         ('C', '仅委外'), ]
# 结案模式
CLOSE_MODE = [('unknown', '未知'),
              ('auto', '自动结案'),
              ('enforce', '强制结案')]

# 原材料类型
RAW_MATERIALS_TYPE = [('A', '盘元'),
                      ('B', '盘元精线'),
                      ('C', '棒元'),
                      ('D', '棒料精线'),
                      ('E', '冷轧带钢')]
# 工序组合类型
ROUTING_TYPE = [
    ('A', '线材改制'),
    ('B', '电镀前'),
    ('C', '电镀后'),
]

# 工时类型
TIME_TYPE = [
    ('A', '定额工时'),
    ('B', '固定工时')
]

# 质量状态
QUALITY_STATE = [('A', '良品'),
                 ('B', '不良品'),
                 ('C', '报废品'),
                 ('D', '待检验品')]


# 计算开始日期与结束日期之间的天数（参数为两个日期格式的文本）
def get_calc_date_difference(tsstart, tsend):
    if len(tsstart.split(':')) > 1:
        tsstart = datetime.strptime(tsstart, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    if len(tsend.split(':')) > 1:
        tsend = datetime.strptime(tsend, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    dtstart = datetime(*time.strptime(tsstart, '%Y-%m-%d')[:3])
    dtend = datetime(*time.strptime(tsend, '%Y-%m-%d')[:3])
    return (dtend - dtstart).days


# # ===============================================
# # 方法名称: get_hr_employee
# # 功能描述: 取得员工对象
# # 输入参数: user_id(用户id)
# # 返 回 值: employee_obj --对象(object)
# # 创 建 人:
# # 创建日期: 2015/12/30
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_hr_employee(self, user_id):
    employee_obj = self.env['hr.employee'].search([('user_id', '=', user_id.id)], limit=1)
    if (employee_obj):
        return employee_obj
    else:
        raise  UserError(_('错误!当前用户没有设置对应的员工信息，不能执行您指定的操作！'))
        return False


# # ===============================================
# # 方法名称: check_float
# # 功能描述: 检查输入的数值是否符合要求
# # 输入参数: import_qty(输入数量),is_min(最小值),message(验证信息)
# # 返 回 值: employee_obj 人员对象(object)
# # 创 建 人:
# # 创建日期: 2016/01/15
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def check_float(import_qty, is_min, message=''):
    if is_min is True:
        if float(import_qty) == 0.0:
            raise  UserError(_('数值输入错误!%s输入的数值不能为零！' % message))
    elif is_min is False:
        if float(import_qty) <= 0.0:
            raise  UserError(_('数值输入错误!%s输入的数值不能小于零！' % message))


# # ===============================================
# # 方法名称: get_add_days
# # 功能描述: 计算当前时间加上N天后的日期
# #          N为0时获取时间戳ts当天的起始时间戳，
# #          N为负数时前数N天，N为正数是后数N天
# # 输入参数: ts:当前时间,N:天数
# # 返 回 值: datetime
# # 创 建 人: Jacky
# # 创建日期: 2016/01/20
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_add_days(ts=datetime.now(), N=0):
    return ts + timedelta(days=N)


# # ===============================================
# # 方法名称: get_differrent_hours
# # 功能描述: # 计算开始时间与结束时间之间的小时数
# # 输入参数: start_time:开始时间,end_time:天数
# # 返 回 值: datetime
# # 创 建 人: Jacky
# # 创建日期: 2016/01/20
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_differrent_hours(start_time, end_time):
    hour = 0.0
    starttime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    endtime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
    hour = float((endtime - starttime).days) * 24
    hour += float((endtime - starttime).seconds) / 3600
    return hour


# # ===============================================
# # 方法名称: get_chinese_money
# # 功能描述: 将小写金额转换大写中文金额
# # 输入参数: num 小写金额
# # 返 回 值: 字符串
# # 创 建 人: Jacky
# # 创建日期: 2016/01/20
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_chinese_money(num=0):
    """
    将小写金额数值转换为中文大写格式
    :param num: 金额数值
    :return:中文大写金额格式
    """
    capUnit = ['万', '亿', '万', '圆', '']
    capDigit = {2: ['角', '分', ''], 4: ['仟', '佰', '拾', '']}
    capNum = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
    snum = str('%019.02f') % num
    if snum.index('.') > 16:
        return ''
    ret, nodeNum, subret, subChr = '', '', '', ''
    CurChr = ['', '']
    for i in range(5):
        j = int(i * 4 + math.floor(i / 4))
        subret = ''
        nodeNum = snum[j:j + 4]
        lens = len(nodeNum)
        for k in range(lens):
            if int(nodeNum[k:]) == 0:
                continue
            CurChr[k % 2] = capNum[int(nodeNum[k:k + 1])]
            if nodeNum[k:k + 1] != '0':
                CurChr[k % 2] += capDigit[lens][k]
            if not ((CurChr[0] == CurChr[1]) and (CurChr[0] == capNum[0])):
                if not ((CurChr[k % 2] == capNum[0]) and (subret == '') and (ret == '')):
                    subret += CurChr[k % 2]
        subChr = [subret, subret + capUnit[i]][subret != '']
        if not ((subChr == capNum[0]) and (ret == '')):
            ret += subChr
    if len(ret) > 1:
        if ret[len(ret) - 1] != '分':
            ret += '整'
    return [ret, capNum[0] + capUnit[3]][ret == '']


# # ===============================================
# # 方法名称: get_product_equipment_mode_scrope
# # 功能描述: 根据当前成型工序及产品直径和长度过滤可使用的设备型号范围
# # 输入参数: process_id 工序对象;product_id:产品对象
# # 返 回 值: 设备集合
# # 创 建 人: Jacky
# # 创建日期: 2016/01/26
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_product_equipment_mode_scrope(self, process_id, product_id):
    list = []
    sq = ("""select process_id from mrp_equipment_production_scope where process_id=%s
                and min_diameter<=%s and (max_diameter>=%s or COALESCE(max_diameter,0)=0)
                and min_length<=%s and (max_length>=%s or COALESCE(max_length,0)=0)""" % (
        process_id.process_id_calc_capacity.id, product_id.diameter, product_id.diameter, product_id.length,
        product_id.length))
    self._cr.execute(sq)
    res = self._cr.fetchone()
    if res:
        # if len(self._cr.fetchall()) > 0:
        sq2 = ("""select equipment_mode_id from mrp_equipment_production_scope
                where process_id=%s and min_diameter<=%s and (max_diameter>=%s or COALESCE(max_diameter,0)=0)
                and min_length<=%s and (max_length>=%s or COALESCE(max_length,0)=0)"""
               % (
                   process_id.process_id_calc_capacity.id, product_id.diameter, product_id.diameter, product_id.length,
                   product_id.length))
    else:
        sq2 = ("""
                select equipment_mode_id from mrp_process_equipment_mode where process_id=%s
            """ % (process_id.id))
    self._cr.execute(sq2)
    res1 = self._cr.fetchall()
    if res1:
        list = filter(None, map(lambda x: x[0], res1))
    return list


# # ===============================================
# # 方法名称: get_product_process_id_list
# # 功能描述: 获取产品工序ID集合
# # 输入参数: product_id:产品ID
# # 返 回 值: list[]
# # 创 建 人: Jacky
# # 创建日期: 2016/01/20
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_product_process_id_list(cr, product_id):
    """ 根据产品ID取得对应的工序ID集合
        @param product_id: 产品id
        @return: 工序ID集合
        """
    process_list = []
    cr.execute(""" select id,code,name from mrp_process where id in (
                    select distinct t7.process_id
                    from product_product as t1
                    left join mrp_routing t2 on t1.id=t2.product_id
                    left join mrp_bom t3 on t2.id=t3.routing_id
                    left join mrp_bom_line t4 on t3.id=t4.master_id and t4.mrp_routing_id is not null
                    left join mrp_routing t5 on t4.mrp_routing_id = t5.id
                    left join mrp_process_group t6 on t5.before_process_group_id=t6.id
                    left join mrp_process_group_line t7 on t6.id=t7.process_group_id
                    where t1.id=%s
		            union
                    select distinct t4.process_id
                    from product_product as t1
                    join mrp_routing t2 on t1.id=t2.product_id
                    join mrp_process_group t3 on t2.before_process_group_id=t3.id
                    join mrp_process_group_line t4 on t3.id=t4.process_group_id
                    where t1.id=%s
                    union all
                    select distinct t4.process_id
                    from product_product as t1
                    join mrp_routing t2 on t1.id=t2.product_id
                    join mrp_process_group t3 on t2.after_process_group_id=t3.id
                    join mrp_process_group_line t4 on t3.id=t4.process_group_id
                    where t1.id=%s
                    union
                    select distinct b.process_id from mrp_process_group a left join mrp_process_group_line b on a.id=b.process_group_id
                    where a.routing_type='A' and exists(select * from product_product where id=%s and product_type='A')) order by code
                    """ % (product_id, product_id, product_id, product_id))
    process_list = filter(None, map(lambda x: x[0], cr.fetchall()))
    return process_list


# # ===============================================
# # 方法名称: get_stock_qty
# # 功能描述: 取当前库存,default group by 以下参数;目前扩展了 材质、品牌、和订单明细。以后可以识需求增加要判断的栏位
# # 输入参数: product_id/package_id/lot_id/partner_id/location_id
# # 返 回 值: qty
# # 创 建 人: Sunshine
# # 创建日期: 2023/3/10
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_stock_qty(self, product_id=None, package_id=None, lot_id=None, partner_id=None, location_id=None, **kwargs):
    selectSql = """
        select cast(sum(a.quantity)-sum(coalesce(a.reserved_quantity,0)) as numeric(16,3)) as stock_qty,
               a.company_id,a.product_id,a.package_id,a.lot_id,a.owner_id
    """
    fromSql = """
          from stock_quant a left join stock_location b on a.location_id=b.id
                            --left join stock_location c on c.name='Stock' and b.parent_left between c.parent_left and c.parent_right
                             left join product_product d on a.product_id=d.id
                             left join product_template e on d.product_tmpl_id=e.id
                             left join stock_quant_package f on a.package_id=f.id
                             left join stock_lot g on a.lot_id=g.id and a.product_id=g.product_id
                             left join res_partner h on a.owner_id=h.id
    """
    whereSql = """
         where 1=1 and 
           (b.usage = 'internal' or b.usage = 'transit')
    """

    groupbySql = """
    group by a.company_id,a.product_id,a.package_id,a.lot_id,a.owner_id
    """
    if product_id:
        if isinstance(product_id, int):
            whereSql += """
            and a.product_id={product_id}
            """.format(product_id=product_id)
        else:
            whereSql += " and (d.default_code ilike '%{default_code}%' or e.name ilike '%{product_name}%')".format(
                default_code=product_id, product_name=product_id)
    if package_id:
        if isinstance(package_id, int):
            whereSql += """and a.package_id={package_id}
            """.format(package_id=package_id)
        else:
            whereSql += """
            and f.name ilike '%{package_name}%'
            """.format(package_name=package_id)
    if lot_id:
        if isinstance(lot_id, int):
            whereSql += """and a.lot_id={lot_id}
            """.format(lot_id=lot_id)
        else:
            whereSql += """and g.name ilike '%{lot_name}%'
            """.format(lot_name=lot_id)
    if kwargs.get('partner_relationship', False):  # 考虑客户下单关系 默认是不考虑的
        if partner_id:
            if isinstance(partner_id, int):
                sql = """
                       select b.partner_id as parent_partner_id
                          from sale_partner_relationship_line a left join sale_partner_relationship b on a.master_id=b.id
                         where a.partner_id={0}
                         union
                        select id as parent_partner_id
                          from res_partner
                         where id={1}
                           and customer='t'
                """.format(partner_id, partner_id)
            # sql="""select parent_partner_id from sale_partner_relationship_view where partner_id={0}""".format(partner_id)
            else:
                sql = """
                    select parent_partner_id
                      from sale_partner_relationship_view left join res_partner b on a.partner_id=b.id
                     where b.name ilike '%%s%'
                """ % partner_id

            self.env.cr.execute(sql)
            partner_ids = filter(None, map(lambda x: x[0], self.env.cr.fetchall()))
            if len(partner_ids) == 1:
                whereSql += """and a.owner_id ={partner_id}
                """.format(partner_id=partner_ids[0])
            else:
                # partner_ids=filter(None,map(lambda x:x[0],results))
                # partner_ids = math(itemgetter(0),self.env.cr.fetchall())
                whereSql += """and a.owner_id in {partner_ids}
                        """.format(partner_ids=tuple(partner_ids))
    else:
        if partner_id:
            if isinstance(partner_id, int):
                whereSql += """and a.owner_id ={partner_id}
                """.format(partner_id=partner_id)
    if location_id:
        if isinstance(location_id, int):
            whereSql += """and a.location_id = {location_id}
            """.format(location_id=location_id)
        else:
            whereSql += """and c.name ilike '%{location_name}%'
            """.format(location_name=location_id)

    obj = self.env['stock.lot'].browse()

    if kwargs.get('sale_line_id', False):  # 订单明细
        try:
            getattr(obj, 'sale_line_id')
            if isinstance(kwargs.get('sale_line_id'), int):
                selectSql += """,sale_line_id
                """
                whereSql += """and g.sale_line_id = {sale_line_id}
                """.format(sale_line_id=kwargs.get('sale_line_id'))
                groupbySql += """,sale_line_id
                """
        except AttributeError:
            pass

    sql = selectSql + fromSql + whereSql + groupbySql
    self._cr.execute(sql)
    qty = self._cr.fetchone()
    if qty:
        return qty[0]
    else:
        return 0


# # ===============================================
# # 方法名称: get_stock_qty
# # 功能描述: 取当前库存,default group by 以下参数;目前扩展了 材质、品牌、和订单明细。以后可以识需求增加要判断的栏位
# # 输入参数: product_id/package_id/lot_id/partner_id/location_id
# # 返 回 值: 库存明细
# # 创 建 人: Sunshine
# # 创建日期: 2023/3/10
# # 更 新 人:
# # 更新日期:
# # 更新说明: 暂无
# # ===============================================
def get_stock_quants(self, product_id=None, package_id=None, lot_id=None, partner_id=None, location_id=None, **kwargs):
    selectSql = """
        select 
               cast(a.quantity-coalesce(a.reserved_quantity,0) as numeric(16,3)) as stock_qty,
               a.company_id,a.product_id,a.package_id,a.lot_id,a.owner_id
    """
    fromSql = """
          from stock_quant a left join stock_location b on a.location_id=b.id
 
                             left join product_product d on a.product_id=d.id
                             left join product_template e on d.product_tmpl_id=e.id
                             left join stock_quant_package f on a.package_id=f.id
                             left join stock_lot g on a.lot_id=g.id and a.product_id=g.product_id
                             left join res_partner h on a.owner_id=h.id
    """
    whereSql = """
         where 1=1
           --and quality_state='A'
           and b.usage = 'internal'
    """
    if product_id:
        if isinstance(product_id, int):
            whereSql += """
            and a.product_id={product_id}
            """.format(product_id=product_id)
        else:
            whereSql += " and (d.default_code ilike '%{default_code}%' or e.name ilike '%{product_name}%')".format(
                default_code=product_id, product_name=product_id)
    if package_id:
        if isinstance(package_id, int):
            whereSql += """and a.package_id={package_id}
            """.format(package_id=package_id)
        else:
            whereSql += """
            and f.name ilike '%{package_name}%'
            """.format(package_name=package_id)
    if lot_id:
        if isinstance(lot_id, int):
            whereSql += """and a.lot_id={lot_id}
            """.format(lot_id=lot_id)
        else:
            whereSql += """and g.name ilike '%{lot_name}%'
            """.format(lot_name=lot_id)
    if kwargs.get('partner_relationship', False):  # 考虑客户下单关系 默认是不考虑的
        if partner_id:
            if isinstance(partner_id, int):
                sql = """
                       select b.partner_id as parent_partner_id
                          from sale_partner_relationship_line a left join sale_partner_relationship b on a.master_id=b.id
                         where a.partner_id={0}
                         union
                        select id as parent_partner_id
                          from res_partner
                         where id={1}
                           and customer='t'
                """.format(partner_id, partner_id)
            # sql="""select parent_partner_id from sale_partner_relationship_view where partner_id={0}""".format(partner_id)
            else:
                sql = """
                    select parent_partner_id
                      from sale_partner_relationship_view left join res_partner b on a.partner_id=b.id
                     where b.name ilike '%%s%'
                """ % partner_id

            self.env.cr.execute(sql)
            partner_ids = filter(None, map(lambda x: x[0], self.env.cr.fetchall()))
            if len(partner_ids) == 1:
                whereSql += """and a.owner_id ={partner_id}
                """.format(partner_id=partner_ids[0])
            else:
                # partner_ids=filter(None,map(lambda x:x[0],results))
                # partner_ids = math(itemgetter(0),self.env.cr.fetchall())
                whereSql += """and a.owner_id in {partner_ids}
                        """.format(partner_ids=tuple(partner_ids))
    else:
        if partner_id:
            if isinstance(partner_id, int):
                whereSql += """and a.owner_id ={partner_id}
                """.format(partner_id=partner_id)
    if location_id:
        if isinstance(location_id, int):
            whereSql += """and a.location_id = {location_id}
            """.format(location_id=location_id)
        else:
            whereSql += """and c.name ilike '%{location_name}%'
            """.format(location_name=location_id)

    obj = self.env['stock.lot'].browse()

    if kwargs.get('sale_line_id', False):  # 订单明细
        try:
            getattr(obj, 'sale_line_id')
            if isinstance(kwargs.get('sale_line_id'), int):
                selectSql += """,sale_line_id
                """
                whereSql += """and g.sale_line_id = {sale_line_id}
                """.format(sale_line_id=kwargs.get('sale_line_id'))

        except AttributeError:
            pass

    sql = selectSql + fromSql + whereSql
    orderSql = """order by a.in_date,a.id
    """
    if kwargs.get('removal_strategy', 'fifo') != 'fifo':
        orderSql = """order by a.in_date desc,a.id desc
        """
    sql += orderSql
    self._cr.execute(sql)
    quants = filter(None, map(lambda x: x[0], self._cr.fetchone()))
    return quants or []


# ===============================================================================
# # 方法: get_user_by_partner
# # Copyright(c): Hailun
# # 功能描述: 根据客户查找所有可以查看订单的用户清单
# # 创 建 人: Jacky
# # 创建日期: 2016/3/17
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
def get_user_by_partner(self, partner_id):
    """
    根据客户查找所有可以查看订单的用户清单
    :param partner_id:客户ID
    :return: 用户集合
    """
    self._cr.execute("""select distinct c.user_id from res_partner_support_line a left join res_users_parent b on a.user_id=b.user_id
                                                                                  left join res_users_parent c on b.user_id=c.user_id or b.parent_user_id=c.user_id
                        where a.partner_id=%s""" % (partner_id))
    return filter(None, map(lambda x: x[0], self._cr.fetchall()))


# ===============================================================================
# # 方法: get_partner_by_user
# # Copyright(c): Hailun
# # 功能描述: 根据用户查找所有可以查看的客户清单
# # 创 建 人: Jacky
# # 创建日期: 2016/3/17
# # 更 新 人:
# # 更新日期:
# # 更新说明:
# ===============================================================================
def get_partner_by_user(self, user_id):
    self._cr.execute("""select distinct partner_id from (
                    select distinct b.partner_id from res_users_parent a
                    left join res_partner_support_line b on a.user_id=b.user_id or a.parent_user_id=b.user_id
                    where a.parent_user_id=%s and b.partner_id is not null
                    union all
                    select c.id from res_groups_users_rel a left join ir_model_data b on a.gid=b.res_id
                    left join res_partner c on 1=1
                    where b.name='group_partner_all' and a.uid=%s
                    union all
                    select c.id from res_groups_users_rel a left join ir_model_data b on a.gid=b.res_id
                    left join res_partner c on sales_orientation='A'
                    where b.name='group_partner_domestic' and a.uid=%s
                    union all
                    select c.id from res_groups_users_rel a left join ir_model_data b on a.gid=b.res_id
                    left join res_partner c on sales_orientation='B'
                    where b.name='group_partner_export' and a.uid=%s
                    ) a""" % (user_id, user_id, user_id, user_id))
    return filter(None, map(lambda x: x[0], self._cr.fetchall()))


@api.model
def generate_voucher_no(self, vals=None, code=None, voucher_date=None):
    """
    生成单据编号  在程式 create 中调用
    :param self:
    :param vals:
    :return:
    :author: MF
    """
    if code is None:
        code = self._name
    if vals is None:
        vals = dict()
    if isinstance(vals, dict):  # 检查 vals 是否为字典
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.sudo().env['ir.sequence'].next_by_code(code) or 'New'
    else:
        raise ValueError("vals should be a dictionary, but got {}".format(type(vals)))

@api.model
def generate_sequence(self, vals, master_column='master_id'):
    """
    取表中[项次]的最大值+1 作为当前笔的 项次值
    1.在程式 create 中调用,更新单档中sequence栏位值，
    2.在程式 create 中调用, 更新明细档中sequence栏位值，
      限制:明细档对应主档的外键栏位名称必须是master_id
    :param self:
    :param vals:
    :return:
    :author: MF
    """
    if vals is None:
        vals = dict()
    sql = """select coalesce(max(sequence),0) from %s """ % (self._table,)
    if isinstance(vals, dict):  # 检查 vals 是否为字典
        if vals.get(master_column, False):
            sql += """ where %s=%s """ % (master_column, vals.get(master_column),)
    else:
        raise ValueError("vals should be a dictionary, but got {}".format(type(vals)))
    self._cr.execute(sql)
    vals['sequence'] = self._cr.fetchone()[0] + 1


@api.model
def add_customer_relationship(self, partner_id=None, sql=None):
    """
    增加当前客户对应的客户下关系 组成客户范围 进行库存查找
    :param partner_id:
    :param sql:
    :return:
    """
    if sql is None:
        raise  UserError(_('提示!sql 参数没有传值!'))
    if not partner_id:
        raise  UserError(_('提示!客户取值不正确!'))  # and isinstance(partner_id,type('res.partner'))
    partner_ids = [r.master_id.partner_id.id for r in
                   self.env['sale.partner.relationship.line'].search(
                       [('partner_id', '=', self.master_id.partner_id.id)])]
    partner_ids.append(self.master_id.partner_id.id)
    if len(partner_ids) == 1:
        sql += " and a.owner_id = %s" % (partner_ids[0])
    elif len(partner_ids) > 1:
        sql += " and a.owner_id in %s" % (tuple(partner_ids),)
    pass


@api.model
def get_partner_relationship(self, partner_id=False):
    """
    取有下单关系的客户
    返回值为 list
    """
    if not isinstance(partner_id, int):
        return False
    sql = """--
           select distinct a.partner_id,b.partner_id as parent_partner_id
             from sale_partner_relationship_line a left join sale_partner_relationship b on a.master_id=b.id
            where a.partner_id = %s
            union
           select id as  partner_id,id as parent_partner_id from res_partner
            where customer='t' and active='t'
              and id=%s
    """ % (partner_id, partner_id)
    self._cr.execute(sql)
    return map(itemgetter(1), self._cr.fetchall())


@api.model
def create_taking_barcode(self, product_type='A', is_required=False):
    """
    创建 盘点barcode    default 是不创建的
    :param self:
    :param product_type:
    :param is_required:
    :return:
    """
    barcode = False
    if is_required and product_type in ("A", 'E'):  # 产品/包材
        barcode = self.env['ir.sequence'].next_by_code('stock.taking.barcode') or 'New'
    return barcode


@api.model
def get_conversion_rate(self, from_currency, to_currency, from_currency_rate=0.0, to_currency_rate=0.0):
    """
    不同币别 转换率
    :param self:
    :param from_currency:
    :param to_currency:
    :param from_currency_rate:
    :param to_currency_rate:
    :return:
    """
    if not from_currency_rate:
        from_currency_rate = from_currency.rate or 1.0
    if not to_currency_rate:
        to_currency_rate = to_currency.rate or 1.0
    if to_currency_rate > 0 and to_currency_rate < 1:
        return from_currency_rate / to_currency_rate
    else:
        return from_currency_rate / to_currency_rate


@api.model
def compute_amount(self, from_currency, to_currency, from_amount, from_currency_rate=0.0,
                   to_currency_rate=0.0, round=True, custom_round=False, custom_rounding=2):
    """
    不同币别 金额转换
    :param self:
    :param from_currency:
    :param to_currency:
    :param from_amount:
    :param from_currency_rate:
    :param to_currency_rate:
    :param round:
    :param custom_round:自定义精度 参适应单价的币别转换
    :param custom_rounding: 自定义精度数值
    :return:
    """
    if to_currency.id == from_currency.id and from_currency_rate == to_currency_rate:
        if round:
            return to_currency.round(from_amount)
        else:
            return from_amount
    else:
        rate = get_conversion_rate(self, from_currency, to_currency, from_currency_rate=from_currency_rate,
                                   to_currency_rate=to_currency_rate)
        if round:
            if custom_round:
                return float_round(from_amount * rate, precision_rounding=custom_rounding)
            else:
                return to_currency.round(from_amount * rate)
        else:
            return from_amount * rate


@api.model
def get_converted_qty(self, product_id, from_unit, from_qty, to_unit, from_unit_rate=0, round=True,
                      rounding_method='UP'):
    """
    采购单位数量 转换为 库存单位数量 或相反
    from_unit  转换前单位
    to_unit    转换后单位
    """
    from_unit = product_id.unit_ids.filtered(lambda x: x.unit_id == from_unit) and \
                product_id.unit_ids.filtered(lambda x: x.unit_id == from_unit)[0]
    to_unit = product_id.unit_ids.filtered(lambda x: x.unit_id == to_unit) and \
              product_id.unit_ids.filtered(lambda x: x.unit_id == to_unit)[0]
    to_qty = compute_qty(self, from_unit, from_qty, to_unit, from_unit_rate=0, round=True, rounding_method='UP')
    return to_qty


@api.model
def compute_qty(self, from_unit, qty, to_unit, from_unit_rate=0, round=True, rounding_method='UP'):
    """
    from_unit / to_unit 均为货品辅助单位
    from_unit_rate 指定单位换算率
    """
    if (not from_unit or not qty or not to_unit
            or (to_unit.unit_id == from_unit.unit_id)):
        return qty
    if from_unit_rate:
        qty /= from_unit_rate
    else:
        qty /= from_unit.unit_rate
    if to_unit:
        qty *= to_unit.unit_rate
    if round:
        qty = float_round(qty, precision_rounding=to_unit.unit_id.rounding, rounding_method=rounding_method)
    return qty


@api.model
def get_converted_price(self, product_id, from_unit, from_price, to_unit, from_unit_rate=0, ):
    """
    采购单位数量 转换为 库存单位数量 或相反
    from_unit  转换前单位
    to_unit    转换后单位
    """
    from_unit = product_id.unit_ids.filtered(lambda x: x.unit_id == from_unit) and \
                product_id.unit_ids.filtered(lambda x: x.unit_id == from_unit)[0]
    to_unit = product_id.unit_ids.filtered(lambda x: x.unit_id == to_unit) and \
              product_id.unit_ids.filtered(lambda x: x.unit_id == to_unit)[0]
    to_price = compute_price(self, from_unit, from_price, to_unit, from_unit_rate=0)
    return to_price


@api.model
def compute_price(self, from_unit, from_price, to_unit, from_unit_rate=0):
    """
    from_unit / to_unit 均为货品辅助单位
    from_unit_rate 指定单位换算率
    """
    price = from_price
    if (not from_unit or not price or not to_unit
            or (to_unit.unit_id.id == from_unit.unit_id.id)):
        return price
    if from_unit_rate:
        price *= from_unit_rate
    else:
        price *= from_unit.unit_rate
    if to_unit:
        price /= to_unit.unit_rate
    return price


# 计算开始日期与结束日期之间的天数（参数为两个日期格式的文本）
def get_days_between_date(start_date, end_date):
    if start_date and len(start_date.split(':')) > 1:
        start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    if end_date and len(end_date.split(':')) > 1:
        end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    dtstart = datetime(*time.strptime(start_date, '%Y-%m-%d')[:3])
    dtend = datetime(*time.strptime(end_date, '%Y-%m-%d')[:3])
    return (dtend - dtstart).days


@api.model
def update_quant(self, r):
    quant_ids = r.op_ids.filtered(lambda x: x.quant_id).mapped('quant_id.id')
    self._cr.execute(""" update stock_quant set voucher_line_id=null,
                                                    picking_type_id=null,
                                                    reservation_voucher=null
                          where id in %s """, (tuple(quant_ids),))


# 判断当前数据记录是否有重复，主要用于Create事件
@api.model
def check_unique(self, param=[], values=None, message=False):
    sql = "select count(id) count from %s where (true)" % self._table
    if self.id:
        sql = "select count(id) count from %s where id!=%s" % (self._table, self.id)
    for r in param:
        if r == 'code' or r == 'name' or r == 'acc_number' or r == 'bic' or r == 'default_code':
            sql += """ and upper(%s) = '%s'""" % (r, values[r].strip().upper())
            if len(values[r]) > len(values[r].strip()):
                raise  UserError(_('输入错误!%s的数据有空格，请重新输入！' % (message and message or '')))
        else:
            if r in values and values[r]:
                sql += """ and %s = '%s'""" % (r, values[r])
            else:
                sql += """ and %s is null""" % (r)
    self._cr.execute(sql)
    res = self._cr.fetchone()
    if res and res[0] > 0:
        raise  UserError(_('输入错误!%s不能重复增加相同的数据！' % (message and message or '')))


@api.model
def get_single_first_letter(self, str_input):
    if isinstance(str_input, bytes):
        unicode_str = str_input
    else:
        try:
            unicode_str = str_input.decode('utf8')
        except:
            try:
                unicode_str = str_input.decode('gbk')
            except:
                print('unknown coding')
        return
    return_list = []
    for one_unicode in unicode_str:
        return_list.append(single_get_first(self, one_unicode))
    return (''.join(return_list)).upper()


@api.model
def single_get_first(self, unicode1):
    str1 = unicode1.encode('gbk')
    try:
        ord(str1)
        return str1
    except:
        asc = ord(str1[0]) * 256 + ord(str1[1]) - 65536
        if -20319 <= asc <= -20284:
            return 'a'
        if -20283 <= asc <= -19776:
            return 'b'
        if -19775 <= asc <= -19219:
            return 'c'
        if -19218 <= asc <= -18711:
            return 'd'
        if -18710 <= asc <= -18527:
            return 'e'
        if -18526 <= asc <= -18240:
            return 'f'
        if -18239 <= asc <= -17923:
            return 'g'
        if -17922 <= asc <= -17418:
            return 'h'
        if -17417 <= asc <= -16475:
            return 'j'
        if -16474 <= asc <= -16213:
            return 'k'
        if -16212 <= asc <= -15641:
            return 'l'
        if -15640 <= asc <= -15166:
            return 'm'
        if -15165 <= asc <= -14923:
            return 'n'
        if -14922 <= asc <= -14915:
            return 'o'
        if -14914 <= asc <= -14631:
            return 'p'
        if -14630 <= asc <= -14150:
            return 'q'
        if -14149 <= asc <= -14091:
            return 'r'
        if -14090 <= asc <= -13119:
            return 's'
        if -13118 <= asc <= -12839:
            return 't'
        if -12838 <= asc <= -12557:
            return 'w'
        if -12556 <= asc <= -11848:
            return 'x'
        if -11847 <= asc <= -11056:
            return 'y'
        if -11055 <= asc <= -10247:
            return 'z'
    return ''
