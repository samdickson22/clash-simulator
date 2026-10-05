"""Write prospective readiness episode declarations; never launch collection."""

from __future__ import annotations

import argparse
from pathlib import Path

from clasher.rl.readiness_root_bank import generate_root_bank


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", type=int, choices=(2, 3), default=2)
    parser.add_argument("--human-decks", type=Path)
    parser.add_argument("--bundle", choices=("B1", "B2", "B3", "B4"))
    parser.add_argument("--card-scope", nargs="+")
    args = parser.parse_args()
    if args.version == 3:
        if args.human_decks is None or args.bundle is None:
            parser.error("v3 requires --human-decks and --bundle")
        from clasher.rl.readiness_root_bank_v3 import (
            C56_SCOPE,
            HumanDeckCatalog,
            generate_root_bank_v3,
        )

        bank = generate_root_bank_v3(
            args.master_seed,
            HumanDeckCatalog.model_validate_json(args.human_decks.read_text()),
            args.bundle,
            card_scope=tuple(args.card_scope) if args.card_scope else C56_SCOPE,
        )
    else:
        if args.human_decks is not None or args.bundle is not None or args.card_scope:
            parser.error("human decks, bundle and card scope require --version 3")
        bank = generate_root_bank(args.master_seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(bank.model_dump_json(indent=2) + "\n")


if __name__ == "__main__":
    main()
