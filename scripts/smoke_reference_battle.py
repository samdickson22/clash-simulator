"""Exercise both native players and compare two deterministic short trajectories."""

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path


def request(port: int, command: str) -> dict:
    with socket.create_connection(("127.0.0.1", port), timeout=30) as connection:
        connection.sendall((command + "\n").encode())
        response = bytearray()
        while chunk := connection.recv(65536):
            response.extend(chunk)
            if len(response) > 16 * 1024 * 1024:
                raise ValueError("oversized response")
    result = json.loads(response)
    if not result.get("ok"):
        raise ValueError(f"native command rejected: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    payload = json.dumps(json.loads(args.config.read_text()), separators=(",", ":"))
    runs = []
    for repeat in range(2):
        config = request(args.port, "configure " + payload)
        assert config["tick"] == 0
        request(args.port, "step 70")
        before = request(args.port, "observe")
        actions = []
        for owner in (0, 1):
            player = next(p for p in before["players"] if p["owner"] == owner)
            card = next(c for c in player["hand"] if c["cardId"] == 26000005)
            actions.extend(
                [owner, card["handIndex"], 3500, 10500 if owner == 0 else 21500]
            )
        after = request(args.port, "play 1 40 2 " + " ".join(map(str, actions)))
        assert after["tick"] == 110 and not after["truncated"]
        for owner in (0, 1):
            player = next(p for p in after["players"] if p["owner"] == owner)
            original = next(p for p in before["players"] if p["owner"] == owner)
            assert 2 < original["elixir"] - player["elixir"] < 3
            assert player["hand"] != original["hand"]
        assert after["count"] == before["count"] + 6
        request(args.port, "step 150")
        fought = request(args.port, "observe")
        assert fought["tick"] == 260 and not fought["truncated"]
        run = {"before": before, "deployed": after, "after_combat": fought}
        (args.output / f"run-{repeat}.json").write_text(
            json.dumps(run, indent=2) + "\n"
        )
        # Generation/state epochs identify allocations, not gameplay state.
        runs.append(
            {
                phase: {
                    k: v
                    for k, v in frame.items()
                    if k not in {"generation", "stateEpoch"}
                }
                for phase, frame in run.items()
            }
        )
    equal = runs[0] == runs[1]
    result = {
        "status": "passed" if equal else "repeat_difference",
        "repeat_exact_gameplay_fields": equal,
        "both_players_spent_elixir_and_changed_hand": True,
        "spawned_units": 6,
        "final_tick": 260,
        "scope": "Native runtime/action plumbing only; no official-game fidelity or human-level play claim.",
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if equal else 1)


if __name__ == "__main__":
    main()
