"""Run the four declared native level probes on one already-running reference.

For each probe this configures the declared config, records a verified-session
coverage game (tick-zero Crowns, body checks, spell checks) in the exact raw
form ``verify_level_extension_receipt`` re-audits, then executes the declared
native ranking branches (two public alternatives x two reacting conditions).

It never starts or restarts an emulator, never writes a readiness ledger and
never retries a probe or branch. Failures are retained on disk. Run it from the
admitted runtime snapshot (``CLASHER_ROOT``/``PYTHONPATH``) with ``-B``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))
import level_extension_common as common  # noqa: E402

common.prefer_runtime_scripts()  # runtime native helpers before workspace scripts

import argparse  # noqa: E402
import fcntl  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from contextlib import ExitStack, contextmanager  # noqa: E402

from clasher.data import CardDataLoader  # noqa: E402
from clasher.rl.native_command_checks import validate_command_step  # noqa: E402
from clasher.rl.native_public_observation import (  # noqa: E402
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.own_card_history import AcceptedOwnPlay  # noqa: E402
from clasher.rl.public_action_mask import (  # noqa: E402
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_reference_checks import reference_token_maps  # noqa: E402
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent  # noqa: E402
from clasher.rl.readiness_execution import condition_styles, packet_sha  # noqa: E402
from clasher.rl.readiness_level_extension import (  # noqa: E402
    PROBE_PLANS,
    LevelExtensionDeclaration,
    configure_native_levels,
)
from clasher.rl.readiness_transport import compact_transport_snapshot  # noqa: E402

SCHEMA = "readiness-level-probe-collection-v1"


class ProbeFailure(RuntimeError):
    """A probe-local failure; later probes still run and nothing is retried."""


def load_declared_probes(declaration_path: Path, manifest_path: Path):
    """Bind each prospective config file to the (already frozen) declaration."""
    declaration = LevelExtensionDeclaration.model_validate_json(declaration_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "readiness-level-probe-configs-v1":
        raise ValueError("unexpected level probe config manifest")
    if manifest.get("gamedata_sha256") != declaration.gamedata_sha256:
        raise ValueError("probe configs were generated for another ruleset")
    probes = []
    for index, (row, declared, plan) in enumerate(
        zip(manifest["probes"], declaration.probes, PROBE_PLANS, strict=True)
    ):
        path = (manifest_path.parent / row["config_path"]).resolve()
        config = json.loads(path.read_text())
        if (
            common.canonical_sha(config) != declared.config_sha256
            or row["config_sha256"] != declared.config_sha256
            or common.file_sha(path) != row["config_file_sha256"]
            or declared.plan != plan
            or configure_native_levels(config, plan) != config
        ):
            raise ValueError(f"probe {index} config differs from the declaration")
        probes.append({"index": index, "plan": plan, "config": config, "config_path": path,
                       "config_sha256": declared.config_sha256})
    return declaration, probes


class NativeLink:
    """Probe command transport plus the frame-read protocol of the Tier A runner."""

    def __init__(self, call, session_factory, fast: bool):
        self.call = call
        self.session_factory = session_factory
        self.fast = fast
        self.session = None

    def observe(self):
        return self.call("observe")

    def read_frame(self):
        if self.session is None:
            raise ValueError("native frame read requires one open verified session")
        before = self.call("observe")
        if self.fast:
            rich = self.call("observe-rich")
            levels = self.session.read_levels(ordinary=before)
        else:
            levels = self.session.read_levels()
            rich = self.call("observe-rich")
            if self.call("observe") != before:
                raise ValueError("native frame changed across level/rich reads")
        if levels["ordinary"] != before:
            raise ValueError("native level evidence belongs to another frame")
        # The reader keys levels by integer object ID; keep the in-memory frame
        # identical to its stored (JSON) form so every check sees what is saved.
        levels = {**levels, "levels": common.serialized_level_map(levels["levels"])}
        return {"ordinary": before, "rich": rich, "level_source": levels}

    def advance(self, current_tick: int, target: int) -> None:
        if target < current_tick:
            raise ValueError("native schedule moved backwards")
        if target > current_tick:
            stepped = self.call(f"step {target - current_tick}")
            if not stepped.get("ended") and stepped.get("tick") not in (None, target):
                raise ValueError("native step did not reach its target tick")

    @contextmanager
    def verified_session(self, output: Path):
        session = self.session_factory()
        try:
            with session as opened:
                self.session = opened
                yield opened
        finally:
            self.session = None
            provenance = session.provenance
            common.write_new(output, provenance)
        if provenance.get("status") != "verified":
            raise ProbeFailure("native read session did not close verified")


def submit_step(link, loader, before, selected, transport, history):
    """Schedule, execute exactly one tick, audit and record one transport row."""
    receipts, commands = [], []
    for choice in selected:
        if choice["name"] is None:
            continue
        native_id = loader.get_card(choice["name"])._raw_entry["id"]
        command = (
            f"replay-schedule-card {choice['owner']} {native_id} "
            f"{round(choice['xy'][0] * 1000)} {round(choice['xy'][1] * 1000)} {before['tick'] + 1}"
        )
        receipts.append(link.call(command))
        commands.append(command)
    link.advance(before["tick"], before["tick"] + 1)
    after = link.observe()
    transport.write({
        "tick": before["tick"],
        "selected": selected,
        "receipts": receipts,
        "commands": commands,
        "before": compact_transport_snapshot(before),
        "after": compact_transport_snapshot(after),
    })
    validate_command_step(before, after, receipts)
    accepted = []
    for choice in selected:
        if choice["name"] is None:
            continue
        old = next(p for p in before["players"] if p["owner"] == choice["owner"])
        new = next(p for p in after["players"] if p["owner"] == choice["owner"])
        if (old["elixirRaw"] - new["elixirRaw"]) / 10000 < choice["cost"] - 0.1:
            raise ProbeFailure("native command lacked spend evidence; no fallback")
        history[choice["owner"]] = AcceptedOwnPlay(choice["name"], choice["cost"])
        accepted.append({
            "owner": choice["owner"], "name": choice["name"], "action": choice["action"],
            "xy": choice["xy"], "cost": choice["cost"], "submitted_tick": before["tick"],
            "execution_tick": after["tick"], "native_card_id": loader.get_card(choice["name"])._raw_entry["id"],
        })
    return after, accepted


def selection(owner, action, view, builder, space, ordinary):
    """Public-legal transport choice (hand slot identity and HUD cost)."""
    decoded = space.decode_action(action, owner)
    if decoded.is_no_op:
        return {"owner": owner, "action": action, "name": None, "cost": None, "xy": None}
    name = builder.card_name_for_token_id(int(view.observation.hand_ids[decoded.slot]))
    hud = next(p for p in ordinary["players"] if p["owner"] == owner)
    hand = [c for c in hud["hand"] if c["handIndex"] == decoded.slot]
    if name is None or len(hand) != 1 or hand[0]["cardId"] != builder.loader.get_card(name)._raw_entry["id"]:
        raise ProbeFailure("public hand slot disagrees with the native HUD")
    return {"owner": owner, "action": action, "name": name, "cost": hand[0]["cost"],
            "xy": [decoded.position.x, decoded.position.y]}


class Collector:
    def __init__(self, *, loader, catalog, gamedata_sha256, link, output, root_tick,
                 max_tick, public_views):
        self.loader = loader
        self.builder = public_reference_builder(
            loader, catalog, card_semantics_version=4, public_contract_version=4
        )
        self.adapter = NativePublicObservationAdapter(
            self.builder,
            NativePublicScope("15.535.86", gamedata_sha256),
            card_names=tuple(PUBLIC_REFERENCE_CARDS),
            projectile_catalog=catalog,
        )
        self.maps = reference_token_maps(self.builder, PUBLIC_REFERENCE_CARDS, catalog)
        self.masks = PublicActionMaskBuilder(self.builder)
        self.space = common.DiscreteTileActionSpace()
        self.link = link
        self.output = output
        self.root_tick = root_tick
        self.max_tick = max_tick
        self.public_views = public_views

    def views(self, frame, plan, history):
        return common.native_level_views(
            frame, plan, self.adapter, self.maps, history, self.loader, self.builder, self.public_views
        )

    def mask(self, view):
        return self.masks.build(PublicActionMaskInput.from_confidence_observation(view))

    def configure(self, config):
        self.link.call("configure " + json.dumps(config, separators=(",", ":")))
        initial = self.link.observe()
        if initial.get("tick") != 0 or initial.get("truncated") is not False:
            raise ProbeFailure("configuration did not produce a complete tick-zero state")
        for owner in (0, 1):
            player = next(p for p in initial["players"] if p["owner"] == owner)
            observed = [c["cardId"] for c in sorted(player["deck"], key=lambda c: c["deckSlot"])]
            if observed != [c["d"] for c in config["battle"][f"deck{owner}"]["sp"]]:
                raise ProbeFailure("native deck differs from the declared probe deck")
        return initial

    # ------------------------------------------------------- coverage game

    def coverage_game(self, probe, out: Path) -> dict:
        plan, config = probe["plan"], probe["config"]
        initial = self.configure(config)
        common.write_new(out / "initial.json", initial)
        driver = common.CoverageDriver(
            self.loader, attacker=common.attacker_for_probe(probe["index"]), card_level=plan.card_level
        )
        history = [None, None]
        accepted_log = []
        root = None
        status = "incomplete_coverage"
        with ExitStack() as stack:
            stack.enter_context(self.link.verified_session(out / "read-session.json"))
            frames = stack.enter_context(common.JsonlWriter(out / "frames.jsonl.gz"))
            decisions = stack.enter_context(common.JsonlWriter(out / "decisions.jsonl.gz"))
            transport = stack.enter_context(common.JsonlWriter(out / "transport.jsonl.gz"))
            first = self.link.read_frame()
            if first["ordinary"]["tick"] != 0:
                raise ProbeFailure("first probe frame must be the tick-zero Crown observation")
            common.check_native_levels(first, plan, self.loader)
            frames.write(first)
            self.link.advance(0, 90)
            tick = 90
            while True:
                frame = self.link.read_frame()
                ordinary = frame["ordinary"]
                if ordinary["tick"] != tick:
                    raise ProbeFailure(f"expected native tick {tick}, got {ordinary['tick']}")
                combat = frame["rich"].get("combatEvents") or {}
                if combat.get("complete") is not True or combat.get("hookSetAttested") is not True:
                    raise ProbeFailure("native combat telemetry is incomplete or unattested")
                frames.write(frame)
                driver.observe(frame)
                views = self.views(frame, plan, history)
                if root is None and tick >= self.root_tick:
                    root = self.try_ranking_root(probe, frame, views, accepted_log, out)
                if driver.complete() and root is not None:
                    status = "coverage_complete"
                    break
                if ordinary["ended"] or tick >= self.max_tick:
                    break
                selected, intents = [], []
                for owner, view in enumerate(views):
                    mask = self.mask(view)
                    action, intent = driver.choose(
                        owner, ordinary, mask,
                        keep_cycling=root is None and owner == common.ranking_root_owner(probe["index"]),
                    )
                    if not mask[action]:
                        raise ProbeFailure("coverage driver chose an illegal public action")
                    selected.append(selection(owner, action, view, self.builder, self.space, ordinary))
                    intents.append(intent)
                decisions.write({
                    "tick": tick,
                    "native_frame": {"ordinary": ordinary},
                    "actions": [s["action"] for s in selected],
                    "public_sha256": [packet_sha(v) for v in views],
                    "driver_intents": intents,
                })
                after, accepted = submit_step(self.link, self.loader, ordinary, selected, transport, history)
                for row in accepted:
                    accepted_log.append(row)
                    driver.pending.setdefault((row["owner"], row["name"]), row["submitted_tick"])
                self.link.advance(after["tick"], tick + 5)
                tick += 5
        if root is None:
            root = self.freeze_root(probe, None, None, accepted_log, out,
                                    failure="no eligible ranking root before the probe ended")
        common.write_new(out / "accepted-commands.json", accepted_log)
        coverage = driver.coverage()
        common.write_new(out / "coverage.json", coverage)
        return {"status": status, "coverage": coverage, "root": root, "final_tick": tick}

    def try_ranking_root(self, probe, frame, views, accepted_log, out):
        """Freeze the first eligible root, its prefix and both alternatives."""
        owner = common.ranking_root_owner(probe["index"])
        try:
            candidates = common.ranking_candidates(self.builder, views[owner])
        except ValueError:
            return None
        return self.freeze_root(probe, frame, views[owner], accepted_log, out, candidates=candidates)

    def freeze_root(self, probe, frame, view, accepted_log, out, *, candidates=None, failure=None):
        root = {
            "schema": "readiness-level-ranking-root-v1",
            "probe": probe["index"],
            "config_sha256": probe["config_sha256"],
            "root_min_tick": self.root_tick,
            "root_rule": "first five-tick boundary at/after root_min_tick with both declared alternatives",
            "root_tick": None if frame is None else frame["ordinary"]["tick"],
            "root_owner": common.ranking_root_owner(probe["index"]),
            "root_ordinary_sha256": None if frame is None else common.canonical_sha(frame["ordinary"]),
            "root_public_packet_sha256": None if view is None else packet_sha(view),
            "prefix_commands": [dict(c) for c in accepted_log],
            "roles": list(common.RANKING_ROLES),
            "candidates": candidates,
            "conditions": list(common.RANKING_CONDITIONS),
            "failure": failure,
        }
        common.write_new(out / "ranking-root.json", root)
        return root

    # ------------------------------------------------------ ranking branch

    def native_branch(self, probe, root, root_ordinary, condition_index, candidate, out: Path) -> dict:
        plan, config = probe["plan"], probe["config"]
        out.mkdir()
        root_tick, owner = root["root_tick"], root["root_owner"]
        self.configure(config)
        tick = 0
        for command in root["prefix_commands"]:
            self.link.advance(tick, command["submitted_tick"])
            tick = command["submitted_tick"]
            self.link.call(
                f"replay-schedule-card {command['owner']} {command['native_card_id']} "
                f"{round(command['xy'][0] * 1000)} {round(command['xy'][1] * 1000)} {tick + 1}"
            )
        self.link.advance(tick, root_tick)
        current = self.link.observe()
        if any(current[k] != root_ordinary[k] for k in ("objects", "players", "tick", "ended", "winner")):
            raise ProbeFailure("native replay did not reproduce the frozen ranking root")
        history = [None, None]
        for command in root["prefix_commands"]:
            history[command["owner"]] = AcceptedOwnPlay(command["name"], command["cost"])
        styles = condition_styles(common.RANKING_CONDITIONS[condition_index], owner)
        controllers = [PublicScriptedOpponent(self.builder, style=style) for style in styles]
        legal = True
        with ExitStack() as stack:
            stack.enter_context(self.link.verified_session(out / "read-session.json"))
            decisions = stack.enter_context(common.JsonlWriter(out / "decisions.jsonl.gz"))
            transport = stack.enter_context(common.JsonlWriter(out / "transport.jsonl.gz"))
            tick = root_tick
            for boundary in range(root_tick, root_tick + common.HORIZON_TICKS, 5):
                self.link.advance(tick, boundary)
                frame = self.link.read_frame()
                ordinary = frame["ordinary"]
                if ordinary["tick"] != boundary or ordinary["ended"]:
                    raise ProbeFailure("ranking branch ended or skipped a decision interval")
                views = self.views(frame, plan, history)
                if boundary == root_tick and packet_sha(views[owner]) != root["root_public_packet_sha256"]:
                    raise ProbeFailure("native root public packet differs from the frozen root")
                selected = []
                for seat, view in enumerate(views):
                    action = (
                        candidate["action_id"] if boundary == root_tick and seat == owner
                        else controllers[seat].select_action(view)
                    )
                    if not self.mask(view)[action]:
                        legal = False
                        raise ProbeFailure("declared ranking action is not public-legal")
                    choice = selection(seat, action, view, self.builder, self.space, ordinary)
                    if boundary == root_tick and seat == owner and int(
                        view.observation.hand_ids[action // 576]
                    ) != candidate["card_token"]:
                        raise ProbeFailure("root hand slot differs from the frozen candidate")
                    selected.append(choice)
                decisions.write({
                    "tick": boundary,
                    "native_frame": {"ordinary": ordinary},
                    "actions": [s["action"] for s in selected],
                    "public_sha256": [packet_sha(v) for v in views],
                })
                after, _accepted = submit_step(self.link, self.loader, ordinary, selected, transport, history)
                tick = after["tick"]
            self.link.advance(tick, root_tick + common.HORIZON_TICKS)
            ending = self.link.observe()
        if ending["tick"] != root_tick + common.HORIZON_TICKS:
            raise ProbeFailure("ranking branch did not reach its declared horizon")
        raw = common.write_new(out / "ending-raw.json", {"ordinary": ending})
        crowns = common.write_new(out / "ending-frame.json",
                                  common.crown_projection_record(ending, Path(raw["path"])))
        return {
            "probe": probe["index"],
            "condition": condition_index,
            "candidate": candidate["candidate"],
            "engine": "reference",
            "root_tick": root_tick,
            "root_owner": owner,
            "public_legal": legal,
            "config_sha256": probe["config_sha256"],
            "role": candidate["role"],
            "action_id": candidate["action_id"],
            "ending_frame": crowns,
            "artifacts": {
                name: common.pin(out / name)
                for name in ("decisions.jsonl.gz", "transport.jsonl.gz", "read-session.json", "ending-raw.json")
            },
        }


def run(args, *, call, session_factory, public_views, catalog, fast):
    declaration, probes = load_declared_probes(args.declaration, args.configs_manifest)
    if common.file_sha(args.gamedata) != declaration.gamedata_sha256:
        raise ValueError("gamedata differs from the declaration")
    attest = call("attest")
    if common.canonical_sha(attest) != declaration.native_attestation_sha256:
        raise ValueError("live native attestation differs from the declaration")
    status = call("status")
    if status.get("ready") is not True or status.get("paused") is not True:
        raise ValueError("native reference must already be ready and paused")
    loader = CardDataLoader(args.gamedata)
    args.output.mkdir(parents=True, exist_ok=False)
    link = NativeLink(call, session_factory, fast)
    collector = Collector(
        loader=loader, catalog=catalog, gamedata_sha256=declaration.gamedata_sha256, link=link,
        output=args.output, root_tick=args.ranking_root_tick, max_tick=args.max_probe_tick,
        public_views=public_views,
    )
    tool_files = [Path(__file__).resolve(), Path(common.__file__).resolve()]
    pins_before = common.source_pins(common.runtime_source_files(tool_files))
    manifest = {
        "schema": SCHEMA,
        "tooling_schema": common.TOOL_SCHEMA,
        "declaration": common.pin(args.declaration),
        "configs_manifest": common.pin(args.configs_manifest),
        "gamedata": common.pin(args.gamedata),
        "native_attestation_sha256": declaration.native_attestation_sha256,
        "catalog_sha256": catalog.sha256,
        "ranking_root_tick": args.ranking_root_tick,
        "max_probe_tick": args.max_probe_tick,
        "ranking_roles": list(common.RANKING_ROLES),
        "ranking_conditions": list(common.RANKING_CONDITIONS),
        "native_path": "fast" if fast else "legacy",
        "port": getattr(args, "port", None),
        "serial": getattr(args, "serial", None),
        "runtime": common.runtime_identity(),
        "source_pins": pins_before,
        "started_at": time.time(),
        "probes": [],
        "game_complete": False,
        "training_permission": None,
    }
    common.write_new(args.output / "collection-plan.json", {k: v for k, v in manifest.items() if k != "probes"})
    ranking_rows, failures = [], []
    for probe in probes:
        out = args.output / f"probe-{probe['index']}"
        out.mkdir()
        record = {"probe": probe["index"], "plan": probe["plan"].model_dump(mode="json"),
                  "config": common.pin(probe["config_path"]), "output": str(out.resolve())}
        try:
            game = collector.coverage_game(probe, out)
            record.update(status=game["status"], coverage=game["coverage"], final_tick=game["final_tick"])
            record["raw"] = {
                name: common.pin(out / name)
                for name in ("frames.jsonl.gz", "read-session.json", "decisions.jsonl.gz", "transport.jsonl.gz")
            }
        except Exception as error:  # retained, never retried
            record.update(status="failed", failure=f"{type(error).__name__}: {error}",
                          traceback=traceback.format_exc())
            manifest["probes"].append(record)
            failures.append(record)
            continue
        root = game["root"]
        record["ranking_root"] = common.pin(out / "ranking-root.json") if root else None
        record["branches"] = []
        if root is None or root["candidates"] is None:
            record["ranking_failure"] = None if root is None else root["failure"]
            manifest["probes"].append(record)
            failures.append(record)
            continue
        root_frame = next(
            f for f in common.read_jsonl(out / "frames.jsonl.gz") if f["ordinary"]["tick"] == root["root_tick"]
        )["ordinary"]
        for condition_index in range(len(common.RANKING_CONDITIONS)):
            for candidate in root["candidates"]:
                branch_dir = out / f"ranking-c{condition_index}-a{candidate['candidate']}"
                try:
                    row = collector.native_branch(probe, root, root_frame, condition_index, candidate, branch_dir)
                except Exception as error:
                    branch_failure = {"condition": condition_index, "candidate": candidate["candidate"],
                                      "failure": f"{type(error).__name__}: {error}",
                                      "traceback": traceback.format_exc()}
                    record["branches"].append(branch_failure)
                    failures.append({"probe": probe["index"], **branch_failure})
                    continue
                ranking_rows.append(row)
                record["branches"].append({"condition": condition_index, "candidate": candidate["candidate"],
                                           "status": "completed"})
        manifest["probes"].append(record)
    common.write_new(args.output / "native-rankings.json", {
        "schema": "readiness-level-native-rankings-v1",
        "declaration_sha256": common.file_sha(args.declaration),
        "horizon_ticks": common.HORIZON_TICKS,
        "conditions": list(common.RANKING_CONDITIONS),
        "branches": ranking_rows,
    })
    pins_after = common.source_pins(common.runtime_source_files(tool_files))
    manifest["producer_sources_unchanged"] = pins_after == pins_before
    manifest["ended_at"] = time.time()
    manifest["failures"] = len(failures)
    common.write_new(args.output / "collection-result.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--configs-manifest", type=Path, required=True)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-lock", type=Path, required=True)
    parser.add_argument("--native-path", choices=("fast", "legacy"), default="fast")
    parser.add_argument("--ranking-root-tick", type=int, default=common.DEFAULT_RANKING_ROOT_TICK)
    parser.add_argument("--max-probe-tick", type=int, default=common.DEFAULT_MAX_PROBE_TICK)
    parser.add_argument("--allow-workspace-runtime", action="store_true")
    args = parser.parse_args()
    if args.ranking_root_tick < 90 or args.ranking_root_tick % 5:
        parser.error("ranking root must be a five-tick boundary at or after tick 90")

    from read_native_public_levels import VerifiedNativeReadSession
    from run_readiness_v2 import public_views
    from smoke_reference_battle import request

    from clasher.rl.native_probe_transport import PersistentProbeSession

    common.require_runtime_root(args.allow_workspace_runtime)
    catalog = NativeProjectileCatalog.from_csv(args.catalog, expected_sha256=args.catalog_sha256)
    declaration = LevelExtensionDeclaration.model_validate_json(args.declaration.read_text())
    fast = args.native_path == "fast"
    args.native_lock.parent.mkdir(parents=True, exist_ok=True)
    with args.native_lock.open("a") as lock, ExitStack() as stack:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(f"native device lock is held: {args.native_lock}")
        if fast:
            transport = stack.enter_context(PersistentProbeSession(args.port))
            call = transport
        else:
            def call(command):
                return request(args.port, command)

        def session_factory():
            return VerifiedNativeReadSession(
                args.adb, port=args.port, serial=args.serial,
                expected_attestation_sha256=declaration.native_attestation_sha256,
                probe=call if fast else None, combined_identity_reads=fast,
            )

        result = run(args, call=call, session_factory=session_factory, public_views=public_views,
                     catalog=catalog, fast=fast)
    print(json.dumps({
        "probes": [{"probe": p["probe"], "status": p["status"]} for p in result["probes"]],
        "failures": result["failures"],
        "producer_sources_unchanged": result["producer_sources_unchanged"],
    }))
    raise SystemExit(0 if result["failures"] == 0 and result["producer_sources_unchanged"] else 1)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main()
