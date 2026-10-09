"""Named table profiles for cpdtab2.

A profile is a bundle of table conventions (value order, total names and
position, share columns, number formats) owned by a domain package. It is
applied only where it is asked for, `df.cpdtab2_a___b__c.myprofile` or
`df.cpdtab2(..., profile="myprofile")`; registering one changes no other call.
"""

from __future__ import annotations

import copy
import json
import re
import warnings
from pathlib import Path

from pandaspro.core.tools.tabrules import POSITION_CHOICES, TOTALS_CHOICES, normalize_total_position

_PROFILES: dict[str, dict] = {}

NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]*$')
# Python format specs that have an exact Excel number format: {:,.0f}  {:.1f}  {:.1%}
FORMAT_PATTERN = re.compile(r'^\{:(,?)\.(\d)([f%])\}$')
PROFILE_KEYS = ('name', 'description', 'totals', 'total_position', 'nested_totals', 'formats', 'fields')
FIELD_KEYS = ('order', 'total_label', 'label', 'total_position', 'share', 'pct_of_total')


def _check_name(name: str) -> None:
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        raise ValueError(
            f"tab profile name {name!r} must be lower_snake_case (letters, digits, underscores; starts with a letter)"
        )
    # imported here: frame.py imports this module
    from pandaspro.core.frame import TabFrame
    from pandaspro.core.tools.tabops import detect_tab_op
    if hasattr(TabFrame, name) or detect_tab_op(name) or name.startswith('cpd'):
        raise ValueError(
            f"tab profile name '{name}' clashes with an existing table attribute; pick another name"
        )


def _clean(spec: dict, allowed: tuple, where: str) -> dict:
    unknown = [key for key in spec if key not in allowed]
    if unknown:
        warnings.warn(f"tab profile {where}: unknown keys ignored: {unknown}", stacklevel=4)
    return {key: copy.deepcopy(value) for key, value in spec.items() if key in allowed}


def _validate(name: str, spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError(f"tab profile '{name}': the spec must be a dict")
    profile = _clean(spec, PROFILE_KEYS, f"'{name}'")
    profile['name'] = name
    if 'totals' in profile and profile['totals'] not in TOTALS_CHOICES:
        raise ValueError(f"tab profile '{name}': totals must be one of {TOTALS_CHOICES}")
    if 'total_position' in profile:
        profile['total_position'] = normalize_total_position(profile['total_position'])
    for kind, fmt in profile.get('formats', {}).items():
        if kind != 'zero' and not FORMAT_PATTERN.match(str(fmt)):
            raise ValueError(
                f"tab profile '{name}': format {kind!r}: {fmt!r} is not supported. "
                "Use '{:,.0f}', '{:.1f}', '{:.1%}' style formats (optional comma, 0-9 decimals, f or %)."
            )
    fields = {}
    for field, rule in profile.get('fields', {}).items():
        rule = _clean(rule, FIELD_KEYS, f"'{name}', field '{field}'")
        if rule.get('total_position') not in (None,) + POSITION_CHOICES:
            raise ValueError(f"tab profile '{name}', field '{field}': total_position must be 'first' or 'last'")
        for entry in ([rule['share']] if isinstance(rule.get('share'), dict) else rule.get('share') or []):
            if 'value' not in entry:
                raise ValueError(f"tab profile '{name}', field '{field}': each share needs a 'value'")
        fields[field] = rule
    profile['fields'] = fields
    return profile


def register_tab_profile(name: str, spec: dict) -> None:
    """Register (or replace) a named table profile. Nothing changes until a call asks for it."""
    _check_name(name)
    _PROFILES[name] = _validate(name, spec)


def load_tab_profiles(path) -> list[str]:
    """Register the profiles found in a .json file, or in every .json file of a folder.

    A file holds one spec (a dict; its "name", or the file name, names the profile) or a list of
    specs. Returns the names registered.
    """
    path = Path(path)
    files = sorted(path.glob('*.json')) if path.is_dir() else [path]
    if not files or not all(file.is_file() for file in files):
        raise FileNotFoundError(f"load_tab_profiles: no .json profile found at {path}")
    names = []
    for file in files:
        with open(file, encoding='utf-8') as handle:
            content = json.load(handle)
        for spec in (content if isinstance(content, list) else [content]):
            name = spec.get('name') or file.stem
            register_tab_profile(name, spec)
            names.append(name)
    return names


def tab_profiles() -> dict:
    """Every registered profile (a copy)."""
    return copy.deepcopy(_PROFILES)


def tab_profile(name: str) -> dict:
    """One registered profile (a copy)."""
    if name not in _PROFILES:
        raise KeyError(f"tab profile '{name}' is not registered. Registered: {sorted(_PROFILES)}")
    return copy.deepcopy(_PROFILES[name])


def unregister_tab_profile(name: str) -> None:
    _PROFILES.pop(name, None)


def is_tab_profile(name: str) -> bool:
    return name in _PROFILES
