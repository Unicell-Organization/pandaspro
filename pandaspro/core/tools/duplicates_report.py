import pandas as pd


def duplicates_report(data, column_list, d: str = 'brief', dropna: bool = False) -> pd.DataFrame:
    """
    仿 Stata `duplicates report`：按指定字段分组，统计「每个取值出现几份」的分布。

    输出列（d='brief'）
    ------------------
    copies        该取值出现的份数（1 = 唯一，2 = 出现两次 ...）
    observations  属于这一档的总行数（copies × 取值个数）
    surplus       这一档里多出来的行数（observations − 取值个数），即删重时会被删掉的行

    输出列（d='detail'）
    -------------------
    依据字段 + copies：只列出重复出现的取值，按 copies 降序

    Parameters
    ----------
    data : DataFrame
        待检测的数据表。
    column_list : str | list
        判断重复所依据的字段，例如 'upi' 或 ['upi', 'year']。
    d : str, optional
        'brief'（默认）：重复份数分布；'detail'：逐个列出重复的取值及其份数。
    dropna : bool, optional
        默认 False：缺失值视为同一个取值参与统计（与 Stata / drop_duplicates 一致）；
        True：任一依据字段缺失的行不参与统计。

    Returns
    -------
    DataFrame
        见上方输出列；空表或无重复时返回空结果。
    """
    if d not in ('brief', 'detail'):
        raise ValueError(f"d 只接受 'brief' 或 'detail'，收到 {d!r}")

    if isinstance(column_list, str):
        column_list = [column_list]
    else:
        column_list = list(column_list)

    group_sizes = data.groupby(column_list, dropna=dropna, sort=False).size()
    groups_by_copies = group_sizes.value_counts().sort_index()

    copies = [int(c) for c in groups_by_copies.index]
    n_groups = [int(g) for g in groups_by_copies.values]
    result = pd.DataFrame({
        'copies': copies,
        'observations': [c * g for c, g in zip(copies, n_groups)],
        'surplus': [(c - 1) * g for c, g in zip(copies, n_groups)],
    }).astype('int64')

    n_obs = int(result['observations'].sum())
    n_unique = sum(n_groups)
    n_dup_values = sum(g for c, g in zip(copies, n_groups) if c > 1)
    n_surplus = int(result['surplus'].sum())
    n_missing = int(data[column_list].isna().any(axis=1).sum())

    label = ', '.join(str(c) for c in column_list)
    summary = (
        f'duplicates_report({label})：共 {n_obs:,} 行，{n_unique:,} 个不同取值，'
        f'其中 {n_dup_values:,} 个取值重复出现，多出 {n_surplus:,} 行'
    )
    if n_missing:
        summary += (
            f'（已排除 {n_missing:,} 行缺失）' if dropna
            else f'（含 {n_missing:,} 行缺失，按同一取值计入）'
        )
    print(summary)

    dup_sizes = group_sizes[group_sizes > 1].sort_values(ascending=False, kind='stable')
    if n_dup_values:
        _print_hints(column_list, d, dup_sizes, show_dropna=bool(n_missing) and not dropna)

    if d == 'detail':
        return dup_sizes.rename('copies').reset_index().astype({'copies': 'int64'})

    return result


def _print_hints(column_list, d, dup_sizes, show_dropna):
    """打印接下来可用的相关调用，列名与取值直接代入，复制即可用。"""
    col_arg = repr(column_list[0]) if len(column_list) == 1 else repr(column_list)
    d_arg = ", d='detail'" if d == 'detail' else ''
    hints = []

    if d == 'brief':
        hints.append((f"df.duplicates_report({col_arg}, d='detail')", '看哪些取值重复、各重复几份'))
    else:
        # inlist 只支持单字段；缺失值不放进示例
        if len(column_list) == 1:
            values = [v.item() if hasattr(v, 'item') else v for v in dup_sizes.index if not pd.isna(v)]
            examples = values[:3]
            if examples:
                desc = '看这些取值的完整行' if len(values) <= 3 else f'看前 {len(examples)} 个重复取值的完整行'
                hints.append((f"df.inlist({col_arg}, {', '.join(repr(v) for v in examples)})", desc))
        hints.append((f'df.duplicates_report({col_arg})', '看重复份数分布'))

    hints.append((f'df.show_duplicates({col_arg})', '取出多余的重复行（每组第一行之外）'))
    if show_dropna:
        hints.append((f'df.duplicates_report({col_arg}{d_arg}, dropna=True)', '缺失值不参与统计'))

    width = max(len(code) for code, _ in hints)
    print('提示：')
    for code, desc in hints:
        print(f'  {code.ljust(width)}  {desc}')
