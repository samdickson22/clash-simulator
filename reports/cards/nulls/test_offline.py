"""Synthetic/offline checks only. Forbid native sockets throughout the suite."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2])]
import adjudicate as A
import capture as C
import scenarios as S
import mac_exec
from bot.fidelity.fixture import load_fixture, load_split

JOB = Path("/mpac/sdicks02/jobs/clasher/cards/nulls/offline-checks")


def metric(value, kind="mechanics", field="first_hit_after_ready", multiset=False):
    return {"value": value, "classification": kind, "field": field, "unit": "ticks",
            "multiset": multiset, "evidence": "synthetic test, never native evidence"}


def arms(values=(16, 17, 16), kind="mechanics", field="first_hit_after_ready", multiset=False):
    return {name: {"arm": name, "scenario_id": "synthetic", "script_sha256": "synthetic-script",
                   "replay_sha256": "synthetic-replay", "native_version": S.VERSION,
                   "provenance": "synthetic test only", "observables": {"event": metric(value, kind, field, multiset)}}
            for name, value in zip(("native", "ours", "rsim"), values)}


class Tests(unittest.TestCase):
    def setUp(self):
        self.socket_guard = patch("socket.create_connection", side_effect=AssertionError("native I/O forbidden"))
        self.socket_guard.start()
        JOB.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-", dir=JOB)
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.socket_guard.stop()
        self.temp.cleanup()

    def test_manifest_coverage_horizon_hands(self):
        rows = S.scenarios()
        self.assertEqual(len(rows), 106)
        self.assertEqual({r["card"] for r in rows}, set(S.A + S.B + ["Wizard"]))
        self.assertEqual(len({r["id"] for r in rows}), len(rows))
        self.assertEqual({(r["card"], r["variant"]) for r in rows if r["priority"] == 0 and r["card"] != "Wizard"}, S.RESIDUALS)
        for row in rows:
            script = row["script"]
            self.assertEqual(row["native_version"], S.VERSION)
            self.assertLessEqual(script["end_tick"], 600)
            self.assertEqual(row["script_sha256"], S.signature(script))
            for side in (0, 1):
                deck = script["decks"][side]
                self.assertEqual(len(set(deck)), 8)
                needed = {c["card"] for c in script["commands"] if c["side"] == side}
                self.assertLessEqual(len(needed), 4)
                self.assertTrue(needed <= set(deck))
            for c in script["commands"]:
                self.assertEqual(c["schedule_tick"], c["command_tick"] + 1)
                self.assertTrue(script["start_tick"] <= c["command_tick"] < script["end_tick"])

    def test_residual_scripts_match_existing_command_geometry(self):
        for row in S.scenarios():
            if (row["card"], row["variant"]) in S.RESIDUALS:
                self.assertEqual(row["script"]["commands"], S.script(row["card"], row["variant"]))
                self.assertEqual(row["script"]["start_tick"], 100)

    def test_expensive_variants_refill_without_forcing(self):
        rows = {r["id"]: r for r in S.scenarios()}
        self.assertEqual(rows["ThreeMusketeers.alone"]["script"]["start_tick"], 220)
        self.assertEqual(rows["GiantBuffer.enchant_support"]["script"]["start_tick"], 300)

    def test_one_tick_residual_is_not_tolerated(self):
        self.assertEqual(A.adjudicate(arms())["observables"][0]["verdict"], "MECHANICS_SUPPORTS_ROYALESIM")

    def test_supports_ours_and_neither(self):
        for values, expected in [((17, 17, 16), "MECHANICS_SUPPORTS_OURS"),
                                 ((18, 17, 16), "MECHANICS_NEITHER_MATCHES_NATIVE")]:
            self.assertEqual(A.adjudicate(arms(values))["observables"][0]["verdict"], expected)

    def test_direct_stat_difference(self):
        result = A.adjudicate(arms((100, 110, 110), "stat", "max_hp"))
        self.assertEqual(result["observables"][0]["verdict"], "STAT_DIFFERENCE_EXPECTED")

    def test_cannot_label_death_tick_stat_only(self):
        with self.assertRaises(ValueError):
            A.adjudicate(arms((100, 110, 110), "stat", "death_tick"))

    def test_dependent_and_stochastic_remain_unresolved(self):
        for kind, expected in [("dependent", "STAT_CONFOUNDED_REQUIRES_CONTROL"),
                               ("stochastic", "RNG_DISTRIBUTION_REQUIRES_REPEATS")]:
            self.assertEqual(A.adjudicate(arms(kind=kind))["observables"][0]["verdict"], expected)

    def test_witch_multiset_ignores_slot_order_preserves_multiplicity(self):
        self.assertTrue(A.equal([{"death": 282}, {"death": 298}], [{"death": 298}, {"death": 282}], multiset=True))
        self.assertFalse(A.equal([1, 1, 2], [1, 2, 2], multiset=True))

    def test_missing_evidence_does_not_pass(self):
        for fault in ("missing", "unavailable", "no_evidence"):
            rows = arms((16, 16, 16))
            m = rows["native"]["observables"]
            if fault == "missing":
                del m["event"]
            elif fault == "unavailable":
                m["event"]["available"] = False
            else:
                del m["event"]["evidence"]
            self.assertEqual(A.adjudicate(rows)["observables"][0]["verdict"], "MISSING_EVIDENCE")

    def test_versions_scripts_and_initial_state_must_match(self):
        for key in ("native_version", "script_sha256", "replay_sha256"):
            rows = arms()
            rows["rsim"][key] = "wrong"
            with self.assertRaises(ValueError):
                A.adjudicate(rows)

    def test_mismatched_observable_contract(self):
        rows = arms()
        rows["rsim"]["observables"]["event"]["tolerance"] = 1
        self.assertEqual(A.adjudicate(rows)["observables"][0]["verdict"], "OBSERVABLE_CONTRACT_MISMATCH")

    def test_null_differs_from_missing(self):
        result = A.adjudicate(arms((None, None, None)))
        self.assertEqual(result["observables"][0]["verdict"], "AGREE")
        self.assertFalse(A.equal(True, 1))

    def test_config_does_not_mutate_template_and_clears_forms(self):
        row = S.scenarios()[0]
        ids = {n: i + 1 for i, n in enumerate(set(sum(row["script"]["decks"], [])))}
        template = {"battle": {"deck0": {"sp": [], "sc": [{"d": 123, "el": 3}]},
                                "deck1": {"sp": [], "sc": [{"d": 123}]}, "hbd": [{}, {}],
                                "avatar0": {}, "avatar1": {}}, "cmd": [123], "evt": [123]}
        before = copy.deepcopy(template)
        config = C.make_config(template, row, ids, 1)
        self.assertEqual(template, before)
        self.assertEqual(config["cmd"], [])
        self.assertTrue(all(set(c) == {"d"} for c in config["battle"]["deck0"]["sp"]))

    def test_schedule_success_requires_hand_change_and_spend(self):
        command = S.command(0, "X", (3.5, 14.5))
        pre = {"players": [{"owner": 0, "elixir": 10, "hand": [{"handIndex": 0, "cardId": 1, "cost": 3}]}]}
        post = {"players": [{"owner": 0, "elixir": 7.02, "hand": [{"handIndex": 0, "cardId": 2, "cost": 3}]}]}
        receipt = {"state": "succeeded", "error": "none", "executeTick": 101}
        result = C.accepted_event(command, {"X": 1}, pre, post, receipt)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["exec_tick"], 101)
        self.assertFalse(C.accepted_event(command, {"X": 1}, pre, pre, receipt)["accepted"])
        receipt["executeTick"] = 102
        self.assertFalse(C.accepted_event(command, {"X": 1}, pre, post, receipt)["accepted"])

    def test_fixture_loader_roundtrip(self):
        episode = self.directory / "synthetic-fixture"
        episode.mkdir()
        entry = {"split": "train", "start_tick": 100, "decks": [["X"] * 8, ["Y"] * 8],
                 "native_version": S.VERSION}
        C.dump(episode / "setup.json", {"entry": entry})
        C.dump(episode / "split.json", {"matches": [{"episode": episode.name, "split": "train"}]})
        players = [{"owner": side, "elixir": 10, "hand": [{"cardId": i + side * 8, "handIndex": i} for i in range(4)],
                    "cycle": [{"cardId": i + side * 8, "cycleIndex": i - 4} for i in range(4, 8)],
                    "deck": [{"cardId": i + side * 8, "deckSlot": i} for i in range(8)]} for side in (0, 1)]
        with gzip.open(episode / "evaluation-only.jsonl.gz", "wt") as f:
            f.write(json.dumps({"observation": {"players": players}}) + "\n")
        C.append(episode / "events.jsonl", {"accepted": True, "exec_tick": 101, "command_tick": 100,
                 "side": 0, "card": "X", "card_id": 0, "kind": "card", "tile": [3.5, 14.5], "slot": 0})
        with gzip.open(episode / "objects.jsonl.gz", "wt") as f:
            for tick in (100, 101):
                f.write(json.dumps({"tick": tick, "objects": [{"native_id": 1, "owner": 0, "card_id": -1,
                    "body_name": "KingTower", "x": 9000, "y": 1500, "hp": 100}]} ) + "\n")
        fixture = load_fixture(episode, load_split(episode / "split.json"))
        self.assertEqual(fixture.plays[0].exec_tick - 1, 100)
        self.assertEqual(fixture.initial_order[0], list(range(8)))
        self.assertEqual(fixture.units[1].tower_slot, 0)
        with self.assertRaises(PermissionError):
            load_fixture(episode, {episode.name: "heldout"})

    def test_resource_and_slot_stops(self):
        now = datetime.now(timezone.utc)
        slot = {"start": (now - timedelta(seconds=10)).isoformat(), "end": (now + timedelta(minutes=90)).isoformat(),
                "serial": C.SERIAL, "probe_port": C.PORT, "adb_server_port": 5049,
                "grant_reference": "synthetic", "native_version": S.VERSION, "baseline_swap_bytes": 0}
        with patch.object(C, "swap_used", return_value=0), patch.object(C.shutil, "disk_usage") as disk:
            disk.return_value.free = 9 * 1024**3
            C.slot_guard(slot, self.directory)
            disk.return_value.free = 7 * 1024**3
            with self.assertRaises(RuntimeError):
                C.slot_guard(slot, self.directory)
            disk.return_value.free = 9 * 1024**3
            with patch.object(C, "swap_used", return_value=2 * 1024**3), self.assertRaises(RuntimeError):
                C.slot_guard(slot, self.directory)
            slot["serial"] = "emulator-5554"
            with self.assertRaises(ValueError):
                C.slot_guard(slot, self.directory)

    def test_output_is_jobs_only(self):
        with self.assertRaises(ValueError):
            C.job_path(HERE / "official-data")
        self.assertEqual(C.job_path(self.directory), self.directory)

    def test_ssh_requires_exact_explicit_rc(self):
        self.assertEqual(mac_exec.parse_rc("some output\n__RC=7\n"), 7)
        self.assertEqual(mac_exec.parse_rc("__RC=0\n"), 0)
        for transcript in ("", "ssh exits zero", "__RC=0\n__RC=0\n", "prefix__RC=0"):
            with self.assertRaises(ValueError):
                mac_exec.parse_rc(transcript)

    def test_derivation_uses_whole_life_multisets_and_separates_stats(self):
        trace = self.directory / "synthetic-trace.jsonl.gz"
        with gzip.open(trace, "wt") as f:
            for tick, units in [(100, []), (101, [(1, 3500), (2, 4500)]), (102, [(2, 4550)])]:
                f.write(json.dumps({"tick": tick, "objects": [{"native_id": uid, "owner": 0, "card_id": 42,
                    "body_name": "Skeleton", "x": x, "y": 14500, "hp": 81, "max_hp": 81} for uid, x in units]}) + "\n")
        metadata = {"scenario": {"id": "synthetic", "script_sha256": "synthetic", "script": {
            "start_tick": 100, "end_tick": 102}}, "replay_sha256": "synthetic"}
        result = A.derive(trace, metadata, "native", {"synthetic": True})
        obs = result["observables"]
        self.assertEqual(obs["0/42/Skeleton.max_hp"]["value"], [81])
        self.assertEqual(obs["0/42/Skeleton.births"]["value"], [101, 101])
        self.assertTrue(obs["0/42/Skeleton.life_multiset"]["multiset"])
        self.assertEqual(obs["0/42/Skeleton.life_multiset"]["classification"], "dependent")

    def test_capture_full_control_flow_and_real_fixture_loader(self):
        # Fake server exercises the collector; these are NOT native outcomes.
        row = next(r for r in S.scenarios() if r["id"] == "MegaMinion.alone")
        ids = {n: i + 1 for i, n in enumerate(dict.fromkeys(sum(row["script"]["decks"], [])))}
        players = [{"owner": side, "elixir": 10.0,
                    "hand": [{"cardId": ids[n], "handIndex": i, "cost": 3} for i, n in enumerate(deck[:4])],
                    "cycle": [{"cardId": ids[n], "cycleIndex": i} for i, n in enumerate(deck[4:])],
                    "deck": [{"cardId": ids[n], "deckSlot": i} for i, n in enumerate(deck)]}
                   for side, deck in enumerate(row["script"]["decks"])]
        towers = [{"nativeObjectId": 5000000 + side * 3 + lane, "owner": side, "cardId": -1,
                   "x": (9000, 3500, 14500)[lane], "y": 2000 + side * 28000, "hp": 100, "maxHp": 100}
                  for side in (0, 1) for lane in (0, 1, 2)]
        state = {"tick": 0, "players": players, "pending": None}
        attest = {"ok": True, "synthetic": True}
        def fake_call(command):
            if command in ("observe", "observe-rich"):
                return copy.deepcopy({"ok": True, "tick": state["tick"], "truncated": False,
                                      "ended": False, "players": state["players"], "objects": towers})
            if command == "status":
                return {"ok": True, "ready": True, "paused": True, "renderSuppressed": False}
            if command == "attest":
                return attest
            if command.startswith("configure "):
                state["tick"] = 0
                return {"ok": True, "tick": 0}
            if command.startswith("step "):
                state["tick"] += int(command.split()[1])
                if state["pending"]:
                    owner, cid = state["pending"]
                    player = state["players"][owner]
                    card = next(c for c in player["hand"] if c["cardId"] == cid)
                    card["cardId"] = player["cycle"][0]["cardId"]
                    player["elixir"] -= card["cost"]
                    state["pending"] = None
                return {"ok": True, "tick": state["tick"]}
            if command.startswith("replay-schedule-card "):
                fields = command.split()
                state["pending"] = int(fields[1]), int(fields[2])
                return {"ok": True, "sequence": 1}
            if command == "replay-schedule-status 1":
                return {"ok": True, "state": "succeeded", "error": "none", "executeTick": 101}
            raise AssertionError(command)
        class FakeSession:
            def __call__(self, command):
                return fake_call(command)
            def close(self):
                pass
        inputs = {
            "slot": {"synthetic": True, "end": (datetime.now(timezone.utc) + timedelta(minutes=90)).isoformat()}, "attestation": attest,
            "template": {"battle": {"deck0": {"sc": [{}]}, "deck1": {"sc": [{}]},
                         "hbd": [{}, {}], "avatar0": {}, "avatar1": {}}},
            "gamedata": {"items": {"spells": [{"name": n, "id": cid} for n, cid in ids.items()]}}}
        from types import SimpleNamespace
        kwargs = {"scenario": row["id"], "output": self.directory / "synthetic-capture", "body_names": None}
        for name, value in inputs.items():
            path = self.directory / (name + ".json")
            C.dump(path, value)
            kwargs[name] = path
        with patch.object(C.platform, "system", return_value="Darwin"), \
                patch.object(C, "slot_guard", return_value={"synthetic": True}), \
                patch.object(C, "single", side_effect=fake_call), patch.object(C, "Session", FakeSession):
            C.capture(SimpleNamespace(**kwargs))
        output = kwargs["output"]
        self.assertEqual(json.loads((output / "metadata.json").read_text())["status"], "complete")
        fixture = load_fixture(output, load_split(output / "split.json"))
        self.assertEqual(fixture.start_tick, 100)
        self.assertEqual(fixture.end_tick, 600)
        self.assertEqual(len(fixture.ticks), 501)
        self.assertEqual(fixture.plays[0].exec_tick, 101)
        self.assertEqual(len(fixture.units), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
