import sys
import warnings

__version__ = '1.2.0'

from pandaspro.email.api import (
    emailfetcher,
    create_mail_class
)

# noinspection PyProtectedMember
from pandaspro.core.api import (
    bdate,
    dfilter,
    FramePro,
    lowervarlist,
    tab,
    str2list,
    wildcardread,
    parse_method,
    parse_wild,
    df_with_index_for_mask,
    create_column_color_dict,
    csort,
    cpdBaseFrameMapper,
    cpdBaseFrameList,
    consecgrouper,
    replace_left_with_right,
    replace_left_with_target,
    compare,
    align_and_sort_by_order,
    ensure_columns,
    set_field_rules,
    set_tab_defaults,
    field_rules,
    tab_defaults,
    clear_field_rules,
    clear_tab_defaults,
    TabFrame,
    tab_layout
)

from pandaspro.cpdbase.api import (
    cpdBaseFrame,
    FilesVersionParser
)

from pandaspro.date.api import (
    DatePro
)

from pandaspro.io.api import (
    CellPro,
    index_cell,
    cell_index,
    resize,
    offset,
    getrange,
    PutxlSet,
    pwread,
    WorkbookExportSimplifier,
    fw
)

from pandaspro.sampledf.api import (
    sysuse_countries,
    sysuse_auto,
    wbuse_pivot
)

from pandaspro.pdfs.api import (
    merge_pdfs
)

excel_d = WorkbookExportSimplifier().declare_workbook
