"""Five-tick causal root-prefix collection; never claims complete-game outcomes."""

from __future__ import annotations

import gzip
import json
import shutil
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any, Literal

from clasher.data import CardDataLoader

from .action_space import DiscreteTileActionSpace
from .native_command_checks import validate_command_step
from .native_frame_storage import compact_native_frame
from .own_card_history import AcceptedOwnPlay
from .public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from .public_observation import ConfidenceAwareActorObservation
from .public_policy_contract import PublicPolicySequence
from .public_scripted_opponent import PublicScriptedOpponent
from .readiness_execution import packet_sha
from .readiness_root_bank import (
    RootRequest,
    RootSelection,
    apply_prefix_owner_reserve,
    select_root,
)
from .structured_obs import StructuredObservationBuilder

Frame = dict[str, Any]
Command = Callable[[str], Frame]
Project = Callable[
    [Frame, list[AcceptedOwnPlay | None]], list[ConfidenceAwareActorObservation]
]


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def collect_prefix(
    root: RootRequest,
    config: Frame,
    *,
    output: Path,
    role: Literal["opened_development", "fresh_acceptance"],
    builder: StructuredObservationBuilder,
    command: Command,
    read_frame: Callable[[], Frame],
    project: Project,
    claim: Callable[[], Any],
    verify_producer: Callable[[], None],
    source_archive: Path | None = None,
    read_session_scope: Callable[[], AbstractContextManager[Any]] | None = None,
    prefix_actors: Sequence[Any] | None = None,
    root_selector: Callable[
        [Iterator[tuple[int, ConfidenceAwareActorObservation]]], RootSelection
    ]
    | None = None,
) -> dict[str, Any]:
    """Claim before creating output or configuring; record every terminal failure.

    The concrete CLI supplies the ownership ledger, pinned native transport and
    strict public adapter. Dependency injection permits offline scheduling tests.
    Once claimed, an episode is never reconfigured or retried by this function.

    Tier A uses the defaults: scripted prefix controllers from
    ``root.prefix_styles`` with the declared owner reserve, and ``select_root``.
    Tier B passes two ``prefix_actors`` (each with ``select_action(packet)``,
    e.g. the frozen policy or a scripted evaluation opponent) and its own
    ``root_selector``; no reserve is applied to supplied actors.
    """
    if (prefix_actors is None) != (root_selector is None):
        raise ValueError("prefix actors and root selector are supplied together")
    if prefix_actors is not None and len(prefix_actors) != 2:
        raise ValueError("one prefix actor per seat is required")
    verify_producer()
    claim()  # Irreversible ownership claim precedes mkdir and native mutation.
    output.mkdir(parents=True, exist_ok=False)
    if source_archive is not None:
        shutil.copyfile(source_archive, output / "producer-source.zip")
    loader: CardDataLoader = builder.loader
    (output / "gamedata.json").write_bytes(loader.data_file.read_bytes())
    _write(
        output / "plan.json",
        {
            "schema": "readiness-v2-root-prefix-plan-v1",
            "role": "development" if role == "opened_development" else "acceptance",
            "evidence_role": role,
            "config": config,
            "root_request": root.model_dump(mode="json"),
            "decks": root.decks,
            "decision_stride": 5,
            "command_delay": 1,
            "startup_wait_ticks": 90,
            "game_complete": False,
            "public_contract_version": 4 if builder.public_hand_levels else 3,
        },
    )
    space = DiscreteTileActionSpace()
    masks = PublicActionMaskBuilder(builder)
    prefix_controllers = (
        list(prefix_actors)
        if prefix_actors is not None
        else [
            PublicScriptedOpponent(builder, style=style)
            for style in root.prefix_styles
        ]
    )
    root_controller = (
        None
        if root_selector is not None
        else PublicScriptedOpponent(builder, style="balanced")
    )
    history: list[AcceptedOwnPlay | None] = [None, None]
    observations: list[list[Any]] = [[], []]
    packet_ticks: list[int] = []
    commands: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    last_frame: Frame | None = None
    selection: RootSelection | None = None
    failure: dict[str, str] | None = None
    unchanged = False
    configured = False
    try:
        command("configure " + json.dumps(config, separators=(",", ":")))
        configured = True
        with nullcontext() if read_session_scope is None else read_session_scope():
            initial = command("observe")
            if initial.get("tick") != 0 or initial.get("truncated") is not False:
                raise ValueError(
                    "configuration did not produce a complete tick-zero state"
                )
            _write(output / "initial.json", initial)
            for owner, deck in enumerate(root.decks):
                player = next(p for p in initial["players"] if p["owner"] == owner)
                observed = sorted(player["deck"], key=lambda card: card["deckSlot"])
                expected = []
                for name in deck:
                    stats = loader.get_card(name)
                    if stats is None:
                        raise ValueError("declared deck card absent from pinned loader")
                    expected.append(stats._raw_entry["id"])
                if [card["cardId"] for card in observed] != expected:
                    raise ValueError(
                        "native initial deck differs from the declared ordered deck"
                    )
                if any(card["commandCardId"] != card["cardId"] for card in observed):
                    raise ValueError(
                        "native initial deck does not expose base command identities"
                    )
            command("step 90")
            with (
                gzip.open(output / "native-frames.jsonl.gz", "xt") as frames,
                (output / "submissions.jsonl").open("x") as submissions,
                (output / "accepted-commands.jsonl").open("x") as accepted_log,
                gzip.open(output / "transport.jsonl.gz", "xt") as transport,
            ):

                def packets() -> Iterator[tuple[int, ConfidenceAwareActorObservation]]:
                    nonlocal last_frame
                    expected_tick = 90
                    while expected_tick <= root.stop_tick:
                        frame = read_frame()
                        before = frame["ordinary"]
                        if before["tick"] != expected_tick:
                            raise ValueError(
                                f"expected native tick {expected_tick}, got {before['tick']}"
                            )
                        stored_frame = compact_native_frame(frame)
                        frames.write(
                            json.dumps(stored_frame, separators=(",", ":")) + "\n"
                        )
                        frames.flush()
                        last_frame = stored_frame
                        views = project(frame, history)
                        if len(views) != 2:
                            raise ValueError("both public perspectives are required")
                        packet_ticks.append(expected_tick)
                        for owner, view in enumerate(views):
                            view.validate()
                            observations[owner].append(view)
                        if expected_tick >= root.start_tick:
                            # select_root stops iteration before prefix actions at the selected root.
                            yield expected_tick, views[root.root_owner]
                        elif before["ended"]:
                            raise ValueError(
                                "native game ended before the declared root window"
                            )
                        if expected_tick == root.stop_tick:
                            return
                        selected = []
                        transport_selected: list[dict[str, Any]] = []
                        submitted_commands = []
                        for owner, view in enumerate(views):
                            mask = masks.build(
                                PublicActionMaskInput.from_confidence_observation(view)
                            )
                            ordinary_action = prefix_controllers[owner].select_action(
                                view
                            )
                            action = (
                                ordinary_action
                                if prefix_actors is not None
                                else apply_prefix_owner_reserve(
                                    root, owner, view, ordinary_action
                                )
                            )
                            if not mask[action]:
                                raise ValueError(
                                    "prefix controller selected an illegal public action"
                                )
                            decoded = space.decode_action(action, owner)
                            decision = {
                                "owner": owner,
                                "observation_tick": expected_tick,
                                "action": action,
                                "ordinary_action": ordinary_action,
                                "prefix_reserve_applied": action != ordinary_action,
                                "public_packet_sha256": packet_sha(view),
                            }
                            decisions.append(decision)
                            if decoded.is_no_op:
                                decision["accepted"] = None
                                transport_selected.append(
                                    {
                                        "owner": owner,
                                        "action": action,
                                        "name": None,
                                        "cost": None,
                                        "xy": None,
                                    }
                                )
                                continue
                            if decoded.position is None or decoded.slot is None:
                                raise ValueError(
                                    "prefix scope supports card placements and wait only"
                                )
                            name = builder.card_name_for_token_id(
                                int(view.observation.hand_ids[decoded.slot])
                            )
                            if name is None:
                                raise ValueError(
                                    "public hand token has no card identity"
                                )
                            stats = loader.get_card(name)
                            if stats is None:
                                raise ValueError(
                                    "prefix card identity absent from pinned loader"
                                )
                            native_id = stats._raw_entry["id"]
                            hud = next(
                                p for p in before["players"] if p["owner"] == owner
                            )
                            hand = next(
                                c for c in hud["hand"] if c["handIndex"] == decoded.slot
                            )
                            if hand["cardId"] != native_id:
                                raise ValueError(
                                    "public chosen slot disagrees with native HUD identity"
                                )
                            x, y = (
                                round(decoded.position.x * 1000),
                                round(decoded.position.y * 1000),
                            )
                            submitted_command = f"replay-schedule-card {owner} {native_id} {x} {y} {expected_tick + 1}"
                            receipt = command(submitted_command)
                            submitted_commands.append(submitted_command)
                            transport_selected.append(
                                {
                                    "owner": owner,
                                    "action": action,
                                    "name": name,
                                    "cost": hand["cost"],
                                    "xy": [decoded.position.x, decoded.position.y],
                                }
                            )
                            submission = {
                                "owner": owner,
                                "name": name,
                                "action": action,
                                "native_card_id": native_id,
                                "native_xy": [x, y],
                                "xy": [decoded.position.x, decoded.position.y],
                                "cost": hand["cost"],
                                "submitted_tick": expected_tick,
                                "scheduled_execution_tick": expected_tick + 1,
                                "schedule_receipt": receipt,
                                "submitted_command": submitted_command,
                            }
                            submissions.write(json.dumps(submission) + "\n")
                            submissions.flush()
                            selected.append((decision, submission))
                        command("step 1")
                        after = command("observe")

                        def compact(snapshot: Frame) -> Frame:
                            return {
                                **{
                                    key: snapshot[key]
                                    for key in ("tick", "generation", "stateEpoch")
                                },
                                "players": [
                                    {
                                        key: player[key]
                                        for key in ("owner", "elixirRaw", "hand")
                                    }
                                    for player in snapshot["players"]
                                ],
                            }

                        receipts = [s["schedule_receipt"] for _, s in selected]
                        transport.write(
                            json.dumps(
                                {
                                    "tick": expected_tick,
                                    "selected": transport_selected,
                                    "receipts": receipts,
                                    "commands": submitted_commands,
                                    "before": compact(before),
                                    "after": compact(after),
                                }
                            )
                            + "\n"
                        )
                        transport.flush()
                        validate_command_step(before, after, receipts)
                        rejected = False
                        for decision, submission in selected:
                            owner = submission["owner"]
                            old = next(
                                p for p in before["players"] if p["owner"] == owner
                            )
                            new = next(
                                p for p in after["players"] if p["owner"] == owner
                            )
                            delta = (old["elixirRaw"] - new["elixirRaw"]) / 10000
                            accepted = delta >= submission["cost"] - 0.1
                            record = {
                                **submission,
                                "execution_tick": after["tick"],
                                "native_spend_delta": delta,
                                "native_acceptance_spend_evidence": accepted,
                            }
                            commands.append(record)
                            decision["accepted"] = accepted
                            if accepted:
                                history[owner] = AcceptedOwnPlay(
                                    submission["name"], submission["cost"]
                                )
                                accepted_log.write(json.dumps(record) + "\n")
                                accepted_log.flush()
                            else:
                                rejected = True
                        if rejected:
                            raise ValueError(
                                "prefix command lacked native acceptance; no fallback"
                            )
                        expected_tick += 5
                        command(f"step {expected_tick - after['tick']}")

                if root_selector is not None:
                    selection = root_selector(packets())
                else:
                    assert root_controller is not None
                    selection = select_root(root, root_controller, packets())
            if selection.status == "selected":
                _write(output / "root-frame.json", last_frame)
        verify_producer()
        unchanged = True
    except (
        ValueError,
        AssertionError,
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        StopIteration,
    ) as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        # Preserve public trajectories even when later transport or legality fails.
        for owner in (0, 1):
            if observations[owner]:
                try:
                    PublicPolicySequence.from_observations(
                        builder, observations[owner]
                    ).save(output / f"seat{owner}-public.npz")
                except (ValueError, OSError, TypeError) as exc:
                    failure = {
                        "type": type(exc).__name__,
                        "message": "public archive: " + str(exc),
                    }
        _write(output / "packet-ticks.json", packet_ticks)
        _write(output / "decisions.json", decisions)
    status = "failed"
    if failure is None and selection is not None:
        status = (
            selection.status
            if selection.status in ("selected", "no_eligible_root")
            else "failed"
        )
    result = {
        "schema": "readiness-v2-root-prefix-result-v1",
        "status": status,
        "evidence_role": role,
        "family_id": root.family_id,
        "source_episode_id": root.source_episode_id,
        "configured": configured,
        "prefix_complete": status in ("selected", "no_eligible_root"),
        "game_complete": False,
        "commands": commands,
        "packet_ticks": packet_ticks,
        "selection": None if selection is None else selection.model_dump(mode="json"),
        "failure": failure,
        "producer_sources_unchanged": unchanged,
    }
    _write(output / "result.json", result)
    return result
