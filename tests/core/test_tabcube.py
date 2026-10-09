import math

import pandas as pd
import pytest

import pandaspro as cpd
from pandaspro.core.frame import FramePro, TabFrame

ROWS = [
    ('Staff HQ', 'IBRD/IDA', 'Open', 3),
    ('Staff HQ', 'IBRD/IDA', 'Term', 1),
    ('Staff HQ', 'IFC', 'Open', 1),
    ('Staff non-HQ', 'IBRD/IDA', 'Open', 2),
    ('Staff non-HQ', 'IFC', 'Term', 2),
    ('Staff non-HQ', 'MIGA', 'Open', 1),
]

ORG_ORDER = ['IBRD/IDA', 'IFC', 'MIGA']
EXPECTED = {
    'Staff HQ':     [4, 1, 0.8, 3, 1, 0.75, 1, 0, 1.0, 0, 0, math.nan],
    'Staff non-HQ': [3, 2, 0.6, 2, 0, 1.0, 0, 2, 0.0, 1, 0, 1.0],
    'Total':        [7, 3, 0.7, 5, 1, 5 / 6, 1, 2, 1 / 3, 1, 0, 1.0],
}
EXPECTED_COLUMNS = [(org, inner) for org in ['WBG'] + ORG_ORDER for inner in ['Open', 'Term', '% Open']]


@pytest.fixture(autouse=True)
def clean_registry():
    cpd.clear_field_rules()
    cpd.clear_tab_defaults()
    yield
    cpd.clear_field_rules()
    cpd.clear_tab_defaults()


def _people():
    records, upi = [], 0
    for loc, org, line, n in ROWS:
        for _ in range(n):
            upi += 1
            records.append({'upi': upi, 'loc_new': loc, 'org': org, 'open_term': line, 'salary': 100 + upi * 10})
    return FramePro(records)


def _register_hr_rules():
    cpd.set_field_rules('org', order=ORG_ORDER, total_label='WBG')
    cpd.set_field_rules('open_term', order=['Open', 'Term'], share={'value': 'Open', 'label': '% Open'})
    cpd.set_field_rules('loc_new', order=['Staff HQ', 'Staff non-HQ'], total_label='Total', label='Locations')
    cpd.set_tab_defaults(total_position={'rows': 'last', 'cols': 'first'})


def _assert_acceptance(table):
    assert list(table.columns) == EXPECTED_COLUMNS
    assert list(table.index) == list(EXPECTED)
    for row, expected in EXPECTED.items():
        for got, want in zip(table.loc[row].tolist(), expected):
            assert (math.isnan(got) and math.isnan(want)) or got == pytest.approx(want)
    assert str(table[('WBG', 'Open')].dtype) == 'int64'
    assert str(table[('WBG', '% Open')].dtype) == 'float64'


# ---- backward compatibility: pinned before anything else

def test_no_rules_count_output_is_unchanged():
    out = _people().cpdtab2_loc_new__org
    assert type(out) is FramePro
    assert list(out.columns) == ['IBRD/IDA', 'IFC', 'MIGA', 'Total']
    assert list(out.index) == ['Staff HQ', 'Staff non-HQ', 'Total']
    assert out.loc['Staff HQ'].tolist()[:2] == [4.0, 1.0] and pd.isna(out.loc['Staff HQ', 'MIGA'])
    assert out.loc['Total'].tolist() == [6.0, 3.0, 1.0, 10]


def test_no_rules_nested_columns_output_is_unchanged():
    out = _people().cpdtab2_loc_new___org__open_term
    assert type(out) is FramePro
    assert list(out.columns) == [('IBRD/IDA', 'Open'), ('IBRD/IDA', 'Term'), ('IFC', 'Open'),
                                 ('IFC', 'Term'), ('MIGA', 'Open'), ('Total', '')]
    assert out[('Total', '')].tolist() == [5, 5, 10]


def test_no_rules_subtotal_and_sum_outputs_are_unchanged():
    df = _people()
    sub = df.cpdtab2s_org__loc_new___open_term
    assert ('IBRD/IDA', 'IBRD/IDA Subtotal') in sub.index and sub.index[-1] == ('Total', '')
    total = df.cpdtab2sum_loc_new__org__salary
    assert type(total) is FramePro
    assert list(total.columns) == ['IBRD/IDA', 'IFC', 'MIGA', 'Total']
    assert total.loc['Total', 'Total'] == df['salary'].sum()


def test_rules_for_other_fields_do_not_change_the_output():
    before = _people().cpdtab2_loc_new__org
    cpd.set_field_rules('grade', order=['GA', 'GB'], total_label='All grades')
    after = _people().cpdtab2_loc_new__org
    assert type(after) is FramePro
    pd.testing.assert_frame_equal(pd.DataFrame(before), pd.DataFrame(after))


def test_subtotal_and_pct_shortcuts_ignore_rules():
    df = _people()
    before = (pd.DataFrame(df.cpdtab2s_loc_new__org), pd.DataFrame(df.cpdtab2pctrow_loc_new__org))
    _register_hr_rules()
    after = (pd.DataFrame(df.cpdtab2s_loc_new__org), pd.DataFrame(df.cpdtab2pctrow_loc_new__org))
    for one, two in zip(before, after):
        pd.testing.assert_frame_equal(one, two)


# ---- acceptance example

def test_acceptance_via_attribute():
    _register_hr_rules()
    table = _people().cpdtab2_loc_new___org__open_term
    assert isinstance(table, TabFrame)
    assert table.index.name == 'Locations'
    _assert_acceptance(table)


def test_acceptance_via_method_without_registry():
    table = _people().cpdtab2(
        'loc_new', ['org', 'open_term'],
        total_position={'rows': 'last', 'cols': 'first'},
        total_labels={'org': 'WBG'},
        order={'org': ORG_ORDER, 'open_term': ['Open', 'Term'], 'loc_new': ['Staff HQ', 'Staff non-HQ']},
        shares=[{'field': 'open_term', 'value': 'Open', 'label': '% Open'}],
    )
    _assert_acceptance(table)


def test_display_strings():
    _register_hr_rules()
    shown = _people().cpdtab2_loc_new___org__open_term.display()
    assert shown.loc['Staff HQ'].tolist() == ['4', '1', '80.0%', '3', '1', '75.0%', '1', '-', '100.0%', '-', '-', '-']
    assert shown.loc['Staff non-HQ', ('IFC', '% Open')] == '0.0%'
    big = FramePro({'a': ['x'] * 1234, 'b': ['y'] * 1234}).cpdtab2('a', 'b').display()
    assert big.loc['x', 'y'] == '1,234'


# ---- nested totals

@pytest.mark.parametrize('aggfunc', ['count', 'sum', 'mean'])
def test_nested_totals_are_recomputed_from_the_data(aggfunc):
    df = _people()
    plain = pd.DataFrame(df)
    kwargs = {} if aggfunc == 'count' else {'values': 'salary', 'aggfunc': aggfunc}
    table = df.cpdtab2('loc_new', ['org', 'open_term'], **kwargs)

    def expect(mask):
        subset = plain[mask]
        return len(subset) if aggfunc == 'count' else subset['salary'].agg(aggfunc)

    hq, ibrd, is_open = plain.loc_new == 'Staff HQ', plain.org == 'IBRD/IDA', plain.open_term == 'Open'
    everyone = pd.Series(True, index=plain.index)
    assert table.loc['Staff HQ', ('IBRD/IDA', 'Open')] == pytest.approx(expect(hq & ibrd & is_open))
    assert table.loc['Staff HQ', ('IBRD/IDA', 'Total')] == pytest.approx(expect(hq & ibrd))
    assert table.loc['Staff HQ', ('Total', 'Open')] == pytest.approx(expect(hq & is_open))
    assert table.loc['Staff HQ', ('Total', 'Total')] == pytest.approx(expect(hq))
    assert table.loc['Total', ('IBRD/IDA', 'Open')] == pytest.approx(expect(ibrd & is_open))
    assert table.loc['Total', ('Total', 'Total')] == pytest.approx(expect(everyone))


def test_nested_totals_off_gives_one_grand_total_per_axis():
    table = _people().cpdtab2('loc_new', ['org', 'open_term'], nested_totals=False)
    totalled = [col for col in table.columns if 'Total' in col]
    assert totalled == [('Total', 'Total')]


def test_nested_totals_on_the_row_axis():
    table = _people().cpdtab2(['org', 'loc_new'], 'open_term')
    assert table.loc[('IBRD/IDA', 'Total'), 'Total'] == 6
    assert table.loc[('Total', 'Staff HQ'), 'Open'] == 4
    assert table.loc[('Total', 'Total'), 'Total'] == 10


# ---- totals: which, where, called what

@pytest.mark.parametrize('totals, has_row, has_col', [
    ('both', True, True), ('rows', True, False), ('cols', False, True), ('none', False, False),
])
def test_totals_switch(totals, has_row, has_col):
    table = _people().cpdtab2('loc_new', 'org', totals=totals)
    assert ('Total' in table.index) is has_row
    assert ('Total' in table.columns) is has_col


def test_total_labels_and_position_on_both_axes():
    table = _people().cpdtab2(
        'loc_new', 'org',
        total_labels={'org': 'WBG', 'loc_new': 'All locations'},
        total_position={'rows': 'first', 'cols': 'first'},
    )
    assert table.index[0] == 'All locations' and table.columns[0] == 'WBG'
    assert table.loc['All locations', 'WBG'] == 10
    last = _people().cpdtab2('loc_new', 'org', total_position='last')
    assert last.index[-1] == 'Total' and last.columns[-1] == 'Total'


def test_order_unknown_values_and_blanks():
    df = FramePro({
        'grade': ['GB', 'GA', 'GZ', None, 'GC', 'GA'],
        'org': ['IFC', 'IBRD/IDA', None, 'IFC', 'ZZZ', 'IFC'],
    })
    table = df.cpdtab2('grade', 'org', order={'grade': ['GC', 'GA'], 'org': ['IFC', 'MIGA']})
    # listed first (kept even when absent: MIGA), then the rest sorted, blanks last, total after
    assert list(table.index) == ['GC', 'GA', 'GB', 'GZ', '(blank)', 'Total']
    assert list(table.columns) == ['IFC', 'MIGA', 'IBRD/IDA', 'ZZZ', '(blank)', 'Total']
    assert table['MIGA'].tolist() == [0, 0, 0, 0, 0, 0]
    assert table.loc['Total', 'Total'] == 6           # blanks stay in the counts
    assert table.loc['(blank)', 'IFC'] == 1


# ---- shares

def test_share_with_zero_denominator_is_nan():
    _register_hr_rules()
    table = _people().cpdtab2_loc_new___org__open_term
    assert math.isnan(table.loc['Staff HQ', ('MIGA', '% Open')])
    assert table.loc['Staff non-HQ', ('IFC', '% Open')] == 0.0


def test_share_keeps_total_when_asked():
    table = _people().cpdtab2(
        'loc_new', 'open_term',
        shares=[{'field': 'open_term', 'value': 'Open', 'label': '% Open', 'keep_total': True}],
    )
    assert list(table.columns) == ['Open', 'Term', 'Total', '% Open']
    assert table.loc['Total'].tolist() == [7, 3, 10, 0.7]


def test_share_on_the_row_axis():
    table = _people().cpdtab2('open_term', 'org', shares=[{'field': 'open_term', 'value': 'Open'}])
    assert list(table.index) == ['Open', 'Term', '% Open']
    assert table.loc['% Open', 'IBRD/IDA'] == pytest.approx(5 / 6)


def test_shares_use_counts_even_with_another_aggregation():
    table = _people().cpdtab2('loc_new', 'open_term', values='salary', aggfunc='mean',
                              shares=[{'field': 'open_term', 'value': 'Open', 'label': '% Open'}])
    assert table.loc['Staff HQ', '% Open'] == pytest.approx(0.8)


def test_share_for_a_field_outside_the_table_is_an_error():
    with pytest.raises(ValueError, match="field 'grade' is not in the table"):
        _people().cpdtab2('loc_new', 'org', shares=[{'field': 'grade', 'value': 'GA'}])


def test_pct_of_total_on_columns_and_rows():
    cols = _people().cpdtab2('loc_new', 'org', pct_of_total={'field': 'org', 'label': '% of Total', 'axis': 'cols'})
    assert cols.loc['Staff HQ', ('IBRD/IDA', 'Count')] == 4
    assert cols.loc['Staff HQ', ('IBRD/IDA', '% of Total')] == pytest.approx(0.8)
    assert cols.loc['Staff HQ', ('Total', '% of Total')] == 1.0
    rows = _people().cpdtab2('loc_new', 'org', pct_of_total={'field': 'loc_new', 'label': '% of column'})
    assert rows.loc['Staff HQ', ('IBRD/IDA', '% of column')] == pytest.approx(4 / 6)
    assert math.isnan(rows.loc['Staff HQ', ('MIGA', '% of column')]) is False   # 0 / 1
    empty = FramePro({'a': ['x'], 'b': ['y']}).cpdtab2('a', 'b', order={'b': ['y', 'z']},
                                                    pct_of_total={'field': 'a', 'label': '%'})
    assert math.isnan(empty.loc['x', ('z', '%')])                               # 0 / 0
    with pytest.raises(ValueError, match='is on the cols axis'):
        _people().cpdtab2('loc_new', 'org', pct_of_total={'field': 'org', 'axis': 'rows'})


# ---- registry

def test_registry_set_list_and_clear():
    cpd.set_field_rules('org', order=ORG_ORDER, total_label='WBG')
    cpd.set_field_rules('org', label='Organization')            # merged, not replaced
    assert cpd.field_rules() == {'org': {'order': ORG_ORDER, 'total_label': 'WBG', 'label': 'Organization'}}
    cpd.field_rules()['org']['order'].append('tampered')         # a copy: the registry is not affected
    assert cpd.field_rules('org')['order'] == ORG_ORDER
    cpd.set_tab_defaults(total_position={'cols': 'first'})
    assert cpd.tab_defaults() == {'total_position': {'cols': 'first'}}
    cpd.clear_field_rules('org')
    assert cpd.field_rules() == {}


def test_explicit_arguments_override_registered_rules():
    _register_hr_rules()
    table = _people().cpdtab2('loc_new', 'org', total_labels={'org': 'Bank Group'}, total_position='last',
                              order={'org': ['MIGA']})
    assert list(table.columns) == ['MIGA', 'IBRD/IDA', 'IFC', 'Bank Group']
    no_share = _people().cpdtab2('loc_new', 'open_term', shares=[])
    assert list(no_share.columns) == ['Total', 'Open', 'Term']


def test_aggregation_shortcut_uses_rules():
    _register_hr_rules()
    table = _people().cpdtab2sum_loc_new__org__salary
    assert isinstance(table, TabFrame)
    assert list(table.columns) == ['WBG', 'IBRD/IDA', 'IFC', 'MIGA']
    assert table.loc['Total', 'WBG'] == _people()['salary'].sum()


def test_invalid_options_raise():
    with pytest.raises(ValueError, match='totals must be one of'):
        _people().cpdtab2('loc_new', 'org', totals='sometimes')
    with pytest.raises(ValueError, match="'first' or 'last'"):
        cpd.set_tab_defaults(total_position={'cols': 'left'})
    with pytest.raises(ValueError, match='fields not found'):
        _people().cpdtab2('loc_new', 'nope')
    with pytest.raises(ValueError, match='needs a values column'):
        _people().cpdtab2('loc_new', 'org', aggfunc='sum')


# ---- rename_agg

def test_rename_agg_on_columns_rows_and_several_fields():
    _register_hr_rules()
    table = _people().cpdtab2_loc_new___org__open_term
    renamed = table.rename_agg(org='Bank Group')
    assert isinstance(renamed, TabFrame)
    assert list(renamed.columns)[:3] == [('Bank Group', 'Open'), ('Bank Group', 'Term'), ('Bank Group', '% Open')]
    assert list(renamed.index) == list(table.index)                       # row total untouched
    assert renamed.to_numpy(na_value=-1).tolist() == table.to_numpy(na_value=-1).tolist()
    assert ('WBG', 'Open') in table.columns                               # original untouched

    assert table.rename_agg('loc_new', 'All locations').index[-1] == 'All locations'
    both = table.rename_agg(org='Bank Group', loc_new='All locations')
    assert both.index[-1] == 'All locations' and both.columns[0][0] == 'Bank Group'
    assert both.rename_agg(org='WBG').columns[0][0] == 'WBG'              # can be renamed again


def test_rename_agg_on_a_plain_cpdtab2_result():
    out = _people().cpdtab2_loc_new___org__open_term.rename_agg(org='WBG')
    assert out.columns[-1] == ('WBG', '')
    assert out.index[-1] == 'Total'


def test_rename_agg_errors():
    table = _people().cpdtab2('loc_new', 'org')
    with pytest.raises(ValueError, match="field 'grade' is not in this table"):
        table.rename_agg(grade='All')
    with pytest.raises(ValueError, match='works on a cpdtab2 result'):
        _people().rename_agg(org='WBG')
    with pytest.raises(ValueError, match="no aggregate 'Total' for field 'org'"):
        _people().cpdtab2('loc_new', 'org', totals='rows').rename_agg(org='WBG')


# ---- options chained after the result, presentation

def test_tab_options_understand_custom_total_labels():
    _register_hr_rules()
    table = _people().cpdtab2_loc_new___org__open_term
    without = table.nototal
    assert isinstance(without, TabFrame)
    assert 'WBG' not in without.columns.get_level_values(0) and 'Total' in without.index
    assert math.isnan(without.loc['Staff HQ', ('MIGA', '% Open')])        # shares are not turned into 0
    flat = _people().cpdtab2('loc_new', 'org', total_labels={'loc_new': 'All'}, order={'loc_new': ['Staff non-HQ']})
    assert flat.tsortd_IFC.index.tolist() == ['Staff non-HQ', 'Staff HQ', 'All']
    assert flat.tdiff_1__2['Diff'].tolist() == [0, 3, 3]


def test_style_and_to_excel(tmp_path):
    _register_hr_rules()
    table = _people().cpdtab2_loc_new___org__open_term
    html = table.style.to_html()
    assert '80.0%' in html and 'font-weight: bold' in html

    from openpyxl import load_workbook
    path = tmp_path / 'tab.xlsx'
    table.to_excel(path)
    sheet = load_workbook(path).active
    assert sheet['B1'].value == 'WBG' and sheet['B2'].value == 'Open' and sheet['A2'].value == 'Locations'
    assert 'B1:D1' in [str(rng) for rng in sheet.merged_cells.ranges]
    assert sheet['B3'].value == 4 and sheet['D3'].value == 0.8            # numbers kept
    assert sheet['D3'].number_format == '0.0%' and sheet['B3'].number_format.startswith('#,##0')
    assert sheet['M3'].value is None                                      # NaN share
    assert sheet['A5'].value == 'Total' and sheet['B5'].font.bold and sheet['B3'].font.bold  # total row, WBG column
    assert not sheet['E3'].font.bold


# ---- total position declared on a field (no global defaults needed)

def test_field_rule_total_position_without_tab_defaults():
    df = _people()
    untouched_before = pd.DataFrame(df.cpdtab2_loc_new__open_term)
    cpd.set_field_rules('org', order=ORG_ORDER, total_label='WBG', total_position='first')
    cpd.set_field_rules('open_term_x', total_position='first')       # a field no call uses
    assert cpd.tab_defaults() == {}

    table = df.cpdtab2_loc_new___org__open_term
    assert table.columns[0][0] == 'WBG'                               # ruled field: total first
    assert table.index[-1] == 'Total'                                 # row axis has no rule: stays last

    plain = df.cpdtab2_loc_new__open_term                             # no ruled field: old engine, old output
    assert type(plain) is FramePro
    pd.testing.assert_frame_equal(pd.DataFrame(plain), untouched_before)


def test_total_position_precedence():
    cpd.set_field_rules('org', total_position='first')
    df = _people()
    assert df.cpdtab2('loc_new', 'org').columns[0] == 'Total'                              # rule
    assert df.cpdtab2('loc_new', 'org', total_position={'cols': 'last'}).columns[-1] == 'Total'   # argument wins
    assert df.cpdtab2('org', 'loc_new').index[0] == 'Total'                                # follows the field's axis
    cpd.set_tab_defaults(total_position={'rows': 'first', 'cols': 'last'})
    table = df.cpdtab2('loc_new', 'org')
    assert table.columns[0] == 'Total' and table.index[0] == 'Total'                       # rule beats defaults


def test_outermost_field_decides_total_position():
    cpd.set_field_rules('org', total_position='first')
    cpd.set_field_rules('open_term', total_position='last')
    df = _people()
    outer_org = df.cpdtab2('loc_new', ['org', 'open_term'])
    assert outer_org.columns[0] == ('Total', 'Total')
    outer_open = df.cpdtab2('loc_new', ['open_term', 'org'])
    assert outer_open.columns[-1] == ('Total', 'Total')
    with pytest.raises(ValueError, match="'first' or 'last'"):
        cpd.set_field_rules('org', total_position='left')


# ---- layout-only mode for precomputed cells

def _rate_cells():
    return pd.DataFrame({
        'org': ['__TOTAL__', '__TOTAL__', 'IFC', 'IFC', 'IBRD/IDA', 'IBRD/IDA'],
        'time': ['FY26', 'FY25', 'FY25', 'FY26', 'FY26', 'FY25'],
        'rate': [0.042, 0.0391, 0.05, 0.061, 0.0377, 0.0352],
    })


def test_tab_layout_keeps_the_values_passed_in():
    cpd.set_field_rules('org', order=ORG_ORDER, total_label='WBG', total_position='first')
    table = cpd.tab_layout(_rate_cells(), 'time', 'org', 'rate', formats='pct1')
    assert isinstance(table, TabFrame)
    assert list(table.columns) == ['WBG', 'IBRD/IDA', 'IFC']          # rule order, total first, MIGA not invented
    assert list(table.index) == ['FY25', 'FY26']
    assert table.loc['FY26'].tolist() == [0.042, 0.0377, 0.061]       # exactly what was passed
    assert table.loc['FY25'].tolist() == [0.0391, 0.0352, 0.05]
    assert table.display().loc['FY26', 'WBG'] == '4.2%'
    assert table.rename_agg(org='Bank Group').columns[0] == 'Bank Group'
    # same thing as a method, with the organization on the rows
    by_row = FramePro(_rate_cells()).tab_layout('org', 'time', 'rate')
    assert list(by_row.index) == ['WBG', 'IBRD/IDA', 'IFC'] and by_row.index.name == 'org'
    assert by_row.loc['WBG', 'FY26'] == 0.042


def test_tab_layout_missing_cells_stay_nan_and_duplicates_raise():
    cells = _rate_cells().iloc[:-1]                                   # drop (IBRD/IDA, FY25)
    table = cpd.tab_layout(cells, 'org', 'time', 'rate', total_labels={'org': 'WBG'})
    assert math.isnan(table.loc['IBRD/IDA', 'FY25'])
    assert table.display().loc['IBRD/IDA', 'FY25'] == '-'
    assert list(table.index) == ['IBRD/IDA', 'IFC', 'WBG']            # built-in position: last
    with pytest.raises(ValueError, match='these keys are repeated'):
        cpd.tab_layout(pd.concat([_rate_cells(), _rate_cells().head(1)]), 'org', 'time', 'rate')
    with pytest.raises(ValueError, match='fields not found'):
        cpd.tab_layout(_rate_cells(), 'org', 'time', 'nope')


def test_tab_layout_formats_by_value_of_a_field(tmp_path):
    cells = pd.DataFrame({
        'org': ['__TOTAL__'] * 2 + ['IFC'] * 2,
        'measure': ['Exits', 'Turnover rate'] * 2,
        'value': [1234, 0.0421, 310, 0.0587],
    })
    cpd.set_field_rules('org', total_label='WBG', total_position='first')
    hints = {'measure': {'Turnover rate': 'pct1', 'Exits': 'int'}}
    wide = cpd.tab_layout(cells, 'org', 'measure', 'value', formats=hints)
    assert wide.display().loc['WBG'].tolist() == ['1,234', '4.2%']
    assert wide.loc['WBG', 'Exits'] == 1234 and wide.loc['IFC', 'Turnover rate'] == 0.0587
    tall = cpd.tab_layout(cells, 'measure', 'org', 'value', formats=hints)   # same hint, field on the rows
    assert tall.display().loc['Turnover rate'].tolist() == ['4.2%', '5.9%']
    assert tall.display().loc['Exits', 'WBG'] == '1,234'
    assert '4.2%' in wide.style.to_html()

    from openpyxl import load_workbook
    wide.to_excel(tmp_path / 'rates.xlsx')
    sheet = load_workbook(tmp_path / 'rates.xlsx').active
    assert sheet['C2'].value == 0.0421 and sheet['C2'].number_format == '0.0%'
    assert sheet['B2'].value == 1234 and sheet['B2'].number_format.startswith('#,##0')

    with pytest.raises(ValueError, match='unknown format'):
        cpd.tab_layout(cells, 'org', 'measure', 'value', formats={'measure': {'Exits': 'percent'}})


def test_tab_layout_nested_columns_and_tab_options():
    cells = pd.DataFrame({
        'time': ['FY25'] * 4 + ['FY26'] * 4,
        'org': ['__TOTAL__', '__TOTAL__', 'IFC', 'IFC'] * 2,
        'open_term': ['Open', 'Term'] * 4,
        'n': [10, 4, 3, 1, 12, 5, 4, 2],
    })
    cpd.set_field_rules('org', total_label='WBG', total_position='first')
    table = cpd.tab_layout(cells, 'time', ['org', 'open_term'], 'n')
    assert list(table.columns) == [('WBG', 'Open'), ('WBG', 'Term'), ('IFC', 'Open'), ('IFC', 'Term')]
    assert table.loc['FY26'].tolist() == [12, 5, 4, 2]
    assert list(table.nototal.columns) == [('IFC', 'Open'), ('IFC', 'Term')]
    assert table.tsortd_1.index.tolist() == ['FY26', 'FY25']
