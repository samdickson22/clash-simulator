"""Shared helpers for the engine-speed study (read-only use of src/)."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import struct
import sys
import time
from pathlib import Path

ES_DIR = Path(__file__).resolve().parent
COUNCIL = ES_DIR.parent
REPO = COUNCIL.parent.parent
TRAIN_DECKS = COUNCIL / "m0/data/roles_v2/training.json"
DEV_DECKS = COUNCIL / "m0/data/roles_v2/development.json"
RESULTS = ES_DIR / "results"
RESULTS.mkdir(exist_ok=True)

sys.dont_write_bytecode = True


def write_json(path: Path, payload) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str))
    tmp.replace(path)


def host_info() -> dict:
    return {
        "load_average": list(os.getloadavg()),
        "pid": os.getpid(),
        "nice": os.getpriority(os.PRIO_PROCESS, 0),
        "python": sys.version.split()[0],
    }


class Timer:
    """Wall and process CPU time of a block."""

    def __init__(self):
        self.wall = 0.0
        self.cpu = 0.0

    def __enter__(self):
        self._w = time.perf_counter()
        self._c = time.process_time()
        return self

    def __exit__(self, *exc):
        self.wall += time.perf_counter() - self._w
        self.cpu += time.process_time() - self._c
        return False


def battle_digest(battle) -> str:
    """Order-sensitive digest of the simulation-relevant battle state."""
    h = hashlib.sha256()
    h.update(struct.pack("<iq", int(battle.tick), int(battle.next_entity_id)))
    for player in battle.players:
        h.update(struct.pack("<d", float(player.elixir)))
        h.update(repr(tuple(player.hand)).encode())
        h.update(repr(tuple(player.cycle_queue)).encode())
    for eid in sorted(battle.entities):
        e = battle.entities[eid]
        h.update(
            struct.pack(
                "<iiddd?",
                int(eid),
                int(e.player_id),
                float(e.position.x),
                float(e.position.y),
                float(e.hitpoints),
                bool(e.is_alive),
            )
        )
        h.update(type(e).__name__.encode())
        h.update(repr(e.target_id).encode())
    h.update(repr((battle.game_over, battle.winner)).encode())
    h.update(repr(battle.rng.getstate()[1][:4]).encode())
    return h.hexdigest()


def peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)


class CollapsedSampler:
    """Pure-Python stack sampler of the main thread (py-spy needs root on macOS).

    Stores collapsed stacks "file:func;file:func;..." (outermost first) with counts.
    The sampling thread needs the GIL, so the switch interval is lowered; overhead
    is a few percent and attribution is unbiased by call counts (unlike cProfile).
    """

    def __init__(self, interval: float = 0.002):
        import collections
        import threading

        self.interval = interval
        self.stacks = collections.Counter()
        self.samples = 0
        self._stop = threading.Event()
        self._target = threading.main_thread().ident
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            frame = sys._current_frames().get(self._target)
            if frame is not None:
                parts = []
                f = frame
                while f is not None:
                    parts.append(f"{'/'.join(f.f_code.co_filename.rsplit('/', 2)[-2:])}:{f.f_code.co_name}")
                    f = f.f_back
                parts.reverse()
                self.stacks[";".join(parts)] += 1
                self.samples += 1
            time.sleep(self.interval)

    def start(self):
        sys.setswitchinterval(0.0005)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join()

    def dump(self, path):
        with open(path, "w") as fh:
            for stack, n in self.stacks.most_common():
                fh.write(f"{stack} {n}\n")


def load_collapsed(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            stack, n = line.rstrip("\n").rsplit(" ", 1)
            out[stack] = out.get(stack, 0) + int(n)
    return out
