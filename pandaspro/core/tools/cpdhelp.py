HELP_TOPIC_KEYWORDS = {
    'tab': (
        'tab', 'cpdtab', '交叉', '频数', 'pivot', 'cpdtab2', 'cpdtabd', 'cpdtabt',
        'cpdtab2s', 'cpdtab2pct', 'cpdtab2spct', 'percent', '百分比', 'pct',
        'sum', 'mean', '小计', 'subtotal', '___', '多维',
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

【多维 index / columns — 用 ___ 分隔两侧】
  格式: cpdtab2_行1__行2___列1__列2
  例: df.cpdtab2_region__dept___quarter__category
  带聚合: df.cpdtab2sum_region___quarter__salary
         （___ 前为 index 字段，后为 columns + 最后的 value 字段）

分隔符速记
  __   同一侧多个字段
  ___  index 侧 与 columns 侧 的分界

除 cpdtab2 外，多维表也可用 cpdtab2s（要小计）、cpdtab2pct*（要百分比）或 cpdtab2sum 等（要聚合）。
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
