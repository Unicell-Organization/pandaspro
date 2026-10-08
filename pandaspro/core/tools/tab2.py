"""两维交叉表（cpdtab2 系列）计数与百分比工具。"""

from __future__ import annotations

import re
from typing import Callable

import pandas as pd

MARGIN_NAMES = frozenset({'Total', 'All'})

# 较长前缀优先匹配
CPDTAB2_PCT_PREFIXES: tuple[tuple[str, str, bool], ...] = (
    ('cpdtab2spctrow_', 'row', True),
    ('cpdtab2spctcol_', 'col', True),
    ('cpdtab2spct_', 'total', True),
    ('cpdtab2pctrow_', 'row', False),
    ('cpdtab2pctcol_', 'col', False),
    ('cpdtab2pct_', 'total', False),
)

CPDTAB2_COUNT_PREFIXES: tuple[tuple[str, bool], ...] = (
    ('cpdtab2s_', True),
    ('cpdtab2_', False),
)

AGG_FUNCS = ('min', 'max', 'mean', 'median', 'sum', 'std', 'var', 'first', 'last')
_AGG_PATTERN = re.compile(r'^cpdtab2(s?)(' + '|'.join(AGG_FUNCS) + r')_')

# sum / std 的合计历史上一直叫 Total（其余聚合叫 All），保持不变以免破坏已有脚本
LEGACY_TOTAL_AGGS = ('sum', 'std')

# first / last 是「每格挑一行」而不是汇总，合计没有意义（pandas 3.0 也算不了），所以不带合计
PICK_AGGS = ('first', 'last')

TAB_KIND_KEY = 'cpdtab'


def detect_cpdtab2_pct(item: str) -> tuple[str, bool, int] | None:
    """返回 (mode, with_subtotals, prefix_len) 或 None。"""
    for prefix, mode, with_subtotals in CPDTAB2_PCT_PREFIXES:
        if item.startswith(prefix):
            return mode, with_subtotals, len(prefix)
    return None


def detect_cpdtab2_count(item: str) -> tuple[bool, int] | None:
    """返回 (with_subtotals, prefix_len) 或 None。"""
    for prefix, with_subtotals in CPDTAB2_COUNT_PREFIXES:
        if item.startswith(prefix):
            return with_subtotals, len(prefix)
    return None


def detect_cpdtab2_agg(item: str) -> tuple[str, bool, int] | None:
    """返回 (aggfunc, with_subtotals, prefix_len) 或 None。

    整段前缀一次匹配：sum / std 以 s 开头，不能先按 cpdtab2s 判小计。
    """
    match = _AGG_PATTERN.match(item)
    if match:
        return match.group(2), bool(match.group(1)), match.end()
    return None


def mark_tab(table: pd.DataFrame, kind: str) -> pd.DataFrame:
    """在结果上记下表的种类（count / pct / agg），供 tabops 的展示选项使用。"""
    table.attrs[TAB_KIND_KEY] = kind
    return table


def _index_is_margin(idx, margins_name: str = 'Total') -> bool:
    names = MARGIN_NAMES | {margins_name}
    if isinstance(idx, tuple):
        return any(part in names for part in idx)
    return idx in names


def _column_is_margin(col, margins_name: str = 'Total') -> bool:
    names = MARGIN_NAMES | {margins_name}
    if isinstance(col, tuple):
        return any(part in names for part in col)
    return col in names


def _match_fields(fields: list[str], columns_list, side: str) -> list[str]:
    """按属性名里的顺序返回匹配到的列；有字段找不到就报错。"""
    matched = [col for col in columns_list if col in fields]
    if len(matched) != len(fields):
        missing = set(fields) - set(matched)
        raise ValueError(f"Some {side} fields not found in dataframe. Missing: {missing}")
    matched.sort(key=lambda x: fields.index(x))
    return matched


def _split_sides(fields_part: str) -> tuple[list[str], list[str]] | None:
    """含 ___ 时拆成 (index 侧字段, columns 侧字段)；不含返回 None。"""
    if '___' not in fields_part:
        return None
    parts = fields_part.split('___')
    if len(parts) != 2:
        raise ValueError(
            f"Invalid cpdtab2 format with ___: expected exactly one ___ separator, "
            f"got {len(parts) - 1}"
        )
    return parts[0].split('__'), parts[1].split('__')


def _missing_separator_error(prefix: str, left: list[str], right: list[str], right_side: str) -> ValueError:
    """字段过多又没写 ___ 时的报错：用文字写明两个 / 三个下划线，并用 ^^^ 指出位置。"""
    head = prefix + '__'.join(left)
    return ValueError(
        f"{len(left) + len(right)} fields were joined with TWO underscores (__) only, "
        f"so the row fields and the column fields cannot be told apart.\n"
        f"Put THREE underscores (___) between the row side and the column side:\n\n"
        f"    {head}___{'__'.join(right)}\n"
        f"    {' ' * len(head)}^^^ THREE underscores here: "
        f"rows on the left, {right_side} on the right\n\n"
        f"Everywhere else keep TWO underscores (__)."
    )


def parse_pivot_fields_from_attr(
    item: str,
    prefix_len: int,
    columns_list,
) -> tuple[list[str], list[str]]:
    """
    解析 cpdtab2 / cpdtab2pct 属性名为 pivot_index、pivot_columns。
    支持 ___ 分隔 index 与 columns 侧。
    """
    fields_part = item[prefix_len:]
    sides = _split_sides(fields_part)
    if sides is not None:
        index_fields, columns_fields = sides
    else:
        all_fields = fields_part.split('__')
        if len(all_fields) < 2:
            raise ValueError(
                f"Attribute var name parsing needs at least 2 columns for pivot, "
                f"fields are {all_fields}"
            )
        if len(all_fields) > 2:
            raise _missing_separator_error(
                item[:prefix_len], all_fields[:-1], all_fields[-1:], 'columns'
            )
        index_fields = [all_fields[0]]
        columns_fields = [all_fields[1]]

    pivot_index = _match_fields(index_fields, columns_list, 'index')
    pivot_columns = _match_fields(columns_fields, columns_list, 'column')
    return pivot_index, pivot_columns


def parse_agg_fields_from_attr(
    item: str,
    prefix_len: int,
    columns_list,
) -> tuple[list[str], list[str], str]:
    """
    解析 cpdtab2{agg} 属性名为 pivot_index、pivot_columns、value 字段。
    最后一个字段总是 value；支持 ___ 分隔 index 与 columns 侧。
    """
    fields_part = item[prefix_len:]
    sides = _split_sides(fields_part)
    if sides is not None:
        index_fields, columns_and_value = sides
        columns_fields, value_field = columns_and_value[:-1], columns_and_value[-1]
    else:
        all_fields = fields_part.split('__')
        if len(all_fields) < 3:
            raise ValueError(
                f"Attribute var name parsing results needs at least 3 columns "
                f"(index, columns, value), fields are {all_fields}"
            )
        if len(all_fields) > 3:
            raise _missing_separator_error(
                item[:prefix_len], all_fields[:-2], all_fields[-2:], 'columns then the value field'
            )
        index_fields, columns_fields, value_field = [all_fields[0]], [all_fields[1]], all_fields[2]

    pivot_index = _match_fields(index_fields, columns_list, 'index')
    pivot_columns = _match_fields(columns_fields, columns_list, 'column')
    if value_field not in columns_list:
        raise ValueError(f"Value field '{value_field}' not found in dataframe")
    return pivot_index, pivot_columns, value_field


def resolve_idvar(frame, pivot_index: list[str], pivot_columns: list[str]) -> str:
    """选择用于 count 的 id 列。"""
    if frame.uid is not None:
        return frame.uid

    used_fields = set(pivot_index) | set(pivot_columns)
    available_cols = [
        col for col in frame.columns[frame.notnull().all()].tolist()
        if col not in used_fields
    ]
    if available_cols:
        return available_cols[0]
    return frame.columns[frame.notnull().all()].tolist()[0]


def apply_export_mapper_fields(frame, pivot_index, pivot_columns, idvar):
    """Export 模式下映射字段名。"""
    if frame.export_mapper is None or frame.rename_status != 'Export':
        return pivot_index, pivot_columns, idvar

    mapper = frame.export_mapper.dict
    pivot_index = [mapper.get(x, x) for x in pivot_index]
    pivot_columns = [mapper.get(x, x) for x in pivot_columns]
    idvar = mapper.get(idvar, idvar)
    return pivot_index, pivot_columns, idvar


def build_count_pivot(
    frame,
    pivot_index: list[str],
    pivot_columns: list[str],
    idvar: str,
    margins_name: str = 'Total',
) -> pd.DataFrame:
    return frame.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values=idvar,
        aggfunc='count',
        margins=True,
        margins_name=margins_name,
    )


def add_subtotals(pivot_df: pd.DataFrame) -> pd.DataFrame:
    """
    为 pivot table 添加 subtotals
    - index 第一级每个分组追加 Subtotal 行
    - columns 第一级每个分组追加 Subtotal 列
    - Total 行/列保持在最下/最右
    """
    result = pivot_df.copy()

    total_row = None
    if isinstance(result.index, pd.MultiIndex):
        for idx in result.index:
            if idx[0] in MARGIN_NAMES:
                total_row = result.loc[[idx]]
                result = result.drop(idx)
                break

    if isinstance(result.index, pd.MultiIndex) and len(result.index.names) > 0:
        index_names = result.index.names
        first_level_values = result.index.get_level_values(0).unique()

        subtotal_rows = []
        for value in first_level_values:
            if value in MARGIN_NAMES:
                continue

            mask = result.index.get_level_values(0) == value
            group_data = result[mask]
            subtotal = group_data.sum(numeric_only=True)

            if len(index_names) == 2:
                subtotal_index = (value, f'{value} Subtotal')
            else:
                subtotal_index = tuple(
                    [value] + [f'{value} Subtotal'] + [''] * (len(index_names) - 2)
                )

            subtotal.name = subtotal_index
            subtotal_rows.append(subtotal)

        if subtotal_rows:
            subtotal_df = pd.DataFrame(subtotal_rows)
            subtotal_df.index.names = index_names
            result = pd.concat([result, subtotal_df])
            result = result.sort_index(level=0, sort_remaining=False)
            result.index.names = index_names

    total_col = None
    total_col_name = None
    if isinstance(result.columns, pd.MultiIndex):
        for col in result.columns:
            if col[0] in MARGIN_NAMES:
                total_col = result[col].copy()
                total_col_name = col
                result = result.drop(columns=[col])
                break

    if isinstance(result.columns, pd.MultiIndex) and len(result.columns.levels) > 0:
        column_names = result.columns.names
        first_level_values = [col[0] for col in result.columns]
        unique_first_levels = []
        seen = set()
        for val in first_level_values:
            if val not in seen:
                unique_first_levels.append(val)
                seen.add(val)

        for value in unique_first_levels:
            if value in MARGIN_NAMES:
                continue

            cols_in_group = [col for col in result.columns if col[0] == value]
            subtotal_col = result[cols_in_group].sum(axis=1, numeric_only=True)

            if len(result.columns.levels) == 2:
                subtotal_col_name = (value, f'{value} Subtotal')
            else:
                subtotal_col_name = tuple(
                    [value] + [f'{value} Subtotal'] + [''] * (len(result.columns.levels) - 2)
                )

            result[subtotal_col_name] = subtotal_col

        if isinstance(result.columns, pd.MultiIndex):
            result = result.sort_index(axis=1, level=0, sort_remaining=False)
            result.columns.names = column_names

    if total_col is not None:
        result[total_col_name] = total_col

    if total_row is not None:
        result = pd.concat([result, total_row])

    return result


def _split_margin_and_data(labels, margins_name: str = 'Total'):
    margin = [x for x in labels if _index_is_margin(x, margins_name)]
    data = [x for x in labels if not _index_is_margin(x, margins_name)]
    return data, margin


def _split_margin_and_data_cols(labels, margins_name: str = 'Total'):
    margin = [x for x in labels if _column_is_margin(x, margins_name)]
    data = [x for x in labels if not _column_is_margin(x, margins_name)]
    return data, margin


def counts_to_pct(
    pivot_df: pd.DataFrame,
    mode: str = 'total',
    margins_name: str = 'Total',
    round_digits: int = 2,
) -> pd.DataFrame:
    """
    将计数交叉表转为百分比（0–100，保留 round_digits 位小数）。

    mode
    ----
    total : 各单元格占全体比例
    row   : 行内比例（每行数据列之和为 100；Total 行展示列占全体比例）
    col   : 列内比例（每列数据行之和为 100；Total 列展示行占全体比例）
    """
    if mode not in {'total', 'row', 'col'}:
        raise ValueError(f"mode must be 'total', 'row', or 'col', got {mode!r}")

    counts = pivot_df.apply(pd.to_numeric, errors='coerce').astype(float).fillna(0.0)
    data_rows, margin_rows = _split_margin_and_data(counts.index, margins_name)
    data_cols, margin_cols = _split_margin_and_data_cols(counts.columns, margins_name)

    margin_row = margin_rows[0] if margin_rows else None
    margin_col = margin_cols[0] if margin_cols else None

    if margin_row is not None and margin_col is not None:
        grand_total = float(counts.loc[margin_row, margin_col])
    else:
        grand_total = float(counts.loc[data_rows, data_cols].values.sum())

    if grand_total == 0:
        return counts * 0.0

    pct = counts.copy()

    if mode == 'total':
        pct.loc[:, :] = counts / grand_total * 100

    elif mode == 'row':
        for row in data_rows:
            row_total = (
                float(counts.loc[row, margin_col])
                if margin_col is not None
                else float(counts.loc[row, data_cols].sum())
            )
            if row_total == 0:
                pct.loc[row, data_cols] = 0.0
            else:
                pct.loc[row, data_cols] = counts.loc[row, data_cols] / row_total * 100
            if margin_col is not None:
                pct.loc[row, margin_col] = 100.0

        if margin_row is not None:
            for col in data_cols:
                pct.loc[margin_row, col] = counts.loc[margin_row, col] / grand_total * 100
            if margin_col is not None:
                pct.loc[margin_row, margin_col] = 100.0

    elif mode == 'col':
        for col in data_cols:
            col_total = (
                float(counts.loc[margin_row, col])
                if margin_row is not None
                else float(counts.loc[data_rows, col].sum())
            )
            if col_total == 0:
                pct.loc[data_rows, col] = 0.0
            else:
                pct.loc[data_rows, col] = counts.loc[data_rows, col] / col_total * 100

        if margin_col is not None:
            for row in data_rows:
                row_total = (
                    float(counts.loc[row, margin_col])
                    if margin_col is not None
                    else float(counts.loc[row, data_cols].sum())
                )
                pct.loc[row, margin_col] = row_total / grand_total * 100

        if margin_row is not None:
            for col in data_cols:
                pct.loc[margin_row, col] = 100.0
            if margin_col is not None:
                pct.loc[margin_row, margin_col] = 100.0

    return pct.round(round_digits)


def cpdtab2_pct_result(
    frame,
    item: str,
    mode: str,
    with_subtotals: bool,
    prefix_len: int,
    frame_ctor: Callable,
) -> pd.DataFrame:
    """构建 cpdtab2pct / cpdtab2spct 系列结果。"""
    pivot_index, pivot_columns = parse_pivot_fields_from_attr(
        item, prefix_len, frame.columns
    )
    idvar = resolve_idvar(frame, pivot_index, pivot_columns)
    pivot_index, pivot_columns, idvar = apply_export_mapper_fields(
        frame, pivot_index, pivot_columns, idvar
    )

    count_table = build_count_pivot(
        frame, pivot_index, pivot_columns, idvar, margins_name='Total'
    )
    if with_subtotals:
        count_table = add_subtotals(count_table)

    pct_table = counts_to_pct(count_table, mode=mode, margins_name='Total')
    return mark_tab(frame_ctor(pct_table), 'pct')


def cpdtab2_count_result(
    frame,
    item: str,
    with_subtotals: bool,
    prefix_len: int,
    frame_ctor: Callable,
) -> pd.DataFrame:
    """构建 cpdtab2_ / cpdtab2s_ 计数交叉表。"""
    pivot_index, pivot_columns = parse_pivot_fields_from_attr(
        item, prefix_len, frame.columns
    )
    idvar = resolve_idvar(frame, pivot_index, pivot_columns)
    pivot_index, pivot_columns, idvar = apply_export_mapper_fields(
        frame, pivot_index, pivot_columns, idvar
    )

    count_table = build_count_pivot(
        frame, pivot_index, pivot_columns, idvar, margins_name='Total'
    )
    if with_subtotals:
        count_table = add_subtotals(count_table)
    return mark_tab(frame_ctor(count_table), 'count')


def cpdtab2_agg_result(frame, item: str, frame_ctor: Callable) -> pd.DataFrame:
    """构建 cpdtab2{agg}_ / cpdtab2s{agg}_ 聚合交叉表。"""
    agg_info = detect_cpdtab2_agg(item)
    if agg_info is None:
        raise ValueError(
            f"Error: The input string '{item}' is not in the correct format. "
            f"If you want to summarize by count, use only cpdtab2 followed by variable names. "
            f"If you want to use the aggregate shortcut of cpdtab2, "
            f"it should start with 'cpdtab2' followed by a valid aggregation function "
            f"(min, max, mean, median, sum, first, last, std, var)."
        )
    aggfunc, with_subtotals, prefix_len = agg_info

    pivot_index, pivot_columns, value_field = parse_agg_fields_from_attr(
        item, prefix_len, frame.columns
    )
    pivot_index, pivot_columns, value_field = apply_export_mapper_fields(
        frame, pivot_index, pivot_columns, value_field
    )

    agg_table = frame.pivot_table(
        index=pivot_index,
        columns=pivot_columns,
        values=value_field,
        aggfunc=aggfunc,
        margins=aggfunc not in PICK_AGGS,
        margins_name='Total' if with_subtotals or aggfunc in LEGACY_TOTAL_AGGS else 'All',
    )
    if with_subtotals:
        agg_table = add_subtotals(agg_table)
    return mark_tab(frame_ctor(agg_table), 'agg')

