"""Guard for the shortcut manifest (pandaspro.shortcuts).

If a new __getattr__ branch uses a pattern discovery cannot read, the branch
shows up in unrecognized_branches() and test_every_getattr_branch_is_recognized
fails. Fix it in _forms_from_test (once, package-wide) or list the branch in
EXPLICIT_BRANCHES.
"""
import ast
import sys
import textwrap

import pytest

import pandaspro.shortcuts as sc


@pytest.fixture(scope="module")
def manifest():
    return sc.data_shortcuts()


def _names(manifest, owner):
    return {row["name"] for row in manifest["attributes"] if row["owner"] == owner}


def test_manifest_shape(manifest):
    assert manifest["schema"] == sc.SCHEMA
    assert manifest["package"] == "pandaspro"
    assert manifest["attributes"]
    for row in manifest["attributes"]:
        assert row.get("name") and row.get("owner") and row.get("kind"), row


def test_every_getattr_branch_is_recognized():
    missing = sc.unrecognized_branches()
    assert not missing, (
        "These __getattr__ branches are not in the manifest. Teach "
        "_forms_from_test the pattern, or add the branch to EXPLICIT_BRANCHES.\n  "
        + "\n  ".join(missing)
    )


def test_explicit_branches_still_exist():
    """A stale EXPLICIT_BRANCHES key means the branch was rewritten and is
    silently unlisted; its replacement would show up as unrecognized, but a
    deleted branch would not, so check both directions."""
    rows, _ = sc._scan()
    published = {(r["owner"], r["name"]) for r in rows}
    for key, explicit in sc.EXPLICIT_BRANCHES.items():
        if explicit:
            owner = key.split(":", 1)[0]
            assert (owner, explicit["name"]) in published, key


def test_unknown_branch_turns_red():
    src = textwrap.dedent('''
        def __getattr__(self, item):
            if item.startswith('known_'):
                return 1
            elif some_new_matcher(item.lower()):
                return 2
    ''')
    fn_node = ast.parse(src).body[0]
    rows, unrecognized = sc._getattr_branches(fn_node, src, "Probe", sys.modules[__name__], "", 1)
    assert [r["name"] for r in rows] == ["known_…"]
    assert len(unrecognized) == 1 and "some_new_matcher" in unrecognized[0]


def test_framepro_getattr_forms(manifest):
    names = _names(manifest, "FramePro")
    for form in ["cpdmap_", "cpdlist_", "cpdf_", "cpdfnot_", "cpdisna_", "cpdnotna_",
                 "cpdtab_", "cpdtabt_", "cpdtabd_", "cpdtab2_", "cpdtab2s_",
                 "cpdtab2pct_", "cpdtab2pctrow_", "cpdtab2pctcol_",
                 "cpdtab2spct_", "cpdtab2spctrow_", "cpdtab2spctcol_"]:
        assert form + "…" in names


def test_cpdbaseframe_decorator_members(manifest):
    names = _names(manifest, "cpdBaseFrame")
    assert {"get_path", "read_table", "get_file_versions_parser"} <= names
