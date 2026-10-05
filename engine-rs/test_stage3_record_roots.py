"""Record additional accepted pilot roots for the Stage 3 planner differential."""

from collections import defaultdict
import hashlib
import json
import random
import sys
from pathlib import Path
import cloudpickle
from clasher.data import CardDataLoader
from differential import ES, Position, battle_digest
from stage2_matches import battle


def main():
    cache = Path.home() / ".cache/clasher-engine-speed"
    source = cache / "stage0-srp-snapshots.pkl"
    roots = cloudpickle.loads(source.read_bytes())
    rows = [dict(origin="stage0", tick=b.tick, digest=battle_digest(b)) for b in roots]
    games = json.loads((ES / "results/stage2_matches_final3.json").read_text())[
        "results"
    ]
    selected = json.loads((ES / "results/stage3_gate1.json").read_text())["results"]
    extended = "--extended" in sys.argv
    if extended:
        for case in range(8, 16):
            selected[str(case)] = [
                dict(tick=t, digest=None)
                for t in sorted(
                    random.Random(103000 + case).sample(
                        range(90, games[str(case)]["ticks"]), 32
                    )
                )
            ]
    loader = CardDataLoader()
    for case, records in selected.items():
        b = battle(games[case]["episode"], loader)
        ticks = {v["tick"]: v["digest"] for v in records}
        schedule = defaultdict(list)
        for a in games[case]["actions"]:
            schedule[a[0]].append(a)
        while ticks:
            if b.tick in ticks:
                digest = battle_digest(b)
                expected = ticks.pop(b.tick)
                assert expected is None or digest == expected
                roots.append(b.clone())
                rows.append(
                    dict(origin="stage2", case=int(case), tick=b.tick, digest=digest)
                )
            for a in schedule[b.tick]:
                assert b.deploy_card(a[1], a[3], Position(a[4], a[5])) == a[6]
            b.step()
        print("recorded", case, len(roots), flush=True)
    dest = cache / (
        "stage3-srp-search-snapshots.pkl" if extended else "stage3-srp-snapshots.pkl"
    )
    dest.write_bytes(cloudpickle.dumps(roots))
    (
        ES
        / (
            "results/stage3_search_corpus.json"
            if extended
            else "results/stage3_corpus.json"
        )
    ).write_text(
        json.dumps(
            dict(
                path=str(dest),
                sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                stage0_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                roots=rows,
            ),
            indent=2,
        )
        + "\n"
    )
    print("PASS", len(roots), "roots", dest.stat().st_size, "bytes", flush=True)


if __name__ == "__main__":
    main()
