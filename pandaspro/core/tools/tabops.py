"""交叉表结果的展示选项：nototal / tdiff / tratio / tsort，接在 cpdtab2 系列结果后面。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pandaspro.core.tools.tab2 import MARGIN_NAMES, TAB_KIND_KEY, TAB_META_KEY

# 较长前缀优先匹配
TAB_OP_PREFIXES: tuple[str, ...] = ('nototal', 'tdiff', 'tratio', 'tsortd', 'tsort')

NOTOTAL_SIDES = {'': 'col', 'row': 'row', 'all': 'all'}
SUBTOTAL_SUFFIX = ' Subtotal'
DIFF_NAME = 'Diff'
RATIO_NAME = 'Ratio'


def detect_tab_op(item: str) -> tuple[str, str | None] | None:
    """返回 (op, arg) 或 None；arg 是下划线后面的部分，nototal 的 arg 是 col / row / all。"""
    for prefix in TAB_OP_PREFIXES:
        if not item.startswith(prefix):
            continue
        rest = item[len(prefix):]
        if prefix == 'nototal':
            if rest in NOTOTAL_SIDES:
                return prefix, NOTOTAL_SIDES[rest]
        elif rest == '':
            return prefix, None
        elif rest.startswith('_') and len(rest) > 1:
            return prefix, rest[1:]
        return None
    return None


def _parts(label) -> tuple:
    return label if isinstance(label, tuple) else (label,)


def _label_sets(table: pd.DataFrame) -> tuple[set, set]:
    """(合计标签, 派生列标签)：除默认的 Total / All、Diff / Ratio 外，还包括规则里起的名字和占比列。"""
    meta = table.attrs.get(TAB_META_KEY) or {}
    totals = set(MARGIN_NAMES) | set(meta.get('total_labels', {}).values())
    derived = {DIFF_NAME, RATIO_NAME} | set(meta.get('pct_labels', []))
    return totals, derived


def _has(label, wanted: set) -> bool:
    return any(part in wanted for part in _parts(label))


def _is_subtotal(label) -> bool:
    return any(isinstance(part, str) and part.endswith(SUBTOTAL_SUFFIX) for part in _parts(label))


def _data_columns(table: pd.DataFrame) -> list:
    totals, derived = _label_sets(table)
    return [
        col for col in table.columns
        if not (_has(col, totals) or _is_subtotal(col) or _has(col, derived))
    ]


def _normalize(table: pd.DataFrame) -> pd.DataFrame:
    """计数表：空格子当 0，整数列显示成整数；其他表原样返回（副本）。"""
    out = table.copy()
    out.attrs = dict(table.attrs)
    if table.attrs.get(TAB_KIND_KEY) != 'count':
        return out
    derived = _label_sets(table)[1]
    for col in out.columns:
        if _has(col, derived):
            continue
        values = out[col].fillna(0)
        if pd.api.types.is_float_dtype(values) and (values % 1 == 0).all():
            values = values.astype('int64')
        out[col] = values
    return out


def _resolve_column(token: str, candidates: list, op: str):
    """先按列名找，找不到且 token 是数字时按位置（从 1 起）找。"""
    for col in candidates:
        if not isinstance(col, tuple) and str(col) == token:
            return col
    if token.isdigit() and 1 <= int(token) <= len(candidates):
        return candidates[int(token) - 1]
    raise ValueError(
        f"{op}: column '{token}' not found. Available columns: {candidates}. "
        f"A column can also be given by position, starting from 1."
    )


def _derived_label(table: pd.DataFrame, name: str):
    nlevels = table.columns.nlevels
    return name if nlevels == 1 else (name,) + ('',) * (nlevels - 1)


def tab_nototal(table: pd.DataFrame, side: str = 'col') -> pd.DataFrame:
    """去掉合计：side = col（右侧 Total 列）/ row（底部 Total 行）/ all。"""
    out = _normalize(table)
    totals = _label_sets(table)[0]
    if side in ('col', 'all'):
        out = out.loc[:, [not _has(col, totals) for col in out.columns]]
    if side in ('row', 'all'):
        out = out.loc[[not _has(idx, totals) for idx in out.index]]
    out.attrs = dict(table.attrs)
    return out


def tab_compare(table: pd.DataFrame, arg: str | None, ratio: bool = False) -> pd.DataFrame:
    """
    新增 Diff（两列相减）或 Ratio（两列相除）列。

    arg 为 None 时要求恰好两个数据列，取「后减前 / 后除以前」；
    arg 为 'A__C' 时取 A − C / A ÷ C。合计列、小计列不参与。
    """
    op = 'tratio' if ratio else 'tdiff'
    out = _normalize(table)
    data_cols = _data_columns(out)

    if arg is None:
        if len(data_cols) != 2:
            raise ValueError(
                f"{op} needs exactly two data columns to pick a default, found "
                f"{len(data_cols)}: {data_cols}. Name the two columns, "
                f"e.g. .{op}_1__2 (first column {'÷' if ratio else '−'} second column)."
            )
        left, right = data_cols[1], data_cols[0]
    else:
        tokens = arg.split('__')
        if len(tokens) != 2:
            raise ValueError(
                f"{op} takes exactly two columns separated by __, got {tokens}"
            )
        left = _resolve_column(tokens[0], data_cols, op)
        right = _resolve_column(tokens[1], data_cols, op)

    if ratio:
        values = (out[left] / out[right]).replace([np.inf, -np.inf], np.nan).round(2)
        label = _derived_label(out, RATIO_NAME)
    else:
        values = out[left] - out[right]
        if table.attrs.get(TAB_KIND_KEY) == 'pct':
            values = values.round(2)
        label = _derived_label(out, DIFF_NAME)

    out[label] = values
    out.attrs = dict(table.attrs)
    return out


def tab_sort(table: pd.DataFrame, arg: str | None, desc: bool = False) -> pd.DataFrame:
    """
    按某一列给行排序，合计行钉在底部。

    arg 为列名或位置（从 1 起），None 表示第一列。多层行索引时在第一层的每个
    分组内部排序，分组顺序不变，小计行钉在分组底部。
    """
    op = 'tsortd' if desc else 'tsort'
    out = _normalize(table)
    columns = list(out.columns)
    key = columns[0] if arg is None else _resolve_column(arg, columns, op)
    values = pd.Series(out[key].to_numpy(), index=range(len(out)))

    def sorted_block(positions: list[int]) -> list[int]:
        return values.iloc[positions].sort_values(
            ascending=not desc, kind='stable', na_position='last'
        ).index.tolist()

    totals = _label_sets(table)[0]
    margin_rows, groups = [], {}
    for pos, idx in enumerate(out.index):
        if _has(idx, totals):
            margin_rows.append(pos)
            continue
        group = idx[0] if isinstance(out.index, pd.MultiIndex) else None
        body, pinned = groups.setdefault(group, ([], []))
        (pinned if _is_subtotal(idx) else body).append(pos)

    order = []
    for body, pinned in groups.values():
        order += sorted_block(body) + pinned
    out = out.iloc[order + margin_rows]
    out.attrs = dict(table.attrs)
    return out


def apply_tab_op(table: pd.DataFrame, op: str, arg: str | None) -> pd.DataFrame:
    if op == 'nototal':
        return tab_nototal(table, arg)
    if op == 'tdiff':
        return tab_compare(table, arg)
    if op == 'tratio':
        return tab_compare(table, arg, ratio=True)
    return tab_sort(table, arg, desc=(op == 'tsortd'))


def rename_agg(table: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Rename the aggregate ("all values together") of one or more fields; numbers are untouched."""
    meta = table.attrs.get(TAB_META_KEY)
    if not meta:
        raise ValueError("rename_agg works on a cpdtab2 result, e.g. df.cpdtab2_a___b__c.rename_agg(b='All')")
    out = table.copy()
    labels = dict(meta['total_labels'])

    def renamed(axis_index, level: int, old, new):
        if isinstance(axis_index, pd.MultiIndex):
            tuples = [tuple(new if (i == level and part == old) else part for i, part in enumerate(label))
                      for label in axis_index]
            return pd.MultiIndex.from_tuples(tuples, names=axis_index.names)
        return pd.Index([new if label == old else label for label in axis_index], name=axis_index.name)

    for field, new in mapping.items():
        if field in meta['index']:
            axis_index, level = out.index, meta['index'].index(field)
        elif field in meta['columns']:
            axis_index, level = out.columns, meta['columns'].index(field)
        else:
            raise ValueError(
                f"rename_agg: field '{field}' is not in this table. "
                f"Row fields: {meta['index']}, column fields: {meta['columns']}"
            )
        old = labels.get(field, 'Total')
        present = axis_index.get_level_values(level) if isinstance(axis_index, pd.MultiIndex) else axis_index
        if old not in present:
            raise ValueError(f"rename_agg: this table shows no aggregate '{old}' for field '{field}'")
        if field in meta['index']:
            out.index = renamed(axis_index, level, old, new)
        else:
            out.columns = renamed(axis_index, level, old, new)
        labels[field] = new

    out.attrs = {**table.attrs, TAB_META_KEY: {**meta, 'total_labels': labels}}
    return out
