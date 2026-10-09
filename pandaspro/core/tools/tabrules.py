"""Field-rule registry for cpdtab2.

Domain packages declare, once at import time, how a field behaves in a
cross-tab (value order, the name of its total, share columns). pandaspro keeps
the rules but knows nothing about what the fields mean.
"""

from __future__ import annotations

import copy

_FIELD_RULES: dict[str, dict] = {}
_TAB_DEFAULTS: dict = {}

TOTALS_CHOICES = ('both', 'rows', 'cols', 'none')
POSITION_CHOICES = ('first', 'last')


def normalize_total_position(total_position) -> dict:
    """Accept 'first' / 'last' for both axes, or a dict with 'rows' and/or 'cols'."""
    if total_position is None:
        return {}
    if isinstance(total_position, str):
        total_position = {'rows': total_position, 'cols': total_position}
    unknown = set(total_position) - {'rows', 'cols'}
    if unknown:
        raise ValueError(f"total_position keys must be 'rows' / 'cols', got {sorted(unknown)}")
    for axis, position in total_position.items():
        if position not in POSITION_CHOICES:
            raise ValueError(f"total_position['{axis}'] must be 'first' or 'last', got {position!r}")
    return dict(total_position)


def set_field_rules(
    field: str,
    *,
    order: list | None = None,
    total_label: str | None = None,
    share: dict | list | None = None,
    pct_of_total: dict | str | None = None,
    label: str | None = None,
) -> None:
    """Register cross-tab rules for one field. Arguments left as None keep their current value.

    order        : values in display order; values not listed come after, sorted.
    total_label  : name of the field's aggregate (default "Total").
    share        : {"value": "Open", "label": "% Open"} or a list of such dicts.
    pct_of_total : {"label": "% of Total"} (or just the label).
    label        : header shown for the field (default: the field name).
    """
    if not isinstance(field, str) or not field:
        raise ValueError("set_field_rules: field must be a non-empty string")
    for entry in ([share] if isinstance(share, dict) else share or []):
        if 'value' not in entry:
            raise ValueError("set_field_rules: each share needs a 'value', e.g. {'value': 'Open', 'label': '% Open'}")
    rule = _FIELD_RULES.setdefault(field, {})
    given = {'order': list(order) if order is not None else None, 'total_label': total_label,
             'share': share, 'pct_of_total': pct_of_total, 'label': label}
    rule.update({key: copy.deepcopy(value) for key, value in given.items() if value is not None})


def set_tab_defaults(
    *,
    totals: str | None = None,
    total_position: dict | str | None = None,
    nested_totals: bool | None = None,
) -> None:
    """Register table-wide defaults used when a cpdtab2 call does not pass the argument."""
    if totals is not None:
        if totals not in TOTALS_CHOICES:
            raise ValueError(f"totals must be one of {TOTALS_CHOICES}, got {totals!r}")
        _TAB_DEFAULTS['totals'] = totals
    if total_position is not None:
        merged = {**_TAB_DEFAULTS.get('total_position', {}), **normalize_total_position(total_position)}
        _TAB_DEFAULTS['total_position'] = merged
    if nested_totals is not None:
        _TAB_DEFAULTS['nested_totals'] = bool(nested_totals)


def field_rules(field: str | None = None) -> dict:
    """Registered rules (a copy): all fields, or one field."""
    if field is not None:
        return copy.deepcopy(_FIELD_RULES.get(field, {}))
    return copy.deepcopy(_FIELD_RULES)


def tab_defaults() -> dict:
    """Registered table-wide defaults (a copy)."""
    return copy.deepcopy(_TAB_DEFAULTS)


def clear_field_rules(field: str | None = None) -> None:
    """Forget the rules of one field, or of every field."""
    if field is None:
        _FIELD_RULES.clear()
    else:
        _FIELD_RULES.pop(field, None)


def clear_tab_defaults() -> None:
    _TAB_DEFAULTS.clear()


def has_tab_rules(fields: list[str]) -> bool:
    """True when the registry would change a cross-tab of these fields."""
    return bool(_TAB_DEFAULTS) or any(field in _FIELD_RULES for field in fields)
