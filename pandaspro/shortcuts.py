"""Self-describing shortcut manifest for pandaspro.

Aggregators (e.g. sw-workstation-wbghr) call ``data_shortcuts()`` instead of
parsing our ``__getattr__`` source themselves.

Everything here is discovered, never hand-listed:

* every module under ``pandaspro`` is walked with ``pkgutil``;
* every class found (including classes built inside factory/decorator
  functions such as ``cpdBaseFrame``) contributes its public members;
* every top-level ``if``/``elif`` branch of a ``__getattr__`` is parsed into a
  name form such as ``cpdmap_…``.

A branch whose test cannot be parsed is reported by ``unrecognized_branches()``
and fails ``tests/test_shortcuts_complete.py``. Fix it by teaching
``_forms_from_test`` the new pattern, or by adding the branch to
``EXPLICIT_BRANCHES``.
"""
from __future__ import annotations

import ast
import contextlib
import importlib
import io
import inspect
import pkgutil
import textwrap

SCHEMA = 1
PACKAGE = "pandaspro"

# Script folders, not library code: importing them opens Excel, reads local
# files, or prints. Anything else under the package is scanned.
SKIP_MODULES = (f"{PACKAGE}.test", f"{PACKAGE}.dev-cpdreport")
ELLIPSIS = "…"

# Hand-written notes only. Keys are "Owner.name" (or a bare name for all
# owners); values are merged over the discovered row. Never add names here
# that discovery does not already produce.
OVERRIDES: dict[str, dict] = {
    "FramePro.cpdtab2…": {
        "summary": "cpdtab2<agg>_ pivot with an aggregation, e.g. cpdtab2sum_",
        "shape": r"^cpdtab2(min|max|mean|median|sum|std|var|first|last)_",
    },
    "FramePro.cpdtab2s…": {
        "summary": "cpdtab2s<agg>_ pivot with subtotals and an aggregation",
        "shape": r"^cpdtab2s(min|max|mean|median|sum|std|var|first|last)_",
    },
}

# __getattr__ branches whose test is not a name shape. Key is
# "Owner: <branch test source>". Value None = deliberately not a shortcut;
# a dict = the row to publish for it.
EXPLICIT_BRANCHES: dict[str, dict | None] = {
    # column access / fall-through to the parent class
    "FramePro: item in self.columns": None,
    "cpdBaseFrame: hasattr(super(self.__class__, self), item) and not item.startswith(tuple(override_list))": None,
    "DatePro: hasattr(self.dt, item)": None,
    "DatePro: not item.startswith('_')": {
        "name": "<strftime code>",
        "summary": "Any format code, e.g. b_sd_sY -> 'Jan 05 2026' (_c=',' _s=' ' _u='_')",
        "shape": r"^[A-Za-z][A-Za-z_]*$",
        "examples": ["b_sd_sY", "Ymd", "b_sd_c_sY"],
    },
}


# ---------------------------------------------------------------- discovery

def _iter_modules():
    pkg = importlib.import_module(PACKAGE)
    yield pkg
    for info in pkgutil.walk_packages(pkg.__path__, PACKAGE + ".", onerror=lambda name: None):
        if info.name.startswith(SKIP_MODULES):
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                module = importlib.import_module(info.name)
        except Exception:
            continue  # one broken module must not sink the whole manifest
        yield module


def _iter_classes():
    """Yield (owner_name, cls) for every class defined in the package."""
    seen = set()
    for module in _iter_modules():
        for obj in list(vars(module).values()):
            if not inspect.isclass(obj) or obj.__module__ != module.__name__:
                continue
            key = (obj.__module__, obj.__qualname__)
            if key in seen:
                continue
            seen.add(key)
            yield obj.__name__, obj


def _iter_factory_classes():
    """Yield (owner, module, ClassDef, first_line, src) for classes defined
    inside module-level functions, e.g. the class ``@cpdBaseFrame`` builds.
    These do not exist until the factory runs, so they are read from source.
    The owner is the factory's name, which is what users actually write."""
    for module in _iter_modules():
        for name, fn in list(vars(module).items()):
            if not inspect.isfunction(fn) or fn.__module__ != module.__name__:
                continue
            try:
                lines, start = inspect.getsourcelines(fn)
                tree = ast.parse(textwrap.dedent("".join(lines)))
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    yield name, module, node, start, "".join(lines)


def _const(module, name):
    return getattr(module, name, None) if module is not None else None


def _str_items(table):
    out = []
    for item in table or []:
        key = item[0] if isinstance(item, (tuple, list)) and item else item
        if isinstance(key, str):
            out.append(key)
    return out


def _is_item(node, argname):
    return isinstance(node, ast.Name) and node.id == argname


def _forms_from_helper(module, func_name):
    """Forms recognised by a helper like ``detect_cpdtab2_pct(item)``: one
    per entry of any ``for p in <CONST>`` table it loops over."""
    fn = _const(module, func_name)
    if not inspect.isfunction(fn):
        return []
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except Exception:
        return []
    helper_mod = inspect.getmodule(fn)
    forms = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Name):
            forms += [k + ELLIPSIS for k in _str_items(_const(helper_mod, node.iter.id))]
    return forms


def _forms_from_test(test, argname, module):
    """Name forms a branch test accepts. Empty list = not understood.

    Recognised:
      item.startswith('x')              -> x…
      item.startswith(('x', 'y'))       -> x…, y…
      item.startswith(CONST_TABLE)      -> one per entry
      item == 'x'                       -> x
      item in ['x', 'y'] / item in CONST
      helper(item) / (v := helper(item)) where helper loops over a CONST
      a and b / a or b                  -> forms of each side
    """
    if isinstance(test, ast.NamedExpr):
        return _forms_from_test(test.value, argname, module)
    if isinstance(test, ast.BoolOp):
        forms = []
        for value in test.values:
            forms += _forms_from_test(value, argname, module)
        return forms
    if isinstance(test, ast.Call):
        f = test.func
        if isinstance(f, ast.Attribute) and f.attr == "startswith" and _is_item(f.value, argname) and test.args:
            arg = test.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return [arg.value + ELLIPSIS]
            if isinstance(arg, ast.Tuple):
                return [e.value + ELLIPSIS for e in arg.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if isinstance(arg, ast.Name):
                return [k + ELLIPSIS for k in _str_items(_const(module, arg.id))]
        if isinstance(f, ast.Name) and any(_is_item(a, argname) for a in test.args):
            return _forms_from_helper(module, f.id)
    if isinstance(test, ast.Compare) and _is_item(test.left, argname) and len(test.ops) == 1:
        op, right = test.ops[0], test.comparators[0]
        if isinstance(op, ast.Eq) and isinstance(right, ast.Constant) and isinstance(right.value, str):
            return [right.value]
        if isinstance(op, ast.In):
            if isinstance(right, (ast.List, ast.Tuple, ast.Set)):
                return [e.value for e in right.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if isinstance(right, ast.Name):
                return _str_items(_const(module, right.id))
    return []


def _getattr_branches(fn_node, src, owner, module, file, first_line):
    """Parse the top-level if/elif chains of a __getattr__ FunctionDef.

    Returns (rows, unrecognized). Nested helper functions are ignored: only
    the dispatch chain decides which names resolve.
    """
    argname = fn_node.args.args[1].arg if len(fn_node.args.args) > 1 else "item"
    rows, unrecognized = [], []

    def visit(if_node):
        test_src = " ".join((ast.get_source_segment(src, if_node.test) or "").split())
        line = first_line + if_node.lineno - 1
        key = f"{owner}: {test_src}"
        if key in EXPLICIT_BRANCHES:
            explicit = EXPLICIT_BRANCHES[key]
            if explicit:
                rows.append({**explicit, "line": line})
        else:
            forms = _forms_from_test(if_node.test, argname, module)
            if not forms:
                unrecognized.append(f"{module.__name__}.{owner} line {line}: {test_src}")
            rows.extend({"name": form, "line": line} for form in forms)
        chain = if_node.orelse
        if len(chain) == 1 and isinstance(chain[0], ast.If):
            visit(chain[0])

    for stmt in fn_node.body:
        if isinstance(stmt, ast.If):
            visit(stmt)
    for row in rows:
        row.update({"kind": "filter", "owner": owner, "owner_module": module.__name__, "on": ["*"],
                    "source": {"file": file, "line": row.pop("line")}})
    return rows, unrecognized


def _member_kind(value):
    if isinstance(value, property):
        return "property"
    if isinstance(value, staticmethod):
        return "static"
    if isinstance(value, classmethod):
        return "classmethod"
    if inspect.isfunction(value):
        return "method"
    return "attribute"


def _scan_live_class(owner, cls):
    rows, unrecognized = [], []
    module = inspect.getmodule(cls)
    for name, value in vars(cls).items():
        if name == "__getattr__" and inspect.isfunction(value):
            try:
                lines, start = inspect.getsourcelines(value)
                src = textwrap.dedent("".join(lines))
                fn_node = ast.parse(src).body[0]
            except Exception:
                continue
            r, u = _getattr_branches(fn_node, src, owner, module,
                                     inspect.getsourcefile(value) or "", start)
            rows += r
            unrecognized += u
            continue
        if name.startswith("_"):
            continue
        kind = _member_kind(value)
        target = getattr(value, "fget", None) or getattr(value, "__func__", None) or value
        summary = (inspect.getdoc(target) or "").strip().split("\n")[0] if kind != "attribute" else ""
        try:
            file, line = inspect.getsourcefile(target) or "", inspect.getsourcelines(target)[1]
        except Exception:
            file, line = "", 0
        rows.append({"name": name, "kind": kind, "owner": owner, "owner_module": cls.__module__,
                     "summary": summary, "source": {"file": file, "line": line}})
    return rows, unrecognized


def _scan_factory_class(owner, module, class_node, first_line, src):
    rows, unrecognized = [], []
    file = inspect.getsourcefile(module) or ""
    src = textwrap.dedent(src)
    for node in class_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "__getattr__":
            r, u = _getattr_branches(node, src, owner, module, file, first_line)
            rows += r
            unrecognized += u
            continue
        if node.name.startswith("_"):
            continue
        decorators = {d.id for d in node.decorator_list if isinstance(d, ast.Name)}
        kind = ("property" if "property" in decorators
                else "static" if "staticmethod" in decorators
                else "classmethod" if "classmethod" in decorators
                else "method")
        doc = (ast.get_docstring(node) or "").strip().split("\n")[0]
        rows.append({"name": node.name, "kind": kind, "owner": owner, "owner_module": module.__name__,
                     "summary": doc, "source": {"file": file, "line": first_line + node.lineno - 1}})
    return rows, unrecognized


def _scan():
    rows, unrecognized = [], []
    for owner, cls in _iter_classes():
        r, u = _scan_live_class(owner, cls)
        rows += r
        unrecognized += u
    for owner, module, class_node, first_line, src in _iter_factory_classes():
        r, u = _scan_factory_class(owner, module, class_node, first_line, src)
        rows += r
        unrecognized += u
    return rows, unrecognized


def unrecognized_branches() -> list[str]:
    """__getattr__ branches discovery could not turn into a name form."""
    return sorted(set(_scan()[1]))


def discover() -> list[dict]:
    rows, _ = _scan()
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (row["owner_module"], row["owner"], row["name"])
        extra = {**OVERRIDES.get(row["name"], {}), **OVERRIDES.get(f"{row['owner']}.{row['name']}", {})}
        merged[key] = {**merged.get(key, {}), **row, **extra}
    return sorted(merged.values(),
                  key=lambda r: (str(r["name"]).lstrip("_").lower(), r["owner_module"], r["owner"]))


def data_shortcuts() -> dict:
    return {
        "schema": SCHEMA,
        "package": PACKAGE,
        "attributes": discover(),
        "tables": [],
    }
