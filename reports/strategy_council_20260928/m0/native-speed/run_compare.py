"""Build the comparison pairs for the equivalence study and run them."""
import subprocess, sys
from pathlib import Path
E = Path("equivalence")
def legacy(j):
    return E / "legacy-profile-i1/job-00048" if j == 48 else E / f"legacy-i1-b/job-{j:05d}"
def run(name, pairs):
    argv = [sys.executable, "compare_equivalence.py", "--output", str(E / f"compare-{name}.json")]
    for label, a, b in pairs:
        argv += ["--pair", label, str(a), str(b)]
    subprocess.run(argv, check=True, stdout=subprocess.DEVNULL)
which = sys.argv[1]
if which == "legacy-vs-fast-snapshot":
    run(which, [(f"job{j}", legacy(j), E / f"fast-snapshot-i2/job-{j:05d}") for j in (48, 49, 0, 1, 16, 17, 32, 33)])
elif which == "legacy-vs-fast-replay":
    run(which, [(f"job{j}", legacy(j), E / f"fast-replay-i1/job-{j:05d}") for j in (48, 0, 16, 32)])
elif which == "fast-replay-vs-fast-snapshot":
    run(which, [(f"job{j}", E / f"fast-replay-i1/job-{j:05d}", E / f"fast-snapshot-i2/job-{j:05d}") for j in (48, 0, 16, 32)])
elif which == "render-off":
    run(which, [(f"job{j}", E / f"fast-snapshot-i2/job-{j:05d}", E / f"fast-snapshot-renderoff-i2/job-{j:05d}") for j in (32, 33)]
        + [(f"legacy-job{j}", legacy(j), E / f"fast-snapshot-renderoff-i2/job-{j:05d}") for j in (32, 33)])
