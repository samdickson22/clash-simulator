"""PREREG-K4S Amendment 2 regression: tier_backend.py re-pinned and state_rows.py added after TIERS Amendment 3
(outcome-blind)."""
import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_manifest as B  # noqa: E402
import k4s_logic as L  # noqa: E402

TIER_BACKEND = L.E4V3_REL + "/tier_backend.py"
STATE_ROWS = L.E4V3_REL + "/state_rows.py"
OLD_TIER_BACKEND = "b04d201de7a95a36669e5c11898a297ba8f324d1a658f2987ec5ba244671add7"  # K4S manifest 8bb20a75
NEW_TIER_BACKEND = "02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d"  # TIERS A3, main f6cebbaa
NEW_STATE_ROWS = "3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755"  # TIERS A3 (new file)
# Code that holds a TierBackend/K4SBackend: it may look one state up by id, never read the stream or all inputs.
BACKEND_CONSUMERS = ("mac/k4s_backend.py", "mac/measure_k4s.py", "end_reference.py", "end_background.py")


def manifest():
    return json.loads((L.MAC_DIR / L.MANIFEST_NAME).read_text())


def test_verify_pinned_accepts_amended_tier_backend_and_state_rows_and_rejects_old():
    reused = manifest()["reused_readonly"]
    assert reused[TIER_BACKEND] == NEW_TIER_BACKEND and reused[STATE_ROWS] == NEW_STATE_ROWS
    assert "state_rows.py" in B.E4V3_REUSED
    L.verify_pinned(L.REPO_ROOT, {TIER_BACKEND: NEW_TIER_BACKEND, STATE_ROWS: NEW_STATE_ROWS}, "amended")
    with pytest.raises(L.PreconditionRefusal, match="Pin mismatch .*tier_backend.py"):
        L.verify_pinned(L.REPO_ROOT, {TIER_BACKEND: OLD_TIER_BACKEND}, "8bb20a75")


def e4v3_imports(path, directory):
    """Every module name imported anywhere in ``path`` (incl. lazy imports) that is a file in ``directory``."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return {n + ".py" for n in names if (directory / (n + ".py")).is_file()}


def test_every_e4v3_module_reachable_from_tier_backend_is_pinned():
    directory = L.REPO_ROOT / L.E4V3_REL
    reached, todo = set(), ["tier_backend.py"]
    while todo:
        name = todo.pop()
        if name not in reached:
            reached.add(name)
            todo.extend(e4v3_imports(directory / name, directory))
    assert {"tier_backend.py", "receipts.py", "state_rows.py"} <= reached
    reused = manifest()["reused_readonly"]
    assert {L.E4V3_REL + "/" + n for n in reached} <= set(reused)


def test_backend_consumers_use_only_single_id_lookups():
    """Amendment 3 views: by_id is a one-state cache, rows a stream, inputs only the agreement set."""
    here = Path(__file__).resolve().parent.parent
    for rel in BACKEND_CONSUMERS:
        tree = ast.parse((here / rel).read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("rows", "inputs", "openings", "state_rows"):
                raise AssertionError(f"{rel}:{node.lineno} reads backend.{node.attr}")
            if isinstance(node, ast.Attribute) and node.attr == "by_id":
                parent = parents[node]
                assert isinstance(parent, ast.Subscript) and parent.value is node, f"{rel}:{node.lineno}"
