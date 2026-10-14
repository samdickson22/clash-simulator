"""Offline: run safe_input's read gate (exactly loaded_modules_check's read) over every pinned runtime .py outside
the closure, on the 05 staged runtime copy. Read-only."""
import json, os, re, sys
_real_uname = os.uname
NODE = ["127x05"]
class _U:
    def __init__(self, u): self._u = u
    def __getattr__(self, k): return NODE[0] if k == "nodename" else getattr(self._u, k)
os.uname = lambda: _U(_real_uname())
sys.path.insert(0, "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s5s6s7-r7")
import k4s_end_preflight as S
si, tool = S.load_layers()
R = "/mpac/sdicks02/k4s-runner/run-r1/end-staging/runtime-98566c032d0b/runtime"
B = "/mpac/sdicks02/k4s-runner/run-r1/end-staging/bundles/end-ref-127x04-pf00/tiers-pins.json"
rf = json.load(open(B))["runtime_files"]
extra = sorted(r for r in rf if r.endswith(".py") and r not in S.FROZEN_CLOSURE)
bad = []
for host in ("127x03", "127x04"):
    NODE[0] = host
    P = si.Policy(host, [si.Role("runtime-extra", R, "read", 64 << 20, exact=tuple(extra))])
    for rel in extra:
        try:
            si.read_bytes(P, "runtime-extra", rel, expected_sha256=rf[rel])
        except Exception as e:
            bad.append((host, rel, repr(e)[:200]))
print("candidates", len(extra), "refused", len(bad))
for b in bad[:40]: print(b)
