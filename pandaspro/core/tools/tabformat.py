"""Presentation of a cpdtab2 result: formatted strings, Styler, formatted Excel sheet.

The numbers in the table are never changed here; only how they are shown.
"""

from __future__ import annotations

import pandas as pd

from pandaspro.core.tools.tab2 import MARGIN_NAMES, TAB_META_KEY

COUNT_NUMBER_FORMAT = '#,##0;-#,##0;"-"'
DECIMAL_NUMBER_FORMAT = '#,##0.00;-#,##0.00;"-"'
PCT_NUMBER_FORMAT = '0.0%'


def _parts(label) -> tuple:
    return label if isinstance(label, tuple) else (label,)


def _label_sets(table: pd.DataFrame) -> tuple[set, set]:
    meta = table.attrs.get(TAB_META_KEY) or {}
    totals = set(MARGIN_NAMES) | set(meta.get('total_labels', {}).values())
    return totals, set(meta.get('pct_labels', []))


def _flags(labels, wanted: set) -> list[bool]:
    return [any(part in wanted for part in _parts(label)) for label in labels]


def format_number(value) -> str:
    if pd.isna(value) or value == 0:
        return '-'
    if float(value).is_integer():
        return f'{int(value):,}'
    return f'{value:,.2f}'


def format_pct(value) -> str:
    return '-' if pd.isna(value) else f'{value:.1%}'


def tab_display(table: pd.DataFrame) -> pd.DataFrame:
    """Same shape as the table, cells as formatted strings."""
    _, pct_labels = _label_sets(table)
    pct_rows, pct_cols = _flags(table.index, pct_labels), _flags(table.columns, pct_labels)
    plain = pd.DataFrame(table)
    out = pd.DataFrame(index=plain.index, columns=plain.columns, dtype=object)
    for j, is_pct_col in enumerate(pct_cols):
        out.iloc[:, j] = [
            format_pct(value) if (is_pct_col or is_pct_row) else format_number(value)
            for value, is_pct_row in zip(plain.iloc[:, j], pct_rows)
        ]
    return out


def tab_style(table: pd.DataFrame):
    """Styler over the numbers: formatted, right-aligned, total rows / columns in bold."""
    totals, pct_labels = _label_sets(table)
    plain = pd.DataFrame(table)
    total_rows, total_cols = _flags(plain.index, totals), _flags(plain.columns, totals)
    pct_rows, pct_cols = _flags(plain.index, pct_labels), _flags(plain.columns, pct_labels)

    def bold(_):
        return pd.DataFrame(
            [['font-weight: bold' if (in_row or in_col) else '' for in_col in total_cols] for in_row in total_rows],
            index=plain.index, columns=plain.columns,
        )

    styler = plain.style.format(
        {label: (format_pct if is_pct else format_number) for label, is_pct in zip(plain.columns, pct_cols)}
    )
    share_rows = [label for label, is_pct in zip(plain.index, pct_rows) if is_pct]
    if share_rows:
        styler = styler.format(format_pct, subset=pd.IndexSlice[share_rows, :])
    return styler.set_properties(**{'text-align': 'right'}).apply(bold, axis=None)


def tab_to_excel(table: pd.DataFrame, path, sheet_name: str = 'Sheet1') -> None:
    """Write the table to a new workbook with openpyxl: numbers stay numbers, formats applied."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    totals, pct_labels = _label_sets(table)
    plain = pd.DataFrame(table)
    n_header, n_index = plain.columns.nlevels, plain.index.nlevels
    total_rows, total_cols = _flags(plain.index, totals), _flags(plain.columns, totals)
    pct_rows, pct_cols = _flags(plain.index, pct_labels), _flags(plain.columns, pct_labels)
    bold, center, right = Font(bold=True), Alignment(horizontal='center'), Alignment(horizontal='right')

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name

    # header: one row per column level, runs of the same outer label merged
    column_labels = [_parts(label) for label in plain.columns]
    for level in range(n_header):
        start = 0
        while start < len(column_labels):
            end = start
            while (level < n_header - 1 and end + 1 < len(column_labels)
                   and column_labels[end + 1][:level + 1] == column_labels[start][:level + 1]):
                end += 1
            header = sheet.cell(row=level + 1, column=n_index + start + 1, value=column_labels[start][level])
            header.font, header.alignment = bold, center
            if end > start:
                sheet.merge_cells(start_row=level + 1, start_column=n_index + start + 1,
                                  end_row=level + 1, end_column=n_index + end + 1)
            start = end + 1
    for position, name in enumerate(plain.index.names):
        sheet.cell(row=n_header, column=position + 1, value=name).font = bold

    # body
    for i, row_label in enumerate(plain.index):
        excel_row = n_header + 1 + i
        for position, part in enumerate(_parts(row_label)):
            label_cell = sheet.cell(row=excel_row, column=position + 1, value=part)
            if total_rows[i]:
                label_cell.font = bold
        for j in range(plain.shape[1]):
            value = plain.iat[i, j]
            is_pct = pct_rows[i] or pct_cols[j]
            if pd.isna(value):
                value = None
            elif hasattr(value, 'item'):
                value = value.item()
            data_cell = sheet.cell(row=excel_row, column=n_index + j + 1, value=value)
            if is_pct:
                data_cell.number_format = PCT_NUMBER_FORMAT
            elif value is not None and not float(value).is_integer():
                data_cell.number_format = DECIMAL_NUMBER_FORMAT
            else:
                data_cell.number_format = COUNT_NUMBER_FORMAT
            data_cell.alignment = right
            if total_rows[i] or total_cols[j]:
                data_cell.font = bold

    workbook.save(path)
