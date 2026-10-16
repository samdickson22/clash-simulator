from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TRACE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PublicEntity:
    track_id: str
    player_id: int
    card: str
    x: float
    y: float
    hp: float | None = None


@dataclass(frozen=True)
class PublicFrame:
    timestamp_ms: int
    towers: dict[str, float]
    entities: tuple[PublicEntity, ...]


@dataclass(frozen=True)
class InteractionEvent:
    timestamp_ms: int
    kind: str
    subject: str
    player_id: int | None = None
    card: str | None = None
    amount: float | None = None
    x: float | None = None
    y: float | None = None


def load_public_trace(path: Path) -> list[PublicFrame]:
    """Load normalized observations without modifying the source replay.

    Each JSONL row is a public frame exported by a video/manual adapter. The
    bridge deliberately accepts approximate positions and optional unit HP;
    hidden hand, cycle, elixir, and engine IDs are neither required nor used.
    """

    frames: list[PublicFrame] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        schema = int(payload.get("schema_version", TRACE_SCHEMA_VERSION))
        if schema != TRACE_SCHEMA_VERSION:
            raise ValueError(f"{path}:{line_number}: unsupported schema {schema}")
        timestamp = int(payload["timestamp_ms"])
        if frames and timestamp <= frames[-1].timestamp_ms:
            raise ValueError(f"{path}:{line_number}: timestamps must increase")
        entities = tuple(
            PublicEntity(
                track_id=str(entity["track_id"]),
                player_id=int(entity["player_id"]),
                card=str(entity["card"]),
                x=float(entity["x"]),
                y=float(entity["y"]),
                hp=(None if entity.get("hp") is None else float(entity["hp"])),
            )
            for entity in payload.get("entities", [])
        )
        track_ids = [entity.track_id for entity in entities]
        if len(track_ids) != len(set(track_ids)):
            raise ValueError(f"{path}:{line_number}: duplicate track_id")
        frames.append(
            PublicFrame(
                timestamp_ms=timestamp,
                towers={
                    str(key): float(value)
                    for key, value in payload.get("towers", {}).items()
                },
                entities=entities,
            )
        )
    if not frames:
        raise ValueError(f"trace is empty: {path}")
    return frames


def derive_interactions(frames: Iterable[PublicFrame]) -> list[InteractionEvent]:
    ordered = list(frames)
    if not ordered:
        return []
    events: list[InteractionEvent] = []
    previous_entities: dict[str, PublicEntity] = {}
    previous_towers: dict[str, float] = {}
    for frame in ordered:
        current_entities = {entity.track_id: entity for entity in frame.entities}
        for track_id, entity in current_entities.items():
            previous = previous_entities.get(track_id)
            if previous is None:
                events.append(
                    InteractionEvent(
                        timestamp_ms=frame.timestamp_ms,
                        kind="spawn",
                        subject=track_id,
                        player_id=entity.player_id,
                        card=entity.card,
                        x=entity.x,
                        y=entity.y,
                    )
                )
            elif (
                entity.hp is not None
                and previous.hp is not None
                and entity.hp < previous.hp
            ):
                events.append(
                    InteractionEvent(
                        timestamp_ms=frame.timestamp_ms,
                        kind="unit_damage",
                        subject=track_id,
                        player_id=entity.player_id,
                        card=entity.card,
                        amount=previous.hp - entity.hp,
                        x=entity.x,
                        y=entity.y,
                    )
                )
        for track_id, entity in previous_entities.items():
            if track_id not in current_entities:
                events.append(
                    InteractionEvent(
                        timestamp_ms=frame.timestamp_ms,
                        kind="death_or_hidden",
                        subject=track_id,
                        player_id=entity.player_id,
                        card=entity.card,
                        x=entity.x,
                        y=entity.y,
                    )
                )
        for tower, hp in frame.towers.items():
            previous_hp = previous_towers.get(tower)
            if previous_hp is not None and hp < previous_hp:
                events.append(
                    InteractionEvent(
                        timestamp_ms=frame.timestamp_ms,
                        kind="tower_damage",
                        subject=tower,
                        amount=previous_hp - hp,
                    )
                )
        previous_entities = current_entities
        previous_towers = frame.towers
    return events


def _compatible(observed: InteractionEvent, simulated: InteractionEvent) -> bool:
    if observed.kind != simulated.kind:
        return False
    if observed.kind == "tower_damage":
        return observed.subject == simulated.subject
    return observed.player_id == simulated.player_id and observed.card == simulated.card


def compare_interactions(
    observed: list[InteractionEvent],
    simulated: list[InteractionEvent],
    *,
    time_tolerance_ms: int = 250,
    position_tolerance_tiles: float = 1.0,
    amount_relative_tolerance: float = 0.05,
) -> dict[str, Any]:
    if min(time_tolerance_ms, position_tolerance_tiles, amount_relative_tolerance) < 0:
        raise ValueError("comparison tolerances cannot be negative")
    remaining = set(range(len(simulated)))
    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for observed_index, event in enumerate(observed):
        candidates = [
            index
            for index in remaining
            if _compatible(event, simulated[index])
            and abs(event.timestamp_ms - simulated[index].timestamp_ms)
            <= time_tolerance_ms
        ]
        if not candidates:
            mismatches.append(
                {"type": "missing_simulated_event", "observed": asdict(event)}
            )
            continue
        matched_index = min(
            candidates,
            key=lambda index: abs(event.timestamp_ms - simulated[index].timestamp_ms),
        )
        remaining.remove(matched_index)
        counterpart = simulated[matched_index]
        errors: dict[str, float] = {}
        if (
            event.x is not None
            and event.y is not None
            and counterpart.x is not None
            and counterpart.y is not None
        ):
            errors["position_tiles"] = math.hypot(
                float(event.x) - float(counterpart.x),
                float(event.y) - float(counterpart.y),
            )
        if event.amount is not None and counterpart.amount is not None:
            errors["amount_relative"] = abs(event.amount - counterpart.amount) / max(
                1.0, abs(event.amount)
            )
        errors["time_ms"] = float(abs(event.timestamp_ms - counterpart.timestamp_ms))
        violations = {
            key: value
            for key, value in errors.items()
            if (key == "position_tiles" and value > position_tolerance_tiles)
            or (key == "amount_relative" and value > amount_relative_tolerance)
        }
        record = {
            "observed_index": observed_index,
            "simulated_index": matched_index,
            "observed": asdict(event),
            "simulated": asdict(counterpart),
            "errors": errors,
        }
        if violations:
            record["type"] = "value_mismatch"
            record["violations"] = violations
            mismatches.append(record)
        else:
            matches.append(record)
    for index in sorted(remaining):
        mismatches.append(
            {"type": "extra_simulated_event", "simulated": asdict(simulated[index])}
        )
    observed_count = len(observed)
    return {
        "schema_version": 1,
        "summary": {
            "observed_events": observed_count,
            "simulated_events": len(simulated),
            "matched_events": len(matches),
            "mismatches": len(mismatches),
            "match_rate": len(matches) / max(1, observed_count),
            "exact_within_tolerance": not mismatches,
        },
        "tolerances": {
            "time_ms": time_tolerance_ms,
            "position_tiles": position_tolerance_tiles,
            "amount_relative": amount_relative_tolerance,
        },
        "matches": matches,
        "mismatches": mismatches,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare normalized public real-match frames with a simulated trace"
    )
    parser.add_argument("--observed", required=True)
    parser.add_argument("--simulated", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--events-out", default=None)
    parser.add_argument("--time-tolerance-ms", type=int, default=250)
    parser.add_argument("--position-tolerance-tiles", type=float, default=1.0)
    parser.add_argument("--amount-relative-tolerance", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    observed_path = Path(args.observed).expanduser().resolve()
    simulated_path = Path(args.simulated).expanduser().resolve()
    observed = derive_interactions(load_public_trace(observed_path))
    simulated = derive_interactions(load_public_trace(simulated_path))
    report = compare_interactions(
        observed,
        simulated,
        time_tolerance_ms=args.time_tolerance_ms,
        position_tolerance_tiles=args.position_tolerance_tiles,
        amount_relative_tolerance=args.amount_relative_tolerance,
    )
    report["sources"] = {
        "observed": str(observed_path),
        "simulated": str(simulated_path),
    }
    report_path = Path(args.report_out).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    if args.events_out:
        events_path = Path(args.events_out).expanduser().resolve()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(
                {
                    "observed": [asdict(event) for event in observed],
                    "simulated": [asdict(event) for event in simulated],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
