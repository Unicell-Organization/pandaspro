import pandas as pd
import pytest

from pandaspro.core.frame import FramePro
from pandaspro.core.tools.tab2 import detect_cpdtab2_agg
from pandaspro.core.tools.tabops import detect_tab_op


def _sample():
    return FramePro({
        'id': range(1, 13),
        'region': ['East'] * 5 + ['West'] * 4 + ['North'] * 3,
        'grade': ['A', 'A', 'B', 'B', 'C', 'A', 'B', 'B', 'C', 'A', 'C', 'C'],
        'dept': ['HR', 'IT', 'HR', 'IT', 'IT', 'HR', 'HR', 'IT', 'IT', 'HR', 'IT', 'HR'],
        'year': [2024, 2025] * 6,
        'salary': [10, 12, 9, 11, 8, 13, 9, 10, 7, 12, 8, 6],
    })


def test_detect_tab_op():
    assert detect_tab_op('nototal') == ('nototal', 'col')
    assert detect_tab_op('nototalrow') == ('nototal', 'row')
    assert detect_tab_op('nototalall') == ('nototal', 'all')
    assert detect_tab_op('tdiff') == ('tdiff', None)
    assert detect_tab_op('tdiff_A__C') == ('tdiff', 'A__C')
    assert detect_tab_op('tsortd_Diff') == ('tsortd', 'Diff')
    assert detect_tab_op('tsort_1') == ('tsort', '1')
    # 不是选项的名字要放行给 pandas，不能误吞
    for name in ['nototals', 'tdiffs', 'tsortdiff', 'tsort_', 'tratiox']:
        assert detect_tab_op(name) is None


def test_nototal_sides():
    tab = _sample().cpdtab2_region__grade
    assert list(tab.nototal.columns) == ['A', 'B', 'C']
    assert 'Total' in tab.nototal.index
    assert 'Total' not in tab.nototalrow.index
    assert 'Total' in tab.nototalrow.columns
    both = tab.nototalall
    assert 'Total' not in both.index and 'Total' not in both.columns
    assert isinstance(both, FramePro)


def test_count_table_empty_cells_become_zero_integers():
    tab = _sample().cpdtab2_region__grade
    assert pd.isna(tab.loc['North', 'B'])      # 原表不变
    out = tab.nototal
    assert out.loc['North', 'B'] == 0
    assert all(str(dtype) == 'int64' for dtype in out.dtypes)
    assert pd.isna(tab.loc['North', 'B'])      # 选项不改原表


def test_tdiff_named_columns_and_direction():
    tab = _sample().cpdtab2_region__grade
    assert tab.tdiff_A__C['Diff'].tolist() == [1, -1, 0, 0]
    assert tab.tdiff_C__A['Diff'].tolist() == [-1, 1, 0, 0]
    assert tab.tdiff_1__3['Diff'].tolist() == [1, -1, 0, 0]


def test_tdiff_default_is_last_minus_first():
    tab = _sample().cpdtab2_region__dept          # 列: HR, IT
    assert tab.tdiff['Diff'].tolist() == [1, -1, 0, 0]


def test_tdiff_default_needs_exactly_two_columns():
    with pytest.raises(ValueError, match='exactly two data columns'):
        _sample().cpdtab2_region__grade.tdiff


def test_tdiff_ignores_total_column():
    tab = _sample().cpdtab2_region__dept
    assert tab.tdiff['Diff'].tolist() == tab.nototal.tdiff['Diff'].tolist()


def test_tdiff_numeric_labels_win_over_position():
    tab = _sample().cpdtab2_region__year          # 列: 2024, 2025
    assert tab.tdiff_2025__2024['Diff'].tolist() == [-1, 1, 0, 0]


def test_tdiff_unknown_column():
    with pytest.raises(ValueError, match="column 'Z' not found"):
        _sample().cpdtab2_region__grade.tdiff_A__Z


def test_tratio():
    tab = _sample().cpdtab2_region__dept
    assert tab.tratio['Ratio'].tolist() == [1.5, 0.5, 1.0, 1.0]
    # 除以 0 给 NaN，再排序也不会被当成 0
    ratio = _sample().cpdtab2_region__grade.tratio_A__B
    assert pd.isna(ratio.loc['North', 'Ratio'])
    assert pd.isna(ratio.tsort_Ratio.loc['North', 'Ratio'])


def test_tsort_keeps_total_last():
    tab = _sample().cpdtab2_region__grade.tdiff_A__C
    assert tab.tsort_Diff.index.tolist() == ['North', 'West', 'East', 'Total']
    assert tab.tsortd_Diff.index.tolist() == ['East', 'West', 'North', 'Total']


def test_tsort_by_position_and_default():
    tab = _sample().cpdtab2_region__year
    assert tab.tsort_1.index.tolist() == ['North', 'West', 'East', 'Total']
    assert tab.tsort.index.tolist() == tab.tsort_1.index.tolist()


def test_tsort_multiindex_sorts_inside_groups():
    out = _sample().cpdtab2s_region__dept___grade.tsort_A
    assert out.index.tolist() == [
        ('East', 'HR'), ('East', 'IT'), ('East', 'East Subtotal'),
        ('North', 'IT'), ('North', 'HR'), ('North', 'North Subtotal'),
        ('West', 'IT'), ('West', 'HR'), ('West', 'West Subtotal'),
        ('Total', ''),
    ]


def test_ops_on_pct_table():
    out = _sample().cpdtab2pctrow_region__grade.nototal.tdiff_A__C
    assert list(out.columns) == ['A', 'B', 'C', 'Diff']
    assert out.loc['East', 'Diff'] == 20.0


def test_ops_chain_in_any_order():
    tab = _sample().cpdtab2_region__grade
    one = tab.nototal.tdiff_A__C.tsortd_Diff
    two = tab.tdiff_A__C.tsortd_Diff.nototal
    assert one.index.tolist() == two.index.tolist()
    assert one['Diff'].tolist() == two['Diff'].tolist()


# ---- cpdtab2 解析修复（docs/BUGLOG.md BUG-001 / BUG-002）

def test_detect_cpdtab2_agg_s_prefixed_functions():
    assert detect_cpdtab2_agg('cpdtab2sum_a__b__c') == ('sum', False, len('cpdtab2sum_'))
    assert detect_cpdtab2_agg('cpdtab2std_a__b__c') == ('std', False, len('cpdtab2std_'))
    assert detect_cpdtab2_agg('cpdtab2ssum_a__b__c') == ('sum', True, len('cpdtab2ssum_'))
    assert detect_cpdtab2_agg('cpdtab2sstd_a__b__c') == ('std', True, len('cpdtab2sstd_'))
    assert detect_cpdtab2_agg('cpdtab2mean_a__b__c') == ('mean', False, len('cpdtab2mean_'))
    assert detect_cpdtab2_agg('cpdtab2s_a__b') is None


# first / last 不带合计，单独在 test_first_last_spread_long_to_wide 里测
@pytest.mark.parametrize('agg', ['sum', 'std', 'mean', 'min', 'max', 'median', 'var'])
def test_agg_with_triple_underscore_matches_plain_form(agg):
    df = _sample()
    plain = getattr(df, f'cpdtab2{agg}_region__grade__salary')
    split = getattr(df, f'cpdtab2{agg}_region___grade__salary')
    pd.testing.assert_frame_equal(pd.DataFrame(plain), pd.DataFrame(split))


def test_agg_sum_values():
    out = _sample().cpdtab2sum_region__grade__salary
    assert out.loc['East', 'A'] == 22
    assert out.loc['Total', 'Total'] == 115


def test_agg_subtotal_with_s_prefixed_function():
    out = _sample().cpdtab2ssum_region__dept___grade__salary
    assert out.loc[('East', 'East Subtotal'), 'A'] == 22


@pytest.mark.parametrize('name, hint', [
    ('cpdtab2_region__dept__grade', 'cpdtab2_region__dept___grade'),
    ('cpdtab2s_region__dept__grade', 'cpdtab2s_region__dept___grade'),
    ('cpdtab2pct_region__dept__grade', 'cpdtab2pct_region__dept___grade'),
    ('cpdtab2sum_region__dept__grade__salary', 'cpdtab2sum_region__dept___grade__salary'),
])
def test_extra_fields_without_separator_raise_instead_of_being_dropped(name, hint):
    with pytest.raises(ValueError) as err:
        getattr(_sample(), name)
    message = str(err.value)
    assert 'TWO underscores (__)' in message and 'THREE underscores (___)' in message
    # ^^^ 必须正好指在示例写法的 ___ 下面
    lines = message.split('\n')
    example = next(line for line in lines if line.strip() == hint)
    pointer = lines[lines.index(example) + 1]
    assert pointer.index('^^^') == example.index('___')


def test_count_tab_unchanged():
    out = _sample().cpdtab2_region__grade
    assert out.loc['East', 'A'] == 2
    assert out.loc['Total', 'Total'] == 12
    assert list(out.columns) == ['A', 'B', 'C', 'Total']


def test_first_last_spread_long_to_wide():
    df = FramePro({
        'upi': [1, 1, 1, 1, 2, 2, 2],
        'year': [2024, 2024, 2024, 2025, 2024, 2025, 2025],
        'manager': ['Li', 'Wu', 'Zhao', 'Zhao', 'Li', 'Li', 'Chen'],
    })
    first = df.cpdtab2first_upi__year__manager
    last = df.cpdtab2last_upi__year__manager
    assert first.loc[1].tolist() == ['Li', 'Zhao']
    assert last.loc[1].tolist() == ['Zhao', 'Zhao']
    assert last.loc[2].tolist() == ['Li', 'Chen']
    # 挑一行不是汇总，没有合计
    for out in (first, last):
        assert list(out.index) == [1, 2] and list(out.columns) == [2024, 2025]
    pd.testing.assert_frame_equal(pd.DataFrame(first), pd.DataFrame(df.cpdtab2first_upi___year__manager))
