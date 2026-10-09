import os

import numpy as np
import pandas as pd

from pandaspro.core.stringfunc import parse_wild
from pandaspro.core.tools.consecgrouper import ConsecGrouper
from pandaspro.core.tools.csort import csort
from pandaspro.core.tools.corder import corder
from pandaspro.core.tools.dfilter import dfilter
from pandaspro.core.tools.duplicates_report import duplicates_report
from pandaspro.core.tools.inrange import inrange
from pandaspro.core.tools.lowervarlist import lowervarlist
from pandaspro.core.tools.search2df import search2df
from pandaspro.core.tools.strpos import strpos
from pandaspro.core.tools.tab import tab
from pandaspro.core.tools.tab2 import (
    TAB_KIND_KEY,
    TAB_META_KEY,
    cpdtab2_agg_result,
    cpdtab2_count_result,
    cpdtab2_pct_result,
    detect_cpdtab2_agg,
    detect_cpdtab2_count,
    detect_cpdtab2_pct,
    parse_agg_fields_from_attr,
    parse_pivot_fields_from_attr,
)
from pandaspro.core.tools.tabcube import build_tab, layout_tab
from pandaspro.core.tools.tabformat import tab_display, tab_style, tab_to_excel
from pandaspro.core.tools.tabops import apply_tab_op, detect_tab_op, rename_agg
from pandaspro.core.tools.tabrules import has_tab_rules
from pandaspro.core.tools.tab_singleton_scan import tab_singleton_scan
from pandaspro.core.tools.cpdhelp import cpdhelp
from pandaspro.core.tools.askai import askai as _askai, print_askai_result
from pandaspro.core.tools.varnames import varnames
from pandaspro.core.tools.inlist import inlist
from pandaspro.core.tools.indate import indate
from pandaspro.io.excel.wbexportsimple import WorkbookExportSimplifier


class cpdBaseFrameMapper:
    def __init__(self, d):
        self.dict = d


class cpdBaseFrameList:
    def __init__(self, l):
        self.list = l


class FramePro(pd.DataFrame):
    def __init__(
            self,
            *args,
            uid: str = None,
            exr: str = None,
            rename_status: str = 'Process',
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.uid = uid
        self.export_mapper = cpdBaseFrameMapper(exr)
        self.rename_status = rename_status

    # noinspection PyFinal
    def __getattr__(self, item):
        def _parse_and_match(columns_list, attribute_name):
            """
            解析属性名并匹配列名（cpdtab2 系列在 tools/tab2.py 里解析）
            """
            if attribute_name.startswith('cpdmap_'):
                key_part = attribute_name[7:].split('__')
            elif attribute_name.startswith('cpdlist_'):
                key_part = attribute_name[8:].split('__')
            elif attribute_name.startswith('cpdf_'):
                key_part = [attribute_name[5:].split('__')[0]]
            elif attribute_name.startswith('cpdfnot_'):
                key_part = [attribute_name[8:].split('__')[0]]
            elif attribute_name.startswith('cpdisna_'):
                key_part = attribute_name[8:].split('__')
            elif attribute_name.startswith('cpdnotna_'):
                key_part = attribute_name[9:].split('__')
            elif attribute_name.startswith('cpdtab_'):
                key_part = attribute_name[7:].split('__')
            elif attribute_name.startswith('cpdtabt_'):
                key_part = attribute_name[8:].split('__')
            elif attribute_name.startswith('cpdtabd_'):
                key_part = attribute_name[8:].split('__')
            else:
                raise ValueError('prefix not added in [_parse_and_match] method')

            matched_columns = [col for col in columns_list if col in list(key_part)]

            if attribute_name.startswith('cpdmap_') and len(matched_columns) != 2:
                raise ValueError("Attribute var name parsing results does not match exactly two columns in the frame columns")
            if attribute_name.startswith('cpdlist_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdf_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdfnot_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdisna_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdnotna_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdtab_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdtabt_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            if attribute_name.startswith('cpdtabd_') and len(matched_columns) != 1:
                raise ValueError("Attribute var name parsing results does not match exactly 1 columns in the frame columns")
            matched_columns.sort(key=lambda col: key_part.index(col))

            return matched_columns

        if item in self.columns:
            return super().__getattr__(item)

        if item.startswith('cpdmap_'):
            dict_key_column, dict_value_column = _parse_and_match(self.columns, item)
            return self.set_index(dict_key_column)[dict_value_column].to_dict()

        elif item.startswith('cpdlist_'):
            list_column = _parse_and_match(self.columns, item)[0]
            return self[list_column].drop_duplicates().to_list()

        elif item.startswith('cpdf_'):
            list_column = _parse_and_match(self.columns, item)[0]
            value_filtered = item[10:].split('__')[1]
            return self.inlist(list_column, value_filtered)

        elif item.startswith('cpdfnot_'):
            list_column = _parse_and_match(self.columns, item)[0]
            value_filtered = item[10:].split('__')[1]
            return self.inlist(list_column, value_filtered, invert=True)

        elif item.startswith('cpdisna_'):
            notna_column = _parse_and_match(self.columns, item)[0]
            return self[self[notna_column].isna()]

        elif item.startswith('cpdnotna_'):
            notna_column = _parse_and_match(self.columns, item)[0]
            return self[self[notna_column].notna()]

        elif item.startswith('cpdtab_'):
            list_column = _parse_and_match(self.columns, item)[0]
            return self.tab(list_column)

        elif item.startswith('cpdtabt_'):
            list_column = _parse_and_match(self.columns, item)[0]
            return self.tab(list_column, 'detail')[[list_column, 'count']]

        elif item.startswith('cpdtabd_'):
            list_column = _parse_and_match(self.columns, item)[0]
            return self.tab(list_column, 'detail')

        elif (pct_info := detect_cpdtab2_pct(item)):
            mode, with_subtotals, prefix_len = pct_info
            return cpdtab2_pct_result(
                self, item, mode, with_subtotals, prefix_len, self._constructor
            )

        elif (count_info := detect_cpdtab2_count(item)):
            with_subtotals, prefix_len = count_info
            if not with_subtotals and self._tab_rules_apply():
                pivot_index, pivot_columns = parse_pivot_fields_from_attr(item, prefix_len, self.columns)
                if has_tab_rules(pivot_index + pivot_columns):
                    return self.cpdtab2(pivot_index, pivot_columns)
            return cpdtab2_count_result(self, item, with_subtotals, prefix_len, FramePro)

        elif item.startswith(('cpdtab2s', 'cpdtab2')):
            agg_info = detect_cpdtab2_agg(item)
            if agg_info and not agg_info[1] and self._tab_rules_apply():
                pivot_index, pivot_columns, value_field = parse_agg_fields_from_attr(item, agg_info[2], self.columns)
                if has_tab_rules(pivot_index + pivot_columns):
                    return self.cpdtab2(pivot_index, pivot_columns, values=value_field, aggfunc=agg_info[0])
            return cpdtab2_agg_result(self, item, FramePro)

        elif (tab_op := detect_tab_op(item)):
            return apply_tab_op(self, *tab_op)

        else:
            return super().__getattr__(item)

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            return FramePro(*args, uid=self.uid, exr=self.export_mapper.dict, rename_status=self.rename_status, **kwargs)

        return _c

    @property
    def DF(self):
        return pd.DataFrame(self)

    def _tab_rules_apply(self):
        # Registered field rules are keyed by the working column names, so they are not
        # applied while the frame is in Export naming; the plain pivot is used instead.
        return not (self.export_mapper is not None and self.rename_status == 'Export')

    def cpdtab2(
            self,
            index,
            columns=None,
            values: str = None,
            aggfunc='count',
            totals: str = None,
            total_position=None,
            total_labels: dict = None,
            order: dict = None,
            shares=None,
            pct_of_total=None,
            nested_totals: bool = None,
            fill_value=0,
            dropna_label: str = '(blank)',
            labels: dict = None,
    ):
        """Cross-tab with nested totals, named and positioned totals, fixed value order and share columns.

        Arguments left as None fall back to pandaspro.set_field_rules / set_tab_defaults,
        then to the built-in defaults (totals on both axes, placed last, labelled "Total").

        index, columns : field name or list of field names (outer first).
        values, aggfunc: column to aggregate; without values the rows are counted.
        totals         : "both" | "rows" (total row only) | "cols" (total column only) | "none".
        total_position : "first" / "last", or {"rows": ..., "cols": ...}.
        total_labels   : {field: label}, the name of each field's aggregate.
        order          : {field: [values]}; listed values first (always shown), others after, blanks last.
        shares         : [{"field", "value", "label"}], value / field total, placed after the field's values.
                         A field with a share does not show its own total unless "keep_total": True.
        pct_of_total   : {"field", "label"}, each value's share of the field total, as an extra column level.
        nested_totals  : True = every combination of totalled fields; False = one grand total per axis.
        fill_value     : shown for empty count / sum cells (other aggregations stay NaN).
        dropna_label   : label given to missing field values, so they stay in the counts.
        labels         : {field: header}.

        Returns a TabFrame: the numbers, plus .display(), .style, .to_excel(path) and .rename_agg().
        """
        table, meta = build_tab(
            pd.DataFrame(self), index, columns, values=values, aggfunc=aggfunc, totals=totals,
            total_position=total_position, total_labels=total_labels, order=order, shares=shares,
            pct_of_total=pct_of_total, nested_totals=nested_totals, fill_value=fill_value,
            dropna_label=dropna_label, labels=labels,
        )
        result = TabFrame(table)
        result.attrs[TAB_KIND_KEY] = 'count' if aggfunc in ('count', 'size') else 'agg'
        result.attrs[TAB_META_KEY] = meta
        return result

    def tab_layout(self, index, columns=None, value: str = None, *, total_marker='__TOTAL__',
                   total_position=None, total_labels: dict = None, order: dict = None,
                   labels: dict = None, formats=None):
        """Lay out precomputed cells (one row per cell) as a cpdtab2-style table; see pandaspro.tab_layout."""
        return tab_layout(self, index, columns, value, total_marker=total_marker, total_position=total_position,
                          total_labels=total_labels, order=order, labels=labels, formats=formats)

    def rename_agg(self, field: str = None, label: str = None, **labels):
        """Rename the aggregate of a field in a cpdtab2 result: rename_agg(org="WBG") or rename_agg("org", "WBG")."""
        if field is not None:
            if label is None:
                raise ValueError("rename_agg('field', 'New name') needs both the field and the new name")
            labels = {field: label, **labels}
        if not labels:
            raise ValueError("rename_agg needs at least one field, e.g. rename_agg(org='WBG')")
        return rename_agg(self, labels)

    @property
    def varnames(self):
        return varnames(self)

    def set_uid(self, varname):
        self.uid = varname
        return self._constructor()

    def set_exr(self, exr):
        self.export_mapper = cpdBaseFrameMapper(exr)
        return self._constructor()

    def set_rename_status(self, rename_status):
        self.rename_status = rename_status
        return self._constructor()

    def tab(self, name: str, d: str = 'brief', m: bool = False, sort: str = 'index', ascending: bool = True, label: str = None):
        return self._constructor(tab(self, name, d, m, sort, ascending, label))

    def tab_singleton_scan(self, n: int = 1):
        """
        自检全部字段的 tab 统计，汇总「仅有一个计数恰好等于 n 的取值类别」的字段。

        过滤规则：唯一取值类别 > 30 的字段跳过；≤ 30 时用 tab 统计，
        仅保留恰好存在 1 个 count == n 类别的字段。结果会打印并返回 FramePro。

        Parameters
        ----------
        n : int, optional
            目标计数，默认 1。例如 n=10 可捕捉「恰好一类出现 10 次」的字段。
        """
        return self._constructor(tab_singleton_scan(self, n=n))

    def cpdhelp(self, topic: str = 'all'):
        """打印 FramePro API 速查；df.cpdhelp('tab') 查看 tab / 交叉表用法。"""
        cpdhelp(topic)
        return self

    def askai(
        self,
        question: str,
        topic: str | None = None,
        include_schema: bool = False,
        use_ai: bool = True,
    ):
        """
        基于 cpdhelp 文档检索回答用法问题；配置 local.yaml 中的 ai.api_key 后启用 DeepSeek 解释。

        默认不上传行数据；include_schema=True 时仅附带列名与 dtype。
        AI 回答若含文档未出现的 API 名，将自动回退为 cpdhelp 原文。
        """
        result = _askai(
            self,
            question,
            topic=topic,
            include_schema=include_schema,
            use_ai=use_ai,
        )
        print_askai_result(result)
        self._last_askai_result = result
        return self

    def dfilter(self, inputdict: dict = None, debug: bool = False):
        return self._constructor(dfilter(self, inputdict, debug))

    def csort(
            self,
            column,
            order=None,
            where=None,
            before=None,
            after=None,
            inplace=False
    ):
        return csort(
            self,
            column,
            order=order,
            where=where,
            before=before,
            after=after,
            inplace=inplace
        )

    def corder(
            self,
            column,
            before=None,
            after=None,
            pos='start'
    ):
        return corder(
            self,
            column,
            before=before,
            after=after,
            pos=pos
        )

    def inlist(
            self,
            colname: str,
            *args,
            engine: str = 'b',
            inplace: bool = False,
            invert: bool = False,
            rename: str = None,
            relabel_dict: dict = None,
            debug: bool = False
    ):
        result = inlist(
            self,
            colname,
            *args,
            engine=engine,
            inplace=inplace,
            invert=invert,
            rename=rename,
            relabel_dict=relabel_dict,
            debug=debug,
        )
        if debug:
            print("This is debugger for inlist method: ", result)
            print(type(result))
        if engine == 'm':
            return result
        else:
            return self._constructor(result)

    def inrange(
            self,
            colname: str,
            start,
            stop,
            inclusive: str = 'left',
            engine: str = 'b',
            inplace: bool = False,
            invert: bool = False,
            debug: bool = False
    ):
        result = inrange(
            self,
            colname,
            start,
            stop,
            inclusive=inclusive,
            engine=engine,
            inplace=inplace,
            invert=invert,
            debug=debug,
        )
        if debug:
            print(type(result))
        if engine == 'm':
            return result
        else:
            return self._constructor(result)

    def indate(
            self,
            colname,
            compare,
            date,
            end_date: str = None,
            inclusive: str = 'both',
            engine: str = 'b',
            inplace: bool = False,
            invert: bool = False,
    ):
        result = indate(
            self,
            colname,
            compare,
            date,
            end_date=end_date,
            inclusive=inclusive,
            engine=engine,
            inplace=inplace,
            invert=invert,
        )
        if engine == 'm':
            return result
        else:
            return self._constructor(result)

    def strpos(
            self,
            colname: str,
            *args,
            engine: str = 'b',
            inplace: bool = False,
            invert: bool = False,
            rename: str = None,
            debug: bool = False
    ):
        result = strpos(
            self,
            colname,
            *args,
            engine=engine,
            inplace=inplace,
            invert=invert,
            rename=rename,
            debug=debug,
        )
        if debug:
            print("This is debugger for strpos method: ", result)
            print(type(result))
        if engine == 'm':
            return result
        else:
            return self._constructor(result)

    def create_id(self):
        data = self.copy()
        if 'id' not in data.columns:
            data['id'] = range(1, len(data) + 1)
            data = data.corder('id')
            return data
        else:
            print('id column creation failure: already 1 column with the same name existed')
            return

    def create_ids(self):
        data = self.copy()
        if 'id' not in data.columns:
            data['id'] = range(1, len(data) + 1)
            data = data.corder('id')
            return data
        else:
            print('id column creation failure: already 1 column with the same name existed')
            return

    def lowervarlist(self, engine='columns', inplace=False):
        if engine == 'data':
            return self._constructor(lowervarlist(self, engine, inplace=inplace))
        return lowervarlist(self, engine, inplace=inplace)

    def excel_e(
            self,
            sheet_name: str = 'Sheet1',
            cell: str = 'A1',
            index: bool = False,
            header: bool = True,
            replace: str = None,
            sheetreplace: bool = False,
            design: str = None,
            style: str | list = None,
            cd: str | list = None,
            df_format: dict = None,
            cd_format: list | dict = None,
            config: dict = None,
            override: bool = None,
    ):
        declaredwb = WorkbookExportSimplifier.get_last_declared_workbook()
        if hasattr(self, 'df'):
            data = self.df
        else:
            data = self
        declaredwb.putxl(
            content=data,
            sheet_name=sheet_name,
            cell=cell,
            index=index,
            header=header,
            replace=replace,
            sheetreplace=sheetreplace,
            design=design,
            style=style,
            df_format=df_format,
            cd_format=cd_format,
            config=config,
            cd_style=cd
        )

        # ? Seems to return the declaredwb object to change
        if override:
            return declaredwb

    def expand_column(self, column_list):
        data = self.copy()
        data['expand_key'] = column_list[0]
        data['expand_value'] = data[column_list[0]]

        for i in range(1, len(column_list)):
            append = self.copy()
            append['expand_key'] = column_list[i]
            append['expand_value'] = append[column_list[i]]

            data = pd.concat([data, append], ignore_index=True)
        return data

    def cvar(self, promptstring):
        return parse_wild(promptstring, self.columns)

    def br(self, prompt):
        if isinstance(prompt, list):
            final_selection = []
            for item in prompt:
                final_selection.extend(self.cvar(item))
            return self.loc[:, final_selection]

        elif isinstance(prompt, str):
            return self.loc[:, self.cvar(prompt)]
        else:
            raise TypeError('Invalid input type for prompt')

    def insert_blank(self, locator_dict: dict = None, how: str = 'after', nrows: int = 1):
        # Reset Index to Proceed
        org_cols = self.columns.to_list()
        new_cols = self.reset_index().columns.to_list()
        data_op = self.reset_index().copy()
        toResetIndex = [item for item in new_cols if item not in org_cols]
        if len(toResetIndex) != len(self.index.names):
            raise ValueError(
                "The insert_blank method only supports DataFrames where index labels and column names are unique and do not overlap.")

        # Location Dictionary Decipher into Slicing Points
        ##############################
        condition = pd.Series([True] * len(self), index=self.index)
        slice_indices = []

        if locator_dict is not None:
            for col, value in locator_dict.items():
                if not isinstance(value, list):
                    value = [value]
                else:
                    pass

                for v in value:
                    if col in self.columns:
                        locator = condition & (self[col] == v)
                        slice_indices.append(data_op.index[locator][0])
                    else:
                        print(f"Column '{col}' does not exist in the Frame.")
        #             return self
        else:
            pass

        # Define Cutting Machine
        ##############################
        def split_dataframe(df, indices, mode='before'):
            """
            Splits a DataFrame into segments based on a list of indices and a specified mode.

            Parameters:
            df (pd.DataFrame): The DataFrame to be split.
            indices (list): A list of indices where the splits should occur.
            mode (str): 'before' or 'after', indicating the split mode.

            Returns:
            list: A list of DataFrames resulting from the split.

            Example:
            --------
            Suppose you have a DataFrame `df`:

                A  B
            0   0 21
            1   1 22
            2   2 23
            3   3 24
            4   4 25
            5   5 26
            6   6 27
            7   7 28
            8   8 29
            9   9 30
            10 10 31

            And you want to split it using indices [2, 6] and mode 'before'.
            The function call would be: split_dataframe(df, [2, 6], 'before')

            This would produce three segments:
            Segment 1 (0 to 1):
                A  B
            0  0 21
            1  1 22

            Segment 2 (2 to 5):
                A  B
            2  2 23
            3  3 24
            4  4 25
            5  5 26

            Segment 3 (6 to end):
                A  B
            6  6 27
            7  7 28
            8  8 29
            9  9 30
            10 10 31
            """
            split_dfs = []

            if len(indices) == 0:
                split_dfs.append(df)

            else:
                indices = sorted(set(indices))
                if mode == 'before':
                    split_points = [0] + indices + [len(df)]
                elif mode == 'after':
                    split_points = [0] + [i + 1 for i in indices] + [len(df)]
                else:
                    raise ValueError("The mode parameter must be 'before' or 'after'")

                for i in range(len(split_points) - 1):
                    start, end = split_points[i], split_points[i + 1]
                    split_dfs.append(df.iloc[start:end])

            return split_dfs

        # Cut the DataFrames
        ##############################

        blank_fill = np.full((nrows, len(data_op.columns)), np.nan)
        blank_rows = pd.DataFrame(blank_fill, columns=data_op.columns)
        df_packages = split_dataframe(data_op, slice_indices, mode=how)

        output = pd.DataFrame()
        for index, dfl in enumerate(df_packages):
            output = pd.concat([output, dfl])
            if index + 1 != len(df_packages) or (len(df_packages) == 1 and how == 'after'):
                output = pd.concat([output, blank_rows])

        if len(df_packages) == 1 and how == 'before':
            output = pd.concat([blank_rows, output])

        output = self._constructor(output.set_index(toResetIndex))

        return output

    def search2df(
            self,
            data_large=None,
            dictionary=None,
            key=None,
            threshold=0.9,
            show=True,
            debug=False
    ):
        return search2df(
            data_small=self,
            data_large=data_large,
            dictionary=dictionary,
            key=key,
            threshold=threshold,
            show=show,
            debug=debug
        )

    @property
    def search2df_map(
            self,
    ):
        return search2df(
            data_small=self,
            mapsample=True
        )

    def consecgroup(self, groupby: str | list = None):
        return self._constructor(ConsecGrouper(self, groupby=groupby).group())

    def consecgroup_extract(
            self,
            groupby: str | list = None,
            value_at_top: str | list = None,
            value_at_bottom: str | list = None,
    ):
        return self._constructor(ConsecGrouper(self, groupby=groupby).extract(value_at_top, value_at_bottom))

    # __pandaspro_wangshiyao
    # add instruction and example of use
    def add_total(
            self,
            total_label_column,
            label: str = 'Total',
            sum_columns: str = '_all'
    ):
        total_row = {col: np.nan for col in self.columns}
        # noinspection PyTypeChecker
        total_row[total_label_column] = label

        if sum_columns == '_all':
            sum_columns = self.select_dtypes(include=[np.number]).columns.tolist()
        elif isinstance(sum_columns, (str, int)):
            sum_columns = [sum_columns]

        for col in sum_columns:
            if col in self.columns:
                total_sum = self[col].sum(min_count=1)  # 使用min_count=1确保全为np.nan时结果为0
                total_row[col] = total_sum if not pd.isna(total_sum) else 0

        total_df = pd.DataFrame([total_row], columns=self.columns)
        result = self._constructor(pd.concat([self, total_df], ignore_index=True))

        return result

    def show_duplicates(self, column_list):
        data = self.copy()
        result = self._constructor(data[data.duplicated(subset=column_list, keep='first')])
        return result

    def duplicates_report(self, column_list, d: str = 'brief', dropna: bool = False):
        """
        仿 Stata `duplicates report`：按字段统计重复情况。

        例: df.duplicates_report('upi')                返回 copies / observations / surplus 分布
            df.duplicates_report('upi', d='detail')    逐个列出重复的 upi 及其份数
            df.duplicates_report(['upi', 'year'])
        dropna=True 时依据字段缺失的行不参与统计；要看具体重复行用 df.show_duplicates(...)。
        """
        return self._constructor(duplicates_report(self, column_list, d=d, dropna=dropna))

    # tab.__doc__ = pandaspro.core.tools.tab.tab.__doc__
    # dfilter.__doc__ = pandaspro.core.tools.dfilter.dfilter.__doc__
    # inlist.__doc__ = pandaspro.core.tools.inlist.__doc__
    # varnames.__doc__ = pandaspro.core.tools.varnames.varnames.__doc__
    # lowervarlist.__doc__ = lowervarlist.__doc__

    # Overwriting original methods
    def merge(self, *args, display=None, **kwargs):
        update = kwargs.pop('update', None)  # Extract the 'update' parameter and remove it from kwargs
        '''
        Think about updating this design in the future
        
        # Example usage
        left = CustomDataFrame({
            'key': ['K0', 'K1', 'K2', 'K3'],
            'A': ['A0', None, 'A2', 'A3'],
            'B': ['B0', 'B1', 'B2', None]
        })
        
        right = CustomDataFrame({
            'key': ['K0', 'K1', 'K2', 'K3'],
            'A': ['C0', 'C1', 'C2', 'C3'],
            'C': ['D0', 'D1', 'D2', 'D3']
        })
        
        # Use the new merge method with 'update' parameter
        result_missing = left.merge(right, on='key', update='missing')
        result_all = left.merge(right, on='key', update='all')
        
        print("Result with update='missing':\n", result_missing, "\n")
        print("Result with update='missing':\n", result_missing, "\n")
        print("Result with update='all':\n", result_all)
        '''

        result = super().merge(*args, **kwargs)

        if update == 'missing':
            for col in result.columns:
                if '_x' in col and col.replace('_x', '_y') in result.columns:
                    # Update only if the left column has missing values
                    result[col] = result[col].fillna(result[col.replace('_x', '_y')])
            # Drop the columns from the right DataFrame
            result = result.drop(columns=[col for col in result.columns if '_y' in col])

        elif update == 'all':
            for col in result.columns:
                if '_x' in col and col.replace('_x', '_y') in result.columns:
                    # Update the left column with values from the right column
                    result[col] = result[col.replace('_x', '_y')]
            # Drop the columns from the right DataFrame
            result = result.drop(columns=[col for col in result.columns if '_y' in col])

        result.columns = [col.replace('_x', '') for col in result.columns]
        if '_merge' in result.columns and display is not None:
            # noinspection PyTestUnpassedFixture
            print(result.tab('_merge'))
        return self._constructor(result)

    def rename(self, columns=None, *args, **kwargs):
        return self._constructor(super().rename(columns=columns, *args, **kwargs))


pd.DataFrame.excel_e = FramePro.excel_e


class TabFrame(FramePro):
    """A cpdtab2 result built with field rules: the numbers, plus presentation helpers."""

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            return TabFrame(*args, uid=self.uid, exr=self.export_mapper.dict, rename_status=self.rename_status, **kwargs)

        return _c

    def display(self):
        """The table as formatted strings: 1,234 for counts ("-" for 0 / empty), 80.0% for shares."""
        return tab_display(self)

    @property
    def style(self):
        """Styler with formatted numbers, right alignment and bold totals."""
        return tab_style(self)

    def to_excel(self, excel_writer, sheet_name: str = 'Sheet1', **kwargs):
        """Write a formatted sheet (numbers stay numbers). With an ExcelWriter or extra pandas
        arguments, the plain pandas export is used instead."""
        if kwargs or not isinstance(excel_writer, (str, os.PathLike)):
            return pd.DataFrame(self).to_excel(excel_writer, sheet_name=sheet_name, **kwargs)
        return tab_to_excel(self, excel_writer, sheet_name=sheet_name)



def tab_layout(long_df, index, columns=None, value: str = None, *, total_marker='__TOTAL__',
               total_position=None, total_labels: dict = None, order: dict = None,
               labels: dict = None, formats=None):
    """Lay out precomputed cells the way cpdtab2 would, without aggregating anything.

    long_df has one row per cell: the key columns (index + columns fields) and `value`.
    A key equal to total_marker stands for "the total of that field", computed by the caller.
    Registered field rules give the value order, total labels, total position and headers;
    total_position / total_labels / order / labels override them.

    Only keys present in long_df are shown; a combination without a row stays NaN;
    a key combination that appears twice raises.

    formats: one code for the whole table, or {field: {value: code}} to format the rows /
    columns of that value. Codes: "int" (1,234), "pct1" (4.2%), "num2" (1,234.50), any digit 0-9.

    Returns a TabFrame (.display(), .style, .to_excel(path), .rename_agg()).
    """
    table, meta = layout_tab(
        pd.DataFrame(long_df), index, columns, value, total_marker=total_marker, total_position=total_position,
        total_labels=total_labels, order=order, labels=labels, formats=formats,
    )
    result = TabFrame(table)
    result.attrs[TAB_KIND_KEY] = 'layout'
    result.attrs[TAB_META_KEY] = meta
    return result
