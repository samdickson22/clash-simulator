"""Independently check retained native command submission and spend evidence."""

from __future__ import annotations

import gzip
import json
from itertools import zip_longest
from pathlib import Path
from typing import Any

from clasher.data import CardDataLoader

from .action_space import DiscreteTileActionSpace
from .native_command_checks import validate_command_step
from .native_frame_storage import validate_native_frame_storage
from .own_card_history import AcceptedOwnPlay
from .public_scripted_opponent import PublicScriptedOpponent
from .readiness_execution import canonical_sha, condition_styles, packet_sha


def compact_transport_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: snapshot[key] for key in ("tick", "generation", "stateEpoch")},
        "players": [
            {key: player[key] for key in ("owner", "elixirRaw", "hand")}
            for player in snapshot["players"]
        ],
    }


def audit_native_transport_row(
    row: dict[str, Any], decision: dict[str, Any], loader: CardDataLoader
) -> None:
    validate_native_frame_storage(decision["native_frame"])
    before, after = row["before"], row["after"]
    if before != compact_transport_snapshot(decision["native_frame"]["ordinary"]):
        raise ValueError("transport before-state differs from decision evidence")
    if row["tick"] != decision["tick"] or before["tick"] != row["tick"]:
        raise ValueError("transport/decision tick differs")
    selected = row["selected"]
    if (
        len(selected) != 2
        or any(type(s["owner"]) is not int for s in selected)
        or [s["owner"] for s in selected] != [0, 1]
    ):
        raise ValueError("exactly two ordered seat decisions required")
    if [s["action"] for s in selected] != decision["actions"]:
        raise ValueError("submitted choices differ from recorded policy choices")
    validate_command_step(before, after, row["receipts"])
    commands = []
    space = DiscreteTileActionSpace()
    for choice in selected:
        owner, action = choice["owner"], choice["action"]
        if type(action) is not int or not 0 <= action <= 2304:
            raise ValueError("unsupported transport action")
        if action == 2304:
            if any(choice[key] is not None for key in ("name", "cost", "xy")):
                raise ValueError("wait cannot secretly submit a card")
            continue
        decoded = space.decode_action(action, owner)
        if decoded.position is None:
            raise ValueError("play action has no position")
        xy = [decoded.position.x, decoded.position.y]
        if choice["xy"] != xy:
            raise ValueError("native coordinates differ from policy tile")
        old = next(p for p in before["players"] if p["owner"] == owner)
        new = next(p for p in after["players"] if p["owner"] == owner)
        cards = [c for c in old["hand"] if c["handIndex"] == decoded.slot]
        if len(cards) != 1:
            raise ValueError("command used an empty or ambiguous hand slot")
        card = loader.get_card(choice["name"])
        if card is None or card._raw_entry["id"] != cards[0]["cardId"]:
            raise ValueError("command card identity differs from visible slot")
        cost = cards[0]["cost"]
        if (
            choice["cost"] != cost
            or (old["elixirRaw"] - new["elixirRaw"]) / 10000 < cost - 0.1
        ):
            raise ValueError(
                "accepted command lacks matching public cost/spend evidence"
            )
        commands.append(
            f"replay-schedule-card {owner} {card._raw_entry['id']} {round(xy[0] * 1000)} {round(xy[1] * 1000)} {row['tick'] + 1}"
        )
    if row["commands"] != commands or len(row["receipts"]) != len(commands):
        raise ValueError(
            "exact submitted commands/receipts differ from declared selections"
        )


def audit_native_transport_files(
    directory: Path, loader: CardDataLoader, *, provenance: dict[str, Any] | None = None
) -> int:
    count = 0
    history: list[AcceptedOwnPlay | None] = [None, None]
    if provenance is not None:
        from .native_public_calibration import audit_native_frame
        from .native_public_observation import (
            PUBLIC_REFERENCE_CARDS,
            NativeProjectileCatalog,
            NativePublicObservationAdapter,
            NativePublicScope,
            public_reference_builder,
        )

        catalog = NativeProjectileCatalog.from_csv(
            Path(provenance["catalog_path"]),
            expected_sha256=provenance["catalog_sha256"],
        )
        builder = public_reference_builder(loader, catalog, public_contract_version=4)
        controllers = [
            PublicScriptedOpponent(builder, style=style)
            for style in condition_styles(
                provenance["job"]["condition"], provenance["root_owner"]
            )
        ]
        adapter = NativePublicObservationAdapter(
            builder,
            NativePublicScope("15.535.86", provenance["gamedata_sha256"]),
            card_names=PUBLIC_REFERENCE_CARDS,
            projectile_catalog=catalog,
        )
        for command in json.loads(
            (Path(provenance["capture_path"]) / "result.json").read_text()
        )["commands"]:
            if command["submitted_tick"] < provenance["root_tick"]:
                if command["native_acceptance_spend_evidence"] is not True:
                    raise ValueError("prefix command lacks acceptance evidence")
                history[command["owner"]] = AcceptedOwnPlay(
                    command["name"], command["cost"]
                )
    last_tick = None
    if provenance is not None:
        session = provenance.get("native_read_session")
        if (
            not isinstance(session, dict)
            or session.get("status") != "verified"
            or session.get("failures")
            or session.get("schema") != "native-verified-read-session.v1"
            or session.get("verification_frequency")
            != "full-attestation-at-session-enter-and-close"
        ):
            raise ValueError("native session never completed boundary verification")
        if (
            any(
                session.get(key) != provenance["native_attestation_sha256"]
                for key in (
                    "expected_attestation_sha256",
                    "start_attestation_sha256",
                    "end_attestation_sha256",
                )
            )
            or session.get("reader_sha256") != provenance["native_reader_sha256"]
        ):
            raise ValueError("native session boundary pins differ")
    with (
        gzip.open(directory / "decisions.jsonl.gz", "rt") as decisions,
        gzip.open(directory / "transport.jsonl.gz", "rt") as transports,
    ):
        for decision, transport in zip_longest(decisions, transports):
            if decision is None or transport is None:
                raise ValueError("missing native decision or command transport row")
            decision_row, transport_row = json.loads(decision), json.loads(transport)
            audit_native_transport_row(transport_row, decision_row, loader)
            if provenance is not None:
                tick = decision_row["tick"]
                if tick != (
                    provenance["root_tick"] if last_tick is None else last_tick + 5
                ):
                    raise ValueError(
                        "native branch evidence has a missing decision interval"
                    )
                storage = validate_native_frame_storage(decision_row["native_frame"])
                if (
                    storage is not None
                    and storage.producer_source_sha256
                    != provenance["native_frame_storage_sha256"]
                ):
                    raise ValueError(
                        "compact native frame producer differs from source pin"
                    )
                source = decision_row["native_frame"]["level_source"]
                frame_session = source.get("verified_session", {})
                if (
                    frame_session.get("session_id") != session["session_id"]
                    or frame_session.get("read_index") != count + 1
                    or frame_session.get("runtime_identity")
                    != session["runtime_identity"]
                    or frame_session.get("schema") != "native-verified-read-session.v1"
                    or frame_session.get("verification_frequency")
                    != "full-attestation-at-session-enter-and-close"
                    or frame_session.get("pending_final_verification") is not True
                ):
                    raise ValueError(
                        "native frame is outside the verified read session"
                    )
                if (
                    source["reader_sha256"] != provenance["native_reader_sha256"]
                    or canonical_sha({"ok": True, "attestation": source["attestation"]})
                    != provenance["native_attestation_sha256"]
                ):
                    raise ValueError(
                        "native source reader/runtime differs from pinned provenance"
                    )
                packets, masks, coverage = audit_native_frame(
                    decision_row["native_frame"],
                    builder=builder,
                    adapter=adapter,
                    catalog=catalog,
                    own_history=history,
                )
                if [packet_sha(packet) for packet in packets] != decision_row[
                    "public_sha256"
                ] or coverage != decision_row["level_coverage_by_owner"]:
                    raise ValueError(
                        "public actor packet/coverage does not reproduce from native evidence"
                    )
                if (
                    count == 0
                    and packet_sha(packets[provenance["root_owner"]])
                    != provenance["public_packet_sha256"]
                ):
                    raise ValueError(
                        "native root public state differs from sealed candidate source"
                    )
                expected_actions = [
                    provenance["root_action_id"]
                    if count == 0 and owner == provenance["root_owner"]
                    else controllers[owner].select_action(packet)
                    for owner, packet in enumerate(packets)
                ]
                if decision_row["actions"] != expected_actions:
                    raise ValueError(
                        "native branch did not execute its sealed root candidate/continuation styles"
                    )
                if any(
                    not masks[owner][choice["action"]]
                    for owner, choice in enumerate(transport_row["selected"])
                ):
                    raise ValueError(
                        "native command is outside independently reconstructed public mask"
                    )
                for choice in transport_row["selected"]:
                    if choice["name"] is not None:
                        history[choice["owner"]] = AcceptedOwnPlay(
                            choice["name"], choice["cost"]
                        )
                last_tick = tick
            count += 1
    if count == 0:
        raise ValueError("empty native transport evidence")
    if provenance is not None and session["reads_completed"] != count:
        raise ValueError("native session read coverage differs from retained frames")
    return count


def public_packet_record(packet: Any) -> dict[str, Any]:
    """Retain only the public dataclass contract, with exact array dtypes."""
    from dataclasses import fields

    import numpy as np

    def encode(value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return {"dtype": str(value.dtype), "values": value.tolist()}
        if isinstance(value, AcceptedOwnPlay):
            return {"card_name": value.card_name, "elixir_cost": value.elixir_cost}
        return value

    packet.validate()
    return {
        field.name: (
            {
                inner.name: encode(getattr(packet.observation, inner.name))
                for inner in fields(packet.observation)
            }
            if field.name == "observation"
            else encode(getattr(packet, field.name))
        )
        for field in fields(packet)
    }


def restore_public_packet(record: dict[str, Any]) -> Any:
    import numpy as np

    from .public_observation import ConfidenceAwareActorObservation
    from .structured_obs import ActorObservation

    def decode(name: str, value: Any) -> Any:
        if name == "own_last_play" and value is not None:
            return AcceptedOwnPlay(**value)
        if isinstance(value, dict):
            if set(value) != {"dtype", "values"} or value["dtype"] not in (
                "int64",
                "float32",
                "bool",
            ):
                raise ValueError("unsupported public array serialization")
            return np.asarray(value["values"], dtype=value["dtype"])
        return value

    values = {
        name: decode(name, value)
        for name, value in record.items()
        if name != "observation"
    }
    actor = ActorObservation(
        **{name: decode(name, value) for name, value in record["observation"].items()}
    )
    packet = ConfidenceAwareActorObservation(observation=actor, **values)
    packet.validate()
    return packet


def audit_scalar_decisions(
    directory: Path, loader: CardDataLoader, *, provenance: dict[str, Any]
) -> int:
    from .native_public_observation import (
        NativeProjectileCatalog,
        public_reference_builder,
    )
    from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput

    catalog = NativeProjectileCatalog.from_csv(
        Path(provenance["catalog_path"]), expected_sha256=provenance["catalog_sha256"]
    )
    builder = public_reference_builder(loader, catalog, public_contract_version=4)
    masks = PublicActionMaskBuilder(builder)
    controllers = [
        PublicScriptedOpponent(builder, style=style)
        for style in condition_styles(
            provenance["job"]["condition"], provenance["root_owner"]
        )
    ]
    count, last = 0, None
    with gzip.open(directory / "decisions.jsonl.gz", "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row["tick"] != (provenance["root_tick"] if last is None else last + 5):
                raise ValueError("scalar branch has a missing decision interval")
            packets = [
                restore_public_packet(record) for record in row["public_packets"]
            ]
            if (
                len(packets) != 2
                or [packet_sha(p) for p in packets] != row["public_sha256"]
            ):
                raise ValueError("scalar public packet hash or seat coverage changed")
            expected = []
            for owner, packet in enumerate(packets):
                action = (
                    provenance["root_action_id"]
                    if count == 0 and owner == provenance["root_owner"]
                    else controllers[owner].select_action(packet)
                )
                if not masks.build(
                    PublicActionMaskInput.from_confidence_observation(packet)
                )[action]:
                    raise ValueError(
                        "scalar branch candidate/continuation is not public-legal"
                    )
                expected.append(action)
            if row["actions"] != expected:
                raise ValueError(
                    "scalar branch did not execute its sealed root candidate/continuation styles"
                )
            count += 1
            last = row["tick"]
    if not count:
        raise ValueError("scalar branch lacks retained public decisions")
    return count
