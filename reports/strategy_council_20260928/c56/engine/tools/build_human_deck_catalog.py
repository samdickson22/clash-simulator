"""Read only training-role deck identities from the frozen C56 index."""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from clasher.card_aliases import resolve_card_name
from clasher.rl.readiness_root_bank_v3 import (
    C56_SCOPE,
    HumanDeckCatalog,
    HumanDeckFrequency,
)

E = Path(__file__).resolve().parents[1]
DATA = E.parent / "data"
sys.path.insert(0, str(E.parents[1] / "m0/human-prior-scan"))
from card_map import SLUG_TO_GAMEDATA


def main():
    index = DATA / "index/perspectives.jsonl.gz"
    role_file = DATA / "roles/c56_roles_v1.json"
    index_sha = hashlib.sha256(index.read_bytes()).hexdigest()
    roles = json.loads(role_file.read_text())
    assert roles["index_sha256"] == index_sha
    counts = Counter()
    seen = set()
    declared_names = {resolve_card_name(name): name for name in C56_SCOPE}
    with gzip.open(index, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            key = f"{row['tag']}|{row['side']}"
            if roles["roles"].get(key) != "train":
                continue
            assert key not in seen
            seen.add(key)
            cards = tuple(
                sorted(
                    declared_names.get(
                        resolve_card_name(SLUG_TO_GAMEDATA[n]), SLUG_TO_GAMEDATA[n]
                    )
                    for n in row["own_base"]
                )
            )
            if len(set(cards)) == 8 and set(cards) <= set(C56_SCOPE):
                counts[cards] += 1
    catalog = HumanDeckCatalog(
        index_sha256=index_sha,
        roles_sha256=hashlib.sha256(role_file.read_bytes()).hexdigest(),
        decks=tuple(
            HumanDeckFrequency(cards=cards, frequency=n)
            for cards, n in sorted(counts.items())
        ),
    )
    output = E / "root-v3/human_deck_catalog.json"
    with output.open("x") as stream:
        stream.write(catalog.model_dump_json(indent=2) + "\n")
    print(
        json.dumps(
            {
                "unique_decks": len(counts),
                "training_perspectives": sum(counts.values()),
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    main()
