"""r8 RO-1 (COORDINATOR 02656d67): S10 stages the declared EMPTY runtime directories (frozen es_common.py:20 mkdirs
engine-speed/results at import; the staged runtime is a-w)."""
import copy
import json
import os

from conftest import S10, ok

RES = "reports/strategy_council_20260928/engine-speed/results"
PROD = "/mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b/runtime-manifest.json"


def _manifest(dirs, files):
    return {"inventory": {"dirs": list(dirs), "files": dict((f, {}) for f in files)}}


def test_r8_declared_empty_dir_is_added_sorted():
    m = _manifest(["reports", "reports/strategy_council_20260928", "reports/strategy_council_20260928/engine-speed"],
                  ["reports/strategy_council_20260928/engine-speed/es_common.py"])
    got = S10.runtime_dirs(m)
    ok(RES in got and got == sorted(got) and len(got) == 4)
    ok(S10.RUNTIME_EMPTY_DIRS == (RES,))


def test_r8_refuses_if_tracked_or_parentless():
    base = ["reports", "reports/strategy_council_20260928", "reports/strategy_council_20260928/engine-speed"]
    for m in (_manifest(base + [RES], []), _manifest(base, [RES]), _manifest(base, [RES + "/x.json"]),
              _manifest(base[:2], [])):
        try:
            S10.runtime_dirs(m)
        except Exception as error:                      # safe_input Refusal
            ok("RO-1 empty dir" in str(error))
        else:
            raise AssertionError("runtime_dirs must refuse %r" % (m,))


def test_r8_production_manifest_gains_exactly_the_results_dir():
    if not os.path.exists(PROD):
        return
    with open(PROD) as f:
        m = json.load(f)
    before = list(m["inventory"]["dirs"])
    got = S10.runtime_dirs(copy.deepcopy(m))
    ok(set(got) - set(before) == {RES} and len(got) == len(before) + 1)
