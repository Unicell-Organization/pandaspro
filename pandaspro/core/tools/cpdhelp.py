HELP_TOPIC_KEYWORDS = {
    'tab': (
        'tab', 'cpdtab', '交叉', '频数', 'pivot', 'cpdtab2', 'cpdtabd', 'cpdtabt',
        'cpdtab2s', 'cpdtab2pct', 'cpdtab2spct', 'percent', '百分比', 'pct',
        'sum', 'mean', '小计', 'subtotal', '___', '多维',
        'nototal', 'tdiff', 'tratio', 'tsort', 'diff', 'ratio', '差值', '比值',
        'first', 'last', '宽表', '摊',
        'rename_agg', 'set_field_rules', 'field_rules', 'share', '占比', '规则', 'total_label', 'to_excel',
    ),
    'magic': ('cpdlist', 'cpddict', 'cpdf', 'cpdfnot', 'cpdisna', 'cpdnotna', '魔法', 'cpd_'),
    'scan': ('singleton', 'scan', '自检', 'tab_singleton', '计数为', 'duplicate', 'dup', '重复', '去重'),
    'filter': ('filter', '筛选', 'inlist', 'inrange', 'dfilter', 'indate', 'cpdf'),
    'data': ('列', '排序', 'csort', 'corder', 'merge', 'export', 'varnames', 'lowervarlist', 'add_total'),
}

HELP_TOPICS = {
    'all': """
FramePro / cpdBaseFrame 快速帮助
================================
用法: df.cpdhelp()           # 总览
      df.cpdhelp('tab')      # 频数 / 交叉表
      df.cpdhelp('magic')    # cpd* 魔法属性总览
      df.cpdhelp('scan')     # 批量自检 / 重复检查
      df.cpdhelp('filter')   # 筛选魔法属性
      df.cpdhelp('data')     # 列操作 / 排序 / 筛选方法

可用主题: all, tab, magic, scan, filter, data
  df.askai('问题')             AI 辅助（需 local.yaml 配置 api_key）
  df.askai('问题', topic='tab')  指定检索主题
""",
    'tab': """
Tab / 交叉表（cpdtab 系列）
===========================

【单列频数】
  df.tab('gender')              方法调用，brief 模式
  df.cpdtab_gender              同上（魔法属性）
  df.cpdtabd_gender             detail 模式（含 Percent、Cum.）
  df.cpdtabt_gender             detail 精简版（仅取值 + count）

【两维交叉计数 — 最常用】
  df.cpdtab2_行字段__列字段
  例: df.cpdtab2_region__grade     → region × grade 计数表（含 Total）

【两维交叉 + 分组小计】
  df.cpdtab2s_行字段__列字段
  例: df.cpdtab2s_region__grade    → 在 cpdtab2 基础上加 Subtotal 行/列

【两维交叉 + 百分比（0–100，保留 2 位小数）】
  df.cpdtab2pct_行__列          占全体比例（默认）
  df.cpdtab2pctrow_行__列       行内比例（每行数据列之和 100%）
  df.cpdtab2pctcol_行__列       列内比例（每列数据行之和 100%）
  例: df.cpdtab2pct_region__grade
      df.cpdtab2pctrow_gender__dept

  带 Subtotal 小计:
  df.cpdtab2spct_ / cpdtab2spctrow_ / cpdtab2spctcol_
  例: df.cpdtab2spctrow_region__grade

【两维交叉 + 聚合函数】
  df.cpdtab2{agg}_行__列__值字段
  agg: sum mean median min max std var first last
  例: df.cpdtab2sum_region__grade__salary

  first / last 不是汇总，而是每格只取第一行 / 最后一行的值，用来把长表摊成宽表
  （格子里放文字，如部门、职级）；结果不带 Total。
  例: df.cpdtab2first_upi__snapshot__unit   → 一人一行，每个时点一列，格子里是部门
      等价于 drop_duplicates(['upi', 'snapshot'], keep='first') 之后把 snapshot 摊成列

【多维 index / columns — 用 ___ 分隔两侧】
  格式: cpdtab2_行1__行2___列1__列2
  例: df.cpdtab2_region__dept___quarter__category
  带聚合: df.cpdtab2sum_region___quarter__salary
         （___ 前为 index 字段，后为 columns + 最后的 value 字段）

分隔符速记
  __   同一侧多个字段
  ___  index 侧 与 columns 侧 的分界

除 cpdtab2 外，多维表也可用 cpdtab2s（要小计）、cpdtab2pct*（要百分比）或 cpdtab2sum 等（要聚合）。
字段超过两个（聚合超过三个）时必须写 ___，否则报错。

【字段规则 — 登记一次，之后 cpdtab2_ / cpdtab2sum_ 等直接出成品表】
  import pandaspro as cpd
  cpd.set_field_rules('org', order=['IBRD/IDA', 'IFC', 'MIGA'], total_label='WBG')
  cpd.set_field_rules('open_term', order=['Open', 'Term'], share={'value': 'Open', 'label': '% Open'})
  cpd.set_field_rules('loc_new', order=['Staff HQ', 'Staff non-HQ'], label='Locations')
  cpd.set_tab_defaults(total_position={'rows': 'last', 'cols': 'first'})
  df.cpdtab2_loc_new___org__open_term   → WBG / IBRD/IDA / IFC / MIGA 各有 Open、Term、% Open
  cpd.field_rules() 查看已登记的规则；cpd.clear_field_rules() 清空。
  没有登记规则的字段，输出和以前完全一样。cpdtab2s_ 和 cpdtab2pct* 不受规则影响。

  有规则时的不同: 多层字段的每一级都有合计（从数据重算）；空格子是 0；
                 缺失值显示为 (blank) 并计入合计；order 里列出的取值即使没有数据也保留。

【方法写法 — 参数直接传，不依赖登记】
  df.cpdtab2('loc_new', ['org', 'open_term'],
             total_labels={'org': 'WBG'}, total_position={'cols': 'first'},
             order={'org': [...]}, shares=[{'field': 'open_term', 'value': 'Open', 'label': '% Open'}])
  其他参数: values / aggfunc、totals='both'|'rows'|'cols'|'none'、nested_totals、
           pct_of_total={'field': 'org', 'label': '% of Total'}、fill_value、dropna_label、labels

【合计改名】
  结果.rename_agg(org='WBG')            把 org 这个字段的合计改名，数字不变，可连写
  结果.rename_agg(org='WBG', loc_new='All locations')

【规则表的展示】
  结果.display()        格式化成文字：1,234、0 显示为 -、占比 80.0%
  结果.style            Jupyter 里带格式显示，合计加粗
  结果.to_excel(path)   写出带格式的 Excel，数字仍是数字

【展示选项 — 接在任意 cpdtab2 系列结果后面，不用括号，可连写】
  .nototal              去掉右侧 Total 列
  .nototalrow           去掉底部 Total 行
  .nototalall           两个都去掉
  .tdiff                恰好两个数据列时：后减前，新增 Diff 列
  .tdiff_A__C           A − C（反过来写 .tdiff_C__A）
  .tratio / .tratio_A__C   比值 A ÷ C，新增 Ratio 列（保留 2 位小数）
  .tsort_列             按该列从小到大（.tsort 不带列名 = 第 1 列）
  .tsortd_列            按该列从大到小
  例: df.cpdtab2_region__grade.nototal.tdiff_A__C.tsortd_Diff
      df.cpdtab2pctrow_region__grade.tdiff_A__C     （百分比表的 Diff 是百分点）

  列的写法: 先按列名找，找不到再按位置（从 1 起）。取值含空格等写不成属性时用位置，
           例 .tdiff_1__2 = 第 1 列 − 第 2 列。
  规则: Total 行不参与排序，始终在底部；多层行索引时在每个分组内部排序。
       Total / Subtotal 列不参与 tdiff / tratio。
       计数表用了这些选项后，空格子当 0，数字显示成整数。
""",
    'magic': """
cpd* 魔法属性速查
=================
命名规则: cpd{功能}_{字段1__字段2__...}
字段名用双下划线 __ 连接；支持通配符（与 parse_wild 一致）。

cpdlist_字段          唯一值列表
cpddict_键__值        键值字典
cpdf_字段__取值       等于某取值的行
cpdfnot_字段__取值    不等于某取值的行
cpdisna_字段          该字段为 NA 的行
cpdnotna_字段         该字段非 NA 的行
cpdtab_ / cpdtabd_ / cpdtabt_     单列 tab（见 cpdhelp('tab')）
cpdtab2_ / cpdtab2s_ / cpdtab2pct_ / cpdtab2sum_  多维交叉表（见 cpdhelp('tab')）
.nototal / .tdiff / .tratio / .tsort_列 / .tsortd_列  交叉表展示选项（见 cpdhelp('tab')）

查看某一类详情: df.cpdhelp('tab') 或 df.cpdhelp('filter')
""",
    'scan': """
批量自检
========
  df.tab_singleton_scan()       找「恰好 1 个 count=1」的字段（默认 n=1）
  df.tab_singleton_scan(n=10)   找「恰好 1 个 count=10」的字段

规则: 唯一取值类别 > 30 的列跳过；≤ 30 时用 tab 统计。
返回 field / value / count，并打印报告。

重复检查（仿 Stata duplicates report）
  df.duplicates_report('upi')             按 upi 统计重复分布
  df.duplicates_report('upi', d='detail')   列出哪些 upi 重复、各重复几份
  df.duplicates_report(['upi', 'year'])   按多字段组合判断重复
  df.duplicates_report('upi', dropna=True)  缺失的 upi 不参与统计
  df.show_duplicates(['upi'])             取出多余的重复行（每组保留第一行之外的）

默认返回 copies / observations / surplus；d='detail' 返回 upi / copies。都会打印一行汇总。
""",
    'filter': """
筛选
====
方法:
  df.inlist('col', val1, val2)
  df.inrange('col', start, stop)
  df.dfilter({...})
  df.indate(...)

魔法属性:
  df.cpdf_字段__取值
  df.cpdfnot_字段__取值
  df.cpdisna_字段
  df.cpdnotna_字段
""",
    'data': """
列 / 排序 / 结构
================
  df.varnames              列名
  df.csort('col', order=[...])
  df.corder('col')
  df.lowervarlist()
  df.merge(...)            增强 merge
  df.add_total(...)        追加合计行

导出相关（cpdBaseFrame）:
  df.er                    Export 重命名视图
  df.export_build(path)    构建 Excel 导出
""",
}


def get_help_text(topic: str = 'all') -> str:
    """返回指定主题的 help 文本；未知主题时返回 all。"""
    key = (topic or 'all').strip().lower()
    if key not in HELP_TOPICS:
        key = 'all'
    return HELP_TOPICS[key].strip()


def route_help_topics(question: str, hint: str | None = None) -> list[str]:
    """根据问题关键词（及可选 hint）路由到 help 主题列表。"""
    if hint:
        key = hint.strip().lower()
        if key in HELP_TOPICS and key != 'all':
            return [key]

    q = (question or '').lower()
    scores = {}
    for topic, keywords in HELP_TOPIC_KEYWORDS.items():
        scores[topic] = sum(1 for kw in keywords if kw in q)

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    if ranked[0][1] > 0:
        top_score = ranked[0][1]
        return [t for t, s in ranked if s == top_score]

    return ['all']


def build_retrieval_context(question: str, hint: str | None = None) -> tuple[str, list[str]]:
    """拼装 askai 使用的文档上下文与主题列表。"""
    topics = route_help_topics(question, hint)
    parts = [get_help_text(t) for t in topics]
    if 'all' not in topics:
        parts.append(get_help_text('magic'))
    return '\n\n---\n\n'.join(parts), topics


def cpdhelp(topic: str = 'all') -> None:
    """
    打印 FramePro 常用 API 速查；topic 指定主题，默认 all。

    Parameters
    ----------
    topic : str
        all | tab | magic | scan | filter | data
    """
    key = (topic or 'all').strip().lower()
    if key not in HELP_TOPICS:
        print(f"cpdhelp: 未知主题 '{topic}'。\n")
        print(get_help_text('all'))
        return
    print(get_help_text(key))
