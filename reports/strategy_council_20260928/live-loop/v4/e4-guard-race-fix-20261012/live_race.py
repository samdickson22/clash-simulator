"""Live /proc check: spawn workers between the ownership and census snapshots."""
import multiprocessing as mp, os, sys, tempfile, time
from pathlib import Path
e4v3 = Path(sys.argv[1]); sys.path.insert(0, str(e4v3)); sys.path.insert(0, str(e4v3/"tests"))
from fleet_validity import ReportingGuard
from test_guard_seeds import stage_guard

def idle(stop):
    stop.wait(30)

if __name__ == "__main__":
    ctx = mp.get_context("spawn"); stop = ctx.Event()
    with tempfile.TemporaryDirectory(dir="/mpac/sdicks02/tmp") as tmp:
        manifest, bus, job, _ = stage_guard(Path(tmp))
        guard = ReportingGuard(Path(tmp), manifest, [os.getpid()])
        guard.audit.memory = lambda: 30*2**30
        real = guard.audit.processes
        guard.audit.processes = lambda: [r for r in real() if r["pid"] != bus["pid"]] + [dict(bus)]
        original, workers = guard.audit.census, []
        def census(*a, **k):
            for _ in range(10):
                w = ctx.Process(target=idle, args=(stop,)); w.start(); workers.append(w)
            return original(*a, **k)
        guard.audit.census = census
        row = {}; guard(row); g = row["reporting_guard"]
        mine = {w.pid for w in workers}
        tree = set(mine)
        for d in Path("/proc").iterdir():  # resource tracker etc.
            try:
                if d.name.isdigit() and int((d/"stat").read_text().rsplit(")",1)[1].split()[1]) == os.getpid(): tree.add(int(d.name))
            except OSError: pass
        flagged = sorted({r["pid"] for r in g["foreign_compute"] + g["foreign_active"]} & tree)
        owned = set(map(int, g["owned_pid_start_ticks"]))
        print(dict(fleet_validity=__import__("receipts").sha(e4v3/"fleet_validity.py")[:8], workers=len(mine),
                   workers_owned=len(mine & owned), own_tree_flagged=flagged,
                   other_foreign=len(g["foreign_compute"]) - len(flagged)))
        stop.set(); [w.join(10) for w in workers]
