"""Invariant scanners: money renders must be tri-state and config reads must be guarded.

Not a behaviour test - a repo-shape test. Defects 17/19/21 were invisible to a green unit suite
because each instance lived in a line nobody had a test for: a `:.4f` on a sub-cent spend, a
`.get(key, 0.0)` on a money field, an `isinstance(x, (int, float))` guard accepting a bool cap.
Each was fixed by hand, N times. This file makes the rules that kept recurring checkable by scanning
the money-path modules, so a re-introduction fails a test instead of shipping.

The rules, and why each is a real defect rather than a style preference:

  R1  A bare `"${v:.Nf}"` in a money render loses the tri-state. `None` raises, and a `:.4f`
      flattens a real `$0.000013` to the exact string that means "measured zero". Money must reach
      the page through `money.fmt_usd`. `:g` is *not* flagged: it is exact for any float.
  R2  `.get(money_key, 0.0)` fabricates a measurement: an absent key and a genuine `0.0` become the
      same claim. That is Defect 17 with a default argument.
  R3  Every config/money numeric accessor must delegate to `money.as_float`. A guard re-implemented
      per module is how `isinstance(v, (int, float))` (which accepts `bool`, so
      `pipeline_cap_usd: true` reads as a `$1` cap) got back in after the single-sourcing commit.
      This rule pins the *delegation*, not the `isinstance` spelling: metric/token guards are not
      config readers.
  R4  Every read of an untrusted *LLM score* (judge `score`/`supported`, analyst `CONFIDENCE`) must
      go through `money.unit_score`, and the `max(0.0, min(1.0, ...))` clamp idiom must not appear on
      those modules at all. The clamp is not a guard: `min(1.0, nan)` is `1.0` and `min(1.0, 3)` is
      `1.0`, so it converts a broken or off-scale read into a *perfect* grade -- inflating exactly the
      gates (`faithful_rate >= 0.95`, `p7_rubric mean_score >= 0.8`) it is supposed to protect. An
      interval clamp on a confidence-interval *bound* (`p4b_run.py`) is arithmetic, not grading, so
      that module is deliberately not listed.

Scope is the money-path modules by name, not the whole tree: metric-only modules (recall, gate,
discovery) legitimately carry raw numbers, and a scanner that flagged them would be switched off.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "kb"

MONEY_MODULES = (
    "money.py", "runner.py", "ask.py", "c1_review.py", "p2_tables.py", "p2_series.py",
    "p2_report.py", "p2_known_values.py", "p3_resolve.py", "p4a_report.py",
    "p4b_run.py", "p4c_audit.py", "p4c_daemon.py", "p4c_gate.py", "p4c_glean.py",
    "p4c_highvalue.py", "p4c_ladder.py", "p4c_report.py", "p4c_run.py", "p4c_union.py",
    "p5_build.py", "p6_summary.py",
    "p7_analyst.py", "p7_eval.py", "p7_report.py", "p7_rubric.py", "gold_report.py",
    "p3_report.py", "resume.py",
)

# Every function that reads a numeric out of `kb/config.yaml`, a report JSON, or a *printed numeric
# cell* on a money path. Each must be a thin wrapper over `money.as_float`; the mapping is the
# invariant, asserted below. The three P2 printed-cell parsers are separate implementations of the
# same read, so each is listed: fixing one and missing another leaves the same fabrication reachable
# through a different caller (`float("1" + "0"*400)` is `inf`, not an exception).
ACCESSORS: dict[str, tuple[str, ...]] = {
    "money.py": ("as_float", "unit_score"),
    "runner.py": ("pipeline_cap", "cost_usd", "_tokens"),
    "p4b_run.py": ("pipeline_cap", "p4c_allowance"),
    "p4c_highvalue.py": ("bulk_budget",),
    "p4c_ladder.py": ("escalation_cap",),
    "p2_tables.py": ("_num",),
    "p2_series.py": ("to_number",),
    "p2_report.py": ("to_number",),
    "p2_known_values.py": ("to_number",),
    "p3_resolve.py": ("_num",),
    "p7_report.py": ("_cap_num", "pipeline_cap", "_mean", "_count"),
    "p7_eval.py": ("tolerance_of", "tolerance_or_exact", "gold_numbers"),
    "c1_review.py": ("_num",),
    # Defect 29: the number contract's two-sided reads. `numbers_claimed`/`numbers_in` parse the
    # composer's own sentence (an external, LLM-authored string) and `evidence_numbers` reads the
    # analyst's indicator payloads; both feed `number_ok`, whose `value` may be an unreadable literal.
    "ask.py": ("numbers_in", "numbers_claimed", "_finite_token", "number_ok"),
    "p7_analyst.py": ("evidence_numbers",),
}

# The read of an untrusted LLM *score*. The named function must reach `money.unit_score`, and the
# `min(1.0, min(...))` clamp idiom must not appear anywhere in the module: an off-scale or non-finite
# grade is an unusable read (UNGRADED), never a coerced pass.
GRADE_READERS: dict[str, tuple[str, ...]] = {
    "p6_summary.py": ("clamp_score",),
    "p7_rubric.py": ("clamp_score",),
    "p7_eval.py": ("judge_faithful_cost",),
    "p7_analyst.py": ("parse_analyst",),
    "p7_report.py": ("_metric",),
    # Defect 25: a merge/aggregate read of an LLM-emitted confidence out of a *plain row dict*. The
    # union and gate rows are built from `model_dump`/`dict(rec)` and re-read on the JSONL path, so
    # they never pass the pydantic pin; a bare `isinstance(v, (int, float))` admits `True` (== 1) and
    # `inf`, which then wins a max-merge or drags a mean past `p4c_ladder`'s `low_confidence` trigger.
    # `confidence` is a [0, 1] score, so the one grade-scale rule applies: `money.unit_score`.
    "p4c_gate.py": ("_mean_confidence",),
    "p4c_union.py": ("merge_records",),
    # Defect 26: the P4c gate verdict reads its two rates out of on-disk artefacts (`audit.json`'s
    # `wrong_rate`, `union_stats.json`'s `failure_queue_rate`). Both are `[0, 1]` ratios that a §12
    # gate compares as `rate <= max`, so `inf`/`-inf` used to PASS and `True` used to render as
    # `100.00%`; `money.unit_score` is the one scale rule. `gate_rows` is the verdict site, and the
    # two artefact readers are where the value enters the process.
    "p4c_report.py": ("gate_rows", "audit_gate", "union_stats"),
}

MONEY_KEY_HINTS = ("cost", "spend", "money", "usd", "budget", "allowance", "cap", "price")


def _docstring_lines(tree: ast.AST) -> set[int]:
    """Lines covered by any docstring - prose is allowed to *discuss* the bad patterns."""
    covered: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                covered |= set(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    return covered


def _skip_lines(src: str) -> set[int]:
    """Docstrings only.

    Deliberately *not* "all string literals": the string parts of an f-string are Constants too, so
    skipping every Constant would silence exactly the `f"${v:.4f}"` renders this file exists to
    catch. A docstring is the only place prose may quote a bad pattern.
    """
    return _docstring_lines(ast.parse(src))


def _is_money_name(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in MONEY_KEY_HINTS)


def _rule_r1(name: str, src: str) -> list[str]:
    """A fixed-precision `$` render outside `money` itself. `money.fmt_usd` *is* the renderer."""
    if name == "money.py":
        return []
    out: list[str] = []
    tree = ast.parse(src)
    skip = _skip_lines(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr) or not node.values:
            continue
        head = node.values[0]
        if not (isinstance(head, ast.Constant) and isinstance(head.value, str)
                and "$" in head.value):
            continue
        if node.lineno in skip:
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue) or part.format_spec is None:
                continue
            spec = "".join(v.value for v in part.format_spec.values if isinstance(v, ast.Constant))
            # `.Nf` is lossy; `.Ne` / `g` / `%` are exact-enough and deliberate.
            if "." in spec and spec.endswith("f"):
                out.append(f"{name}:{node.lineno}: bare ${{...:{spec}}} money render (use "
                           f"money.fmt_usd): {lines[node.lineno - 1].strip()[:110]}")
    return out


def _rule_r2(name: str, src: str) -> list[str]:
    """`.get(money_key, <numeric>)`: an absent key and a measured `0.0` become the same claim."""
    out: list[str] = []
    tree = ast.parse(src)
    skip = _skip_lines(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "get"):
            continue
        key, dflt = node.args[0], node.args[1]
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        if not _is_money_name(key.value):
            continue
        if isinstance(dflt, ast.Constant) and isinstance(dflt.value, (int, float)) \
                and not isinstance(dflt.value, bool) and node.lineno not in skip:
            out.append(f"{name}:{node.lineno}: .get('{key.value}', {dflt.value!r}) fabricates a "
                       f"measurement: {lines[node.lineno - 1].strip()[:110]}")
    return out


def _delegates(node: ast.AST, allowed: set[str]) -> bool:
    """True when the body reaches `money.as_float`, directly or through a sibling accessor.

    `p7_report.pipeline_cap` calls `_cap_num`, which calls `money.as_float`; a one-hop chain still
    ends at the single-sourced guard, so following it is not a hole in the rule. `tolerance_or_exact`
    reaches the guard only on its non-`None` arm - that arm is the one that must not be a local
    re-implementation, and the `None` arm is the declared-exact-match convention.
    """
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        if isinstance(fn, ast.Attribute) and fn.attr in allowed:
            return True
        if isinstance(fn, ast.Name) and fn.id in allowed:
            return True
    return False


def _rule_r3(name: str, src: str) -> list[str]:
    """Every named accessor must delegate to `money.as_float`; a missing one is a re-implementation."""
    wanted = ACCESSORS.get(name)
    if not wanted:
        return []
    out: list[str] = []
    tree = ast.parse(src)
    found: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            found.setdefault(node.name, node)
    for fn in wanted:
        node = found.get(fn)
        if node is None:
            out.append(f"{name}: accessor `{fn}` is gone - the module no longer reads its config "
                       f"value through a guarded accessor")
        elif fn != "as_float" and not _delegates(node, set(wanted) | {"as_float"}):
            out.append(f"{name}:{node.lineno}: accessor `{fn}` never reaches money.as_float - a "
                       f"per-module numeric guard can re-admit the bool/NaN defect")
    return out


def _rule_r4(name: str, src: str) -> list[str]:
    """An untrusted LLM score must be read through `money.unit_score`, never range-clamped.

    Two independent checks, because either alone is escapable: the named reader must reach the shared
    guard, and the clamp idiom must not be spelled anywhere in the module (including in an unnamed
    helper that the named reader calls).

    Scoped to GRADE_READERS: a `[0, 1]` interval clamp on a confidence-interval *bound*
    (`p4b_run.py:1140`) is arithmetic on a bound, not a read of an LLM grade, so it is not in scope.
    """
    if name not in GRADE_READERS:
        return []
    tree = ast.parse(src)
    skip = _skip_lines(src)
    lines = src.splitlines()
    out: list[str] = []
    for fn in GRADE_READERS[name]:
        node = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == fn), None)
        if node is None:
            out.append(f"{name}: grade reader `{fn}` is gone - either renamed or the score is no "
                       f"longer read through money.unit_score")
        elif not _delegates(node, {"unit_score", "as_float"}):
            out.append(f"{name}:{node.lineno}: grade reader `{fn}` never reaches money.unit_score - "
                       f"a per-module score guard can re-admit the off-scale/non-finite defect")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # `min(1.0, ...)` / `max(0.0, ...)` is the clamp. `max(1.0, x)` (`p2_report`'s relative
        # tolerance, `p4c_run`'s elapsed seconds) is arithmetic and not part of this idiom.
        for inner in node.args:
            if not (isinstance(inner, ast.Call) and inner.args
                    and isinstance(inner.func, ast.Name) and inner.func.id == "min"):
                continue
            lo = inner.args[0]
            if not (isinstance(lo, ast.Constant) and lo.value == 1.0):
                continue
            if node.lineno in skip:
                continue
            out.append(f"{name}:{node.lineno}: range-clamps an untrusted score instead of reading it "
                       f"through money.unit_score: {lines[node.lineno - 1].strip()[:110]}")
    return out


def scan(sources: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Scan named sources; split from the module list so a test can feed it a bad file."""
    return {
        "R1": [m for n, s in sources for m in _rule_r1(n, s)],
        "R2": [m for n, s in sources for m in _rule_r2(n, s)],
        "R3": [m for n, s in sources for m in _rule_r3(n, s)],
        "R4": [m for n, s in sources for m in _rule_r4(n, s)],
    }


def _money_sources() -> list[tuple[str, str]]:
    out = []
    for name in MONEY_MODULES:
        p = KB / name
        if p.exists():
            out.append((name, p.read_text(encoding="utf-8")))
    return out


_FINDINGS = scan(_money_sources())


def test_r1_no_bare_fixed_precision_dollar_render():
    assert not _FINDINGS["R1"], "\n".join(_FINDINGS["R1"])


def test_r2_no_defaulted_money_get():
    assert not _FINDINGS["R2"], "\n".join(_FINDINGS["R2"])


def test_r3_every_money_accessor_delegates_to_as_float():
    assert not _FINDINGS["R3"], "\n".join(_FINDINGS["R3"])


def test_r4_every_untrusted_score_is_read_through_unit_score():
    assert not _FINDINGS["R4"], "\n".join(_FINDINGS["R4"])


def test_the_scanner_actually_sees_the_money_modules():
    """Guards against a silent pass caused by parsing nothing."""
    names = [n for n, _ in _money_sources()]
    assert "money.py" in names and "p7_report.py" in names and len(names) >= 20
    assert all(MONEY_MODULES.count(n) == 1 for n in names), "duplicate module entry"
    assert set(ACCESSORS) <= set(names), "an accessor module is missing from MONEY_MODULES"
    assert set(GRADE_READERS) <= set(names), "a grade module is missing from MONEY_MODULES"
    # Non-vacuity for R4: every named grade reader must actually be found in its module, so the rule
    # cannot pass by finding no function to inspect.
    srcs = dict(_money_sources())
    for mod, fns in GRADE_READERS.items():
        tree = ast.parse(srcs[mod])
        present = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert set(fns) <= present, f"{mod} is missing {set(fns) - present}"


def test_the_scanner_catches_r4_when_reintroduced():
    """Prove R4 is load-bearing: a range clamp and a score guard that bypasses `unit_score`."""
    clamped = ("def parse_analyst(t):\n"
               "    out = {}\n"
               "    out['confidence'] = max(0.0, min(1.0, float(t)))\n"
               "    return out\n")
    got = scan([("p7_analyst.py", clamped)])
    assert any("range-clamps" in m for m in got["R4"]), got["R4"]
    # A local guard that never reaches unit_score is caught by the delegation half, not the idiom half.
    local = ("def clamp_score(v):\n"
             "    import math\n"
             "    return float(v) if math.isfinite(float(v)) else None\n")
    got2 = scan([("p6_summary.py", local)])
    assert any("never reaches money.unit_score" in m for m in got2["R4"]), got2["R4"]


def test_the_scanner_catches_each_rule_when_reintroduced():
    """Prove the scanner is load-bearing, not vacuous: each pattern must produce a hit on its line.

    Without this, a bug in the AST walk (wrong attribute, wrong tuple shape) would make the rules
    silently vacuous and the suite would stay green through a re-introduction.
    """
    bad = (
        'x = f"spend ${v:.4f}"\n'                     # R1
        'b = rep.get("cost_usd", 0.0)\n'              # R2
        'def escalation_cap():\n'                     # R3: no as_float
        '    return float(CONFIG["cap"])\n'
    )
    got = scan([("badmod.py", bad)])
    lines_hit = {int(f.split(":")[1]) for rule in got for f in got[rule]}
    assert lines_hit == {1, 2}, got
    assert len(got["R1"]) == 1 and len(got["R2"]) == 1, got
    # R3 only inspects modules named in ACCESSORS, so verify it on a real accessor module instead.
    assert scan([("p4c_ladder.py", "def escalation_cap():\n    return 1.0\n")])["R3"]


def test_the_scanner_ignores_prose_and_exact_renders():
    """A docstring quoting the bad pattern, an exact `:g` render, and money.py's own renderer."""
    ok = (
        '"""Docs may say f"${v:.4f}" is wrong."""\n'
        'def f(v):\n'
        '    """Also fine: ${v:.4f}."""\n'
        '    return f"${v:g}"\n'
        'MSG = "cost: $0.00"\n'
        'n = rep.get("cost_usd")\n'
        'm = isinstance(cap, float)  # not a config read: narrows to a type\n'
    )
    got = scan([("okmod.py", ok)])
    assert got == {"R1": [], "R2": [], "R3": [], "R4": []}, got
    assert scan([("money.py", KB.joinpath("money.py").read_text(encoding="utf-8"))]) == {
        "R1": [], "R2": [], "R3": [], "R4": []}
