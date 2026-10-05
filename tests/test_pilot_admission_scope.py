"""Admission-scope decision v1: the pilot binds admitted simulator modules exactly.

ADMISSION_BOUND = every admitted ``src/clasher`` module except the explicit
training-only list; each must be byte-identical to the Tier A admission pins.
Training-only modules are pinned by the pilot freeze, and the definitions that
admission-bound modules import from them stay AST-identical to the admission.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess

import pytest

from clasher.rl.council_pilot import (
    PILOT_BOUND_SYMBOLS,
    PILOT_TRAINING_ONLY_MODULES,
    file_sha256,
    verify_pilot_source_scope,
)

ROOT = Path(__file__).resolve().parents[1]
COUNCIL = ROOT / "reports/strategy_council_20260928"
V7_ADMISSION = COUNCIL / "m0/readiness/tier-a-fresh-v7/admission.json"
DECISION = COUNCIL / "pilot/admission-scope-decision.json"

TRAINING_ONLY = ("src/clasher/rl/trainer.py",)
BOUND = {"src/clasher/rl/trainer.py": ("learning_math",)}
FILES = {
    "src/clasher/__init__.py": "",
    "src/clasher/rl/__init__.py": "",
    "src/clasher/battle.py": "TICK = 1\n\ndef step(state):\n    return state + TICK\n",
    "src/clasher/rl/opponent.py": (
        "def act(obs):\n"
        "    from .trainer import stack_inputs\n"
        "    return stack_inputs(obs)\n"
    ),
    "src/clasher/rl/trainer.py": (
        "import math\n\n"
        "SCALE = 2\n\n"
        "def _helper(value):\n    return value * SCALE\n\n"
        "def stack_inputs(obs):\n    return _helper(obs)\n\n"
        "def learning_math(x):\n    return math.sqrt(x)\n\n"
        "def main():\n    return 'orchestration'\n"
    ),
}


def _tree(root: Path) -> dict[str, str]:
    for relative, text in FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return {str((root / relative).resolve()): file_sha256(root / relative) for relative in FILES}


def _freeze(root: Path) -> dict[str, str]:
    return {
        str(path.resolve()): file_sha256(path)
        for path in sorted((root / "src/clasher").rglob("*.py"))
    }


@pytest.fixture
def trees(tmp_path):
    admitted = tmp_path / "admitted"
    pilot = tmp_path / "pilot"
    admitted_pins = _tree(admitted)
    shutil.copytree(admitted, pilot)
    return admitted, pilot, admitted_pins


def _verify(admitted, pilot, admitted_pins, pilot_pins=None):
    return verify_pilot_source_scope(
        pilot_root=pilot,
        admitted_root=admitted,
        admitted_pins=admitted_pins,
        pilot_pins=_freeze(pilot) if pilot_pins is None else pilot_pins,
        training_only=TRAINING_ONLY,
        bound_symbols=BOUND,
    )


def test_identical_runtime_passes_and_reports_the_scope(trees):
    admitted, pilot, pins = trees
    scope = _verify(admitted, pilot, pins)
    assert set(scope["admission_bound"]) == set(FILES) - set(TRAINING_ONLY)
    assert scope["training_only_changed"] == []


def test_admission_bound_drift_is_refused_even_when_the_freeze_matches(trees):
    admitted, pilot, pins = trees
    (pilot / "src/clasher/battle.py").write_text(FILES["src/clasher/battle.py"] + "# drift\n")
    with pytest.raises(ValueError, match="admission-bound module differs"):
        _verify(admitted, pilot, pins)


def test_admission_bound_disk_drift_after_freeze_is_refused(trees):
    admitted, pilot, pins = trees
    freeze = _freeze(pilot)
    (pilot / "src/clasher/battle.py").write_text("TICK = 2\n")
    with pytest.raises(ValueError, match="admission-bound module changed on disk"):
        _verify(admitted, pilot, pins, freeze)


def test_training_only_drift_is_allowed_only_when_it_matches_the_freeze(trees):
    admitted, pilot, pins = trees
    trainer = pilot / "src/clasher/rl/trainer.py"
    stale_freeze = _freeze(pilot)
    trainer.write_text(FILES["src/clasher/rl/trainer.py"] + "\ndef throughput():\n    return 64\n")
    with pytest.raises(ValueError, match="differs from the pilot freeze"):
        _verify(admitted, pilot, pins, stale_freeze)
    scope = _verify(admitted, pilot, pins)  # re-frozen: allowed
    assert scope["training_only_changed"] == ["src/clasher/rl/trainer.py"]
    # Exported symbol, declared root and their dependencies were checked.
    assert {"stack_inputs", "_helper", "SCALE", "learning_math", "math"} <= set(
        scope["bound_symbols_checked"]["src/clasher/rl/trainer.py"]
    )
    main_changed = FILES["src/clasher/rl/trainer.py"].replace("'orchestration'", "'faster'")
    trainer.write_text(main_changed)
    assert _verify(admitted, pilot, pins)["training_only_changed"]


@pytest.mark.parametrize(
    "old,new,symbol",
    [
        ("return _helper(obs)", "return _helper(obs) + 1", "stack_inputs"),  # imported by opponent
        ("SCALE = 2", "SCALE = 3", "SCALE"),  # dependency of an exported symbol
        ("return math.sqrt(x)", "return math.sqrt(x) * 2", "learning_math"),  # declared root
        ("import math", "import cmath as math", "math"),  # rebinding an import used by a root
    ],
)
def test_bound_definitions_inside_training_only_modules_cannot_change(trees, old, new, symbol):
    admitted, pilot, pins = trees
    trainer = pilot / "src/clasher/rl/trainer.py"
    trainer.write_text(FILES["src/clasher/rl/trainer.py"].replace(old, new))
    with pytest.raises(ValueError, match=f"definition {symbol} changed"):
        _verify(admitted, pilot, pins)


def test_shadowing_a_bound_definition_is_refused(trees):
    admitted, pilot, pins = trees
    trainer = pilot / "src/clasher/rl/trainer.py"
    trainer.write_text(FILES["src/clasher/rl/trainer.py"] + "\ndef stack_inputs(obs):\n    return obs\n")
    with pytest.raises(ValueError, match="definition stack_inputs changed"):
        _verify(admitted, pilot, pins)


def test_unadmitted_or_missing_modules_are_refused(trees):
    admitted, pilot, pins = trees
    extra = pilot / "src/clasher/rl/new_fast_path.py"
    extra.write_text("X = 1\n")
    with pytest.raises(ValueError, match="unadmitted source module"):
        _verify(admitted, pilot, pins)
    extra.unlink()
    (pilot / "src/clasher/battle.py").unlink()
    with pytest.raises(ValueError, match="admission-bound module missing"):
        _verify(admitted, pilot, pins)


def test_unpinned_or_unadmitted_training_only_modules_are_refused(trees):
    admitted, pilot, pins = trees
    freeze = _freeze(pilot)
    freeze.pop(str((pilot / "src/clasher/rl/trainer.py").resolve()))
    with pytest.raises(ValueError, match="not pinned by the pilot freeze"):
        _verify(admitted, pilot, pins, freeze)
    with pytest.raises(ValueError, match="never admitted"):
        verify_pilot_source_scope(
            pilot_root=pilot,
            admitted_root=admitted,
            admitted_pins=pins,
            pilot_pins=_freeze(pilot),
            training_only=TRAINING_ONLY + ("src/clasher/rl/unknown.py",),
            bound_symbols=BOUND,
        )


def test_whole_module_import_by_a_bound_module_freezes_the_training_module(trees):
    admitted, pilot, pins = trees
    for root in (admitted, pilot):
        (root / "src/clasher/battle.py").write_text("from clasher.rl import trainer\n")
    pins = {str(Path(k)): (file_sha256(k) if Path(k).exists() else v) for k, v in pins.items()}
    (pilot / "src/clasher/rl/trainer.py").write_text(FILES["src/clasher/rl/trainer.py"] + "# c\n")
    with pytest.raises(ValueError, match="imports all of"):
        _verify(admitted, pilot, pins)


def test_pins_outside_the_pilot_root_are_refused(trees, tmp_path):
    admitted, pilot, pins = trees
    freeze = _freeze(pilot)
    freeze[str(tmp_path / "elsewhere.py")] = "0" * 64
    with pytest.raises(ValueError, match="outside the pilot source root"):
        _verify(admitted, pilot, pins, freeze)


def test_decision_receipt_matches_the_enforced_lists():
    if not DECISION.exists():
        pytest.skip("decision receipt not written yet")
    decision = json.loads(DECISION.read_text())
    assert tuple(sorted(decision["training_only"])) == tuple(sorted(PILOT_TRAINING_ONLY_MODULES))
    assert {k: tuple(v) for k, v in decision["bound_symbol_roots"].items()} == PILOT_BOUND_SYMBOLS


@pytest.mark.skipif(not V7_ADMISSION.exists(), reason="v7 admission not present")
def test_real_v7_admission_scope_against_this_workspace(tmp_path):
    admission = json.loads(V7_ADMISSION.read_text())
    admitted_root = Path(admission["source_root"])
    if not admitted_root.exists():
        pytest.skip("admitted snapshot not present")
    copy = tmp_path / "runtime"
    shutil.copytree(admitted_root / "src", copy / "src", copy_function=shutil.copyfile)
    for relative in PILOT_TRAINING_ONLY_MODULES:
        shutil.copyfile(ROOT / relative, copy / relative)
    freeze = _freeze(copy)

    def verify(pins):
        return verify_pilot_source_scope(
            pilot_root=copy,
            admitted_root=admitted_root,
            admitted_pins=admission["source_pins"],
            pilot_pins=pins,
        )

    scope = verify(freeze)
    assert len(scope["admission_bound"]) + len(PILOT_TRAINING_ONLY_MODULES) == len(
        [k for k in admission["source_pins"] if "/src/clasher/" in k]
    )
    assert "src/clasher/rl/model.py" in scope["admission_bound"]
    assert "src/clasher/rl/council_recurrence.py" in scope["admission_bound"]
    # Drift in an admission-bound simulator file -> refuse.
    battle = copy / "src/clasher/battle.py"
    original = battle.read_bytes()
    battle.chmod(0o644)
    battle.write_bytes(original + b"\n# drift\n")
    with pytest.raises(ValueError, match="admission-bound"):
        verify(_freeze(copy))
    battle.write_bytes(original)
    # Drift in admitted learning math inside a training-only file -> refuse.
    trainer = copy / "src/clasher/rl/train_recurrent.py"
    text = trainer.read_text()
    trainer.write_text(text.replace("clipped_values = old_values + value_delta.clamp(-clip_ratio, clip_ratio)",
                                    "clipped_values = old_values + value_delta.clamp(-2 * clip_ratio, clip_ratio)"))
    with pytest.raises(ValueError, match="definition ppo_update changed"):
        verify(_freeze(copy))
    trainer.write_text(text.replace("def _stack_step_inputs(", "def _stack_step_inputs_v2(", 1))
    with pytest.raises(ValueError, match="_stack_step_inputs changed"):
        verify(_freeze(copy))


PILOT_RUNTIME = COUNCIL / "m0/runtime-snapshots/pilot-runtime-v1"
V7_CONFIG = COUNCIL / "pilot/v7-launch/configs/council-pilot-v7-seed2901.toml"


def _pilot_runtime_config(tmp_path: Path, receipt: Path | None = None) -> Path:
    text = "\n".join(
        line for line in V7_CONFIG.read_text().splitlines() if not line.startswith("#")
    )
    snap = str(COUNCIL / "m0/runtime-snapshots/native-final-v7")
    text = text.replace(f'"{snap}/gamedata.json"', f'"{PILOT_RUNTIME}/gamedata.json"')
    text = text.replace(f'"{snap}"', f'"{PILOT_RUNTIME}"')
    text = text.replace(
        f'"{COUNCIL}/pilot/v7-launch/source-pins-native-final-v7.json"',
        f'"{PILOT_RUNTIME}/pilot-source-pins.json"',
    )
    text = text.replace(f'"{COUNCIL}/pilot/v7-launch/runs/s2901"', f'"{tmp_path}/runs"')
    if receipt is not None:
        text = text.replace(f'"{V7_ADMISSION}"', f'"{receipt}"')
    assert "native-final-v7" not in text
    path = tmp_path / "pilot.toml"
    path.write_text(text + "\n")
    return path


def _run_in_pilot_runtime(config: Path) -> "subprocess.CompletedProcess[str]":
    import os
    import subprocess
    import tempfile

    code = (
        "import sys; from pathlib import Path; import clasher;"
        "from clasher.rl.council_pilot import load_pilot_config, require_pilot_admission;"
        f"assert Path(clasher.__file__).resolve().is_relative_to(Path('{PILOT_RUNTIME}'));"
        f"c = load_pilot_config(Path('{config}'));"
        "r = require_pilot_admission(c, Path(c.nominal_admission_path));"
        "print('ADMITTED', r.attempt_id)"
    )
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "CLASHER_ROOT"}}
    env.update(
        CLASHER_ROOT=str(PILOT_RUNTIME),
        PYTHONPATH=f"{PILOT_RUNTIME}/src",
        PYTHONDONTWRITEBYTECODE="1",
        NUMBA_CACHE_DIR=tempfile.mkdtemp(prefix="clasher-numba-"),
    )
    return subprocess.run(
        [str(PILOT_RUNTIME / ".venv/bin/python"), "-B", "-c", code],
        cwd=PILOT_RUNTIME,
        env=env,
        capture_output=True,
        text=True,
        timeout=1800,
    )


@pytest.mark.skipif(not PILOT_RUNTIME.exists() or not V7_CONFIG.exists(), reason="pilot runtime not built")
def test_pilot_runtime_passes_the_full_ledger_admission(tmp_path):
    result = _run_in_pilot_runtime(_pilot_runtime_config(tmp_path))
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ADMITTED m0-tier-a-fresh-v7" in result.stdout


@pytest.mark.skipif(not PILOT_RUNTIME.exists() or not V7_CONFIG.exists(), reason="pilot runtime not built")
def test_pilot_runtime_refuses_a_receipt_the_ledger_did_not_issue(tmp_path):
    copy = tmp_path / "admission.json"
    copy.write_bytes(V7_ADMISSION.read_bytes())
    result = _run_in_pilot_runtime(_pilot_runtime_config(tmp_path, receipt=copy))
    assert result.returncode != 0
    assert "refused the admission" in result.stderr
