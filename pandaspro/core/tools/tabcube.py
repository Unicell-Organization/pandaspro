"""Rule-aware cross-tab engine behind FramePro.cpdtab2().

Every margin is recomputed from the data (one groupby per combination of
totalled fields), never by adding up displayed cells, so totals are also right
for mean / median. Shares are always ratios of row counts.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import pandas as pd

from pandaspro.core.tools import tabrules

DEFAULT_TOTAL_LABEL = 'Total'
DEFAULT_TOTAL_POSITION = {'rows': 'last', 'cols': 'last'}
FILLABLE_AGGS = ('count', 'size', 'sum')


class _Total:
    """Key standing for "all values of this field" inside cube keys."""

    def __repr__(self):
        return '<total>'


_TOTAL = _Total()


@dataclass(frozen=True)
class _ShareKey:
    """Key standing for a share column / row of one field."""
    field: str
    value: object
    label: str


def _as_list(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _resolve_shares(shares, fields: list[str], rules: dict) -> tuple[dict[str, list[_ShareKey]], dict[str, bool]]:
    if shares is None:
        entries = []
        for field in fields:
            declared = rules[field].get('share')
            for entry in ([declared] if isinstance(declared, dict) else declared or []):
                entries.append({**entry, 'field': field})
    else:
        entries = [shares] if isinstance(shares, dict) else list(shares)

    resolved: dict[str, list[_ShareKey]] = {}
    keep_total: dict[str, bool] = {}
    for entry in entries:
        field = entry.get('field')
        if field not in fields:
            raise ValueError(f"shares: field '{field}' is not in the table. Fields: {fields}")
        if 'value' not in entry:
            raise ValueError("shares: each entry needs a 'value', e.g. "
                             "{'field': 'open_term', 'value': 'Open', 'label': '% Open'}")
        label = entry.get('label') or f"% {entry['value']}"
        resolved.setdefault(field, []).append(_ShareKey(field, entry['value'], label))
        keep_total[field] = keep_total.get(field, False) or bool(entry.get('keep_total'))
    return resolved, keep_total


def _resolve_pct_of_total(pct_of_total, index: list[str], columns: list[str], rules: dict) -> list[tuple[str, str]]:
    if pct_of_total is None:
        entries = []
        for field in index + columns:
            declared = rules[field].get('pct_of_total')
            if declared:
                entry = {'label': declared} if isinstance(declared, str) else dict(declared)
                entries.append({**entry, 'field': field})
    else:
        entries = [pct_of_total] if isinstance(pct_of_total, dict) else list(pct_of_total)

    resolved = []
    for entry in entries:
        field = entry.get('field')
        if field not in index + columns:
            raise ValueError(f"pct_of_total: field '{field}' is not in the table. Fields: {index + columns}")
        actual_axis = 'rows' if field in index else 'cols'
        if entry.get('axis') not in (None, actual_axis):
            raise ValueError(f"pct_of_total: field '{field}' is on the {actual_axis} axis, "
                             f"but axis={entry['axis']!r} was given")
        resolved.append((field, entry.get('label') or '% of Total'))
    return resolved


def _ordered_values(present: list, order: list | None, blank) -> list:
    """Listed values first (always shown), then other values sorted, then the blank label."""
    listed = list(order or [])
    others = [value for value in present if value not in listed and value != blank]
    try:
        others = sorted(others)
    except TypeError:
        others = sorted(others, key=str)
    tail = [blank] if blank in present and blank not in listed else []
    return listed + others + tail


def _cube(work: pd.DataFrame, fields: list[str], values: str | None, aggfunc) -> dict:
    """{key tuple: aggregate} for every combination of totalled / kept fields."""
    out = {}
    for mask in itertools.product((False, True), repeat=len(fields)):
        keep = [field for field, totalled in zip(fields, mask) if not totalled]
        if not keep:
            out[(_TOTAL,) * len(fields)] = len(work) if values is None else work[values].agg(aggfunc)
            continue
        grouped = work.groupby(keep, sort=False, dropna=False)
        series = grouped.size() if values is None else grouped[values].agg(aggfunc)
        for key, value in series.items():
            parts = iter(key if isinstance(key, tuple) else (key,))
            out[tuple(_TOTAL if totalled else next(parts) for totalled in mask)] = value
    return out


def _replace(key: tuple, position: int, new) -> tuple:
    return key[:position] + (new,) + key[position + 1:]


def build_tab(
    data: pd.DataFrame,
    index,
    columns=None,
    values: str | None = None,
    aggfunc='count',
    totals: str | None = None,
    total_position=None,
    total_labels: dict | None = None,
    order: dict | None = None,
    shares=None,
    pct_of_total=None,
    nested_totals: bool | None = None,
    fill_value=0,
    dropna_label: str = '(blank)',
    labels: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Build the cross-tab. Returns (table, meta); see FramePro.cpdtab2 for the arguments."""
    index, columns = _as_list(index), _as_list(columns)
    fields = index + columns
    if not index:
        raise ValueError("cpdtab2 needs at least one index field")
    if len(set(fields)) != len(fields):
        raise ValueError(f"cpdtab2: a field can be used only once, got index={index}, columns={columns}")
    missing = [name for name in fields + _as_list(values) if name not in data.columns]
    if missing:
        raise ValueError(f"cpdtab2: fields not found in dataframe: {missing}")
    if values is None and aggfunc not in ('count', 'size'):
        raise ValueError(f"cpdtab2: aggfunc={aggfunc!r} needs a values column")

    # ---- options: explicit argument > registered default > built-in default
    rules = {field: tabrules.field_rules(field) for field in fields}
    defaults = tabrules.tab_defaults()
    totals = totals if totals is not None else defaults.get('totals', 'both')
    if totals not in tabrules.TOTALS_CHOICES:
        raise ValueError(f"totals must be one of {tabrules.TOTALS_CHOICES}, got {totals!r}")
    nested_totals = nested_totals if nested_totals is not None else defaults.get('nested_totals', True)
    position = {**DEFAULT_TOTAL_POSITION, **defaults.get('total_position', {}),
                **tabrules.normalize_total_position(total_position)}
    for option, given in (('total_labels', total_labels), ('order', order), ('labels', labels)):
        unknown = [field for field in (given or {}) if field not in fields]
        if unknown:
            raise ValueError(f"{option}: fields {unknown} are not in the table. Fields: {fields}")
    total_label = {field: (total_labels or {}).get(field) or rules[field].get('total_label') or DEFAULT_TOTAL_LABEL
                   for field in fields}
    field_label = {field: (labels or {}).get(field) or rules[field].get('label') or field for field in fields}
    field_order = {field: (order or {}).get(field) or rules[field].get('order') for field in fields}
    share_keys, keep_total = _resolve_shares(shares, fields, rules)
    pct_measures = _resolve_pct_of_total(pct_of_total, index, columns, rules)

    # ---- data: blanks become a visible label so nobody silently drops out of the counts
    work = pd.DataFrame(data)[fields + _as_list(values)].copy()
    for field in fields:
        column = work[field].astype(object)
        work[field] = column.where(column.notna(), dropna_label)

    counts = _cube(work, fields, None, None)
    cells = counts if values is None else _cube(work, fields, values, aggfunc)
    missing_value = fill_value if aggfunc in FILLABLE_AGGS and fill_value is not None else math.nan

    # ---- keys shown on each axis
    def level_keys(field: str, axis: str) -> list:
        axis_on = totals in ('both', 'rows' if axis == 'rows' else 'cols')
        # a share takes the place of the field's own total unless keep_total is set
        show_total = axis_on and (field not in share_keys or keep_total.get(field))
        keys = _ordered_values(list(pd.unique(work[field])), field_order[field], dropna_label)
        if show_total:
            keys = [_TOTAL] + keys if position[axis] == 'first' else keys + [_TOTAL]
        return keys + share_keys.get(field, []), show_total

    def axis_keys(axis_fields: list[str], axis: str) -> list[tuple]:
        per_field = [level_keys(field, axis) for field in axis_fields]
        with_total = sum(1 for _, show_total in per_field if show_total)
        out = []
        for key in itertools.product(*[keys for keys, _ in per_field]):
            if sum(isinstance(part, _ShareKey) for part in key) > 1:
                continue
            totalled = sum(part is _TOTAL for part in key)
            if not nested_totals and totalled not in (0, with_total):
                continue
            out.append(key)
        return out

    row_keys = axis_keys(index, 'rows')
    col_keys = axis_keys(columns, 'cols')

    def cell(key: tuple):
        share_at = [i for i, part in enumerate(key) if isinstance(part, _ShareKey)]
        if len(share_at) > 1:
            return math.nan
        if share_at:
            at = share_at[0]
            denominator = counts.get(_replace(key, at, _TOTAL), 0)
            return counts.get(_replace(key, at, key[at].value), 0) / denominator if denominator else math.nan
        return cells.get(key, missing_value)

    def pct_cell(key: tuple, field: str):
        if any(isinstance(part, _ShareKey) for part in key):
            return math.nan
        denominator = counts.get(_replace(key, fields.index(field), _TOTAL), 0)
        return counts.get(key, 0) / denominator if denominator else math.nan

    def label_of(part, field: str):
        if part is _TOTAL:
            return total_label[field]
        return part.label if isinstance(part, _ShareKey) else part

    # ---- assemble
    value_label = 'Count' if aggfunc in ('count', 'size') else str(aggfunc)
    column_labels, column_data = [], []
    for col_key in col_keys:
        base = tuple(label_of(part, field) for part, field in zip(col_key, columns))
        is_share = any(isinstance(part, _ShareKey) for part in col_key)
        main = [cell(row_key + col_key) for row_key in row_keys]
        if not pct_measures:
            column_labels.append(base)
            column_data.append(main)
            continue
        column_labels.append(base + ('' if is_share else value_label,))
        column_data.append(main)
        if is_share:
            continue
        for field, pct_label in pct_measures:
            column_labels.append(base + (pct_label,))
            column_data.append([pct_cell(row_key + col_key, field) for row_key in row_keys])

    column_names = [field_label[field] for field in columns] + ([None] if pct_measures else [])
    if not column_names:
        column_index = pd.Index([value_label])
    elif len(column_names) == 1:
        column_index = pd.Index([labels_[0] for labels_ in column_labels], name=column_names[0])
    else:
        column_index = pd.MultiIndex.from_tuples(column_labels, names=column_names)

    row_labels = [tuple(label_of(part, field) for part, field in zip(row_key, index)) for row_key in row_keys]
    if len(index) == 1:
        row_index = pd.Index([labels_[0] for labels_ in row_labels], name=field_label[index[0]])
    else:
        row_index = pd.MultiIndex.from_tuples(row_labels, names=[field_label[field] for field in index])

    table = pd.DataFrame(dict(enumerate(column_data)), index=row_index)
    table.columns = column_index

    meta = {
        'index': index,
        'columns': columns,
        'total_labels': total_label,
        'pct_labels': sorted({key.label for keys in share_keys.values() for key in keys}
                             | {pct_label for _, pct_label in pct_measures}),
        'aggfunc': str(aggfunc),
    }
    return table, meta
