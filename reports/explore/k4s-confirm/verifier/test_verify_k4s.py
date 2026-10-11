"""Tests for verify_k4s.py. Synthetic trees only: games are tiny JSON files, and the sizes are the test-only
--test-counts hook (primary 100 / 50 subsample, guard 36 / 18), which runs only with a SYNTHETIC marker.
Decks are the real §2 mapping from guard-decks.json (pinned by sha256), so fixtures carry real deck identities.

Author: Claude Haiku 5.5 (independent verifier author). Run from the worktree root with:
    nice -n 19 <python> -m pytest -q reports/explore/k4s-confirm/verifier
"""
import builtins
import copy
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import verify_k4s as V

COUNTS = (100, 50, 36, 18)  # primary n, primary sub, guard n, guard sub (test-only)
POPS_T = V.build_pops(COUNTS)
COUNTS_ARG = ",".join(str(x) for x in COUNTS)
DECKS = V.load_decks()


def outcome_mixed(pop, logical, arm, seat):
    """Deterministic winners covering draw, win and loss for the seat."""
    if arm == "K4-200":
        return [None, seat, 1 - seat][logical % 3]
    return [seat, None, 1 - seat][(logical + len(arm)) % 3]


def make_desc(pop, index, logical, cell=None, replaces=None):
    spec = POPS_T[pop]
    cell = logical % spec["cells"] if cell is None else cell
    order, rho, sub = V.expected_layout(pop, logical, POPS_T)
    want = V.scheduled_decks(pop, cell, DECKS)
    return dict(id=f"{pop}-{index:04d}", population=pop, index=index, seed=spec["base"] + index, cell=cell,
                seat=cell % 2, own_index=want["own_index"], opponent_index=want["opponent_index"],
                order=order, replaces=replaces, rotation=rho, subsample=sub)


def game_record(pop, did, desc, arm, winner, c_star=0.9):
    spec = V.ARM_SPEC[arm]
    c = float(spec["c"])
    sd1 = spec["default"] == "SD1"
    want = V.scheduled_decks(pop, desc["cell"], DECKS)
    meta = dict(study="PREREG-K4S SEALED", arm=arm, terminal=True, winner=winner, seat=desc["seat"],
                seed=desc["seed"], seed_index=desc["index"], cell=desc["cell"], population=pop,
                block_id=did, speed_cell=c, budget_ms=spec["budget"], deadline_seconds=spec["budget"] / 1000,
                reserve_ms=8, inference_scale=1 / c, scale_mode="poll", default_source=spec["default"],
                s_default_rule=spec["rule"], kernel=spec["kernel"], threads=4, coarse_horizon=160, c_star=c_star,
                own_deck=list(want["own"]), opponent_deck=list(want["opponent"]),
                freeze_manifest_sha256="a" * 64, runtime_pin_sha256="b" * 64,
                opponent_checkpoint_sha256="c" * 64, native_sha256="d" * 64,
                sd1_manifest_sha256="e" * 64 if sd1 else None, sd1_checkpoint_sha256="f" * 64 if sd1 else None,
                sd1_calibration_sha256="1" * 64 if sd1 else None,
                sd1_threshold=0.5005528330802917 if sd1 else None)
    return {"cohort": arm, "metadata": meta}


def write_block(root, desc, logical, outcome=outcome_mixed, edit=None, c_star=0.9, host="127x01"):
    """Writes complete.json and games/ for one block. edit(arm, record) may alter a game before it is hashed."""
    did = desc["id"]
    games = {}
    for arm in desc["order"]:
        fname = f"{did}-d27-{arm}.json"
        rec = game_record(desc["population"], did, desc, arm, outcome(desc["population"], logical, arm, desc["seat"]),
                          c_star=c_star)
        if edit is not None:
            edit(arm, rec)
        raw = json.dumps(rec, sort_keys=True).encode()
        path = root / did / "games" / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        games[fname] = V.sha256_bytes(raw)
    complete = dict(descriptor=desc, host=host, slot_cores=[0, 1, 2, 3, 4], games=games, interference={})
    (root / did / "complete.json").write_text(json.dumps(complete))


def write_hub_ack(root, did):
    (root / did / "hub-ack.json").write_text(json.dumps(dict(block=did, verified_sha256="ok")))


def write_originals(root, skip=(), c_star=0.9):
    for pop, spec in POPS_T.items():
        for logical in range(spec["n"]):
            if (pop, logical) in skip:
                continue
            write_block(root, make_desc(pop, logical, logical), logical, c_star=c_star)


def replacement(root, lost, k, logical, outcome=outcome_mixed, replaces=None, c_star=0.9):
    """Replacement for a lost descriptor, the k-th loss in its (population, cell), per §3.4. replaces defaults to
    the lost id; a chain's later replacement passes the logical original's id instead (§3)."""
    spec = POPS_T[lost["population"]]
    index = spec["n"] + spec["cells"] * k + lost["cell"]
    desc = make_desc(lost["population"], index, logical, cell=lost["cell"], replaces=replaces or lost["id"])
    write_block(root, desc, logical, outcome, c_star=c_star)
    return desc


def write_ledger(path, events):
    path.write_text(json.dumps({"events": events}))


def synthetic_root(tmp_path, name="tree"):
    root = tmp_path / name
    root.mkdir()
    (root / "SYNTHETIC").write_text("test-only tree\n")
    return root


def cli(argv):
    """Runs main() and returns (exit code, parsed JSON output)."""
    out = Path(argv[argv.index("--out") + 1])
    code = V.main(argv)
    return code, json.loads(out.read_text())


def base_argv(root, out, *extra):
    return ["--root", str(root), "--synthetic", "--test-counts", COUNTS_ARG, "--out", str(out), *extra]


def fake(upper):
    value = Fraction(upper)
    return {"_upper": value, "upper_float": float(value)}


def all_contracts(value=-1):
    return {key: fake(value) for key in V.CONTRASTS}


N_OF = {"P_full": 3000, "G_full": 900, "P_sub": 600, "G_sub": 300}


# ---------- seal (spec §7) ----------

def run_git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


def make_repo(tmp_path, completion_counts=(3000, 900)):
    """A committed repo holding the §7 items. Returns (repo, receipt) with the §7 receipt shape."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    (repo / "seal").mkdir()
    completion = dict(reporting_complete=True, outcomes_sealed=True,
                      counted_primary_blocks=completion_counts[0], counted_guard_blocks=completion_counts[1])
    contents = {"completion": json.dumps(completion).encode()}
    for name in ("production_checks", "verifier_receipt", "mac_procedure_manifest", "end_reference",
                 "end_recheck", "tiers_summary"):
        contents[name] = f"{name} bytes\n".encode()
    entries = {}
    for name, data in contents.items():
        rel = f"seal/{name}.bin"
        (repo / rel).write_bytes(data)
        entries[name] = dict(path=rel, sha256=V.sha256_bytes(data))
    run_git(repo, "add", "-A")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "seal")
    receipt = dict(coordinator_thread=V.COORDINATOR, authorization_message_id="msg-1",
                   authorized_at_utc="2026-10-12T00:00:00Z", study="PREREG-K4S", commit=head(repo), items=entries)
    return repo, receipt


def test_seal_accepts_a_matching_release(tmp_path):
    repo, receipt = make_repo(tmp_path)
    info = V.check_seal(repo, receipt)
    assert info["commit"] == receipt["commit"]
    assert set(info["item_sha256"]) == set(receipt["items"])


def test_seal_accepts_the_declaration_and_tiers_release_alternatives(tmp_path):
    repo, receipt = make_repo(tmp_path)
    end = receipt["items"].pop("end_reference")
    receipt["items"].pop("end_recheck")
    receipt["items"]["ratio_unavailable_declaration"] = end
    tiers = receipt["items"].pop("tiers_summary")
    receipt["items"]["tiers_release"] = tiers
    assert set(V.check_seal(repo, receipt)["item_sha256"]) == set(receipt["items"])


def test_seal_refuses_wrong_coordinator(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["coordinator_thread"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(V.Refusal, match="coordinator"):
        V.check_seal(repo, receipt)


def test_seal_refuses_wrong_study(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["study"] = "PREREG-K4S-DRAFT"
    with pytest.raises(V.Refusal, match="study"):
        V.check_seal(repo, receipt)


def test_seal_refuses_a_hash_mismatch(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["production_checks"]["sha256"] = "0" * 64
    with pytest.raises(V.Refusal, match="sha256"):
        V.check_seal(repo, receipt)


def test_seal_refuses_a_non_hex_sha256(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["production_checks"]["sha256"] = "Z" * 64
    with pytest.raises(V.Refusal, match="lowercase hex"):
        V.check_seal(repo, receipt)


def test_seal_refuses_an_item_with_extra_keys(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["production_checks"]["note"] = "x"
    with pytest.raises(V.Refusal, match="exactly path and sha256"):
        V.check_seal(repo, receipt)


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.bin", "seal/../../x.bin", ""])
def test_seal_refuses_a_path_outside_the_repository(tmp_path, path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["production_checks"]["path"] = path
    with pytest.raises(V.Refusal, match="repo-relative"):
        V.check_seal(repo, receipt)


def test_seal_refuses_working_tree_bytes_that_differ_from_the_commit(tmp_path):
    repo, receipt = make_repo(tmp_path)
    (repo / "seal" / "production_checks.bin").write_bytes(b"edited after the release commit\n")
    with pytest.raises(V.Refusal, match="working-tree bytes differ"):
        V.check_seal(repo, receipt)


def test_seal_refuses_a_missing_required_item(tmp_path):
    repo, receipt = make_repo(tmp_path)
    del receipt["items"]["verifier_receipt"]
    with pytest.raises(V.Refusal, match="verifier_receipt"):
        V.check_seal(repo, receipt)


def test_seal_refuses_both_end_alternatives(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["ratio_unavailable_declaration"] = dict(receipt["items"]["end_reference"])
    with pytest.raises(V.Refusal, match="exactly one of end_reference"):
        V.check_seal(repo, receipt)


def test_seal_refuses_end_reference_without_end_recheck(tmp_path):
    repo, receipt = make_repo(tmp_path)
    del receipt["items"]["end_recheck"]
    with pytest.raises(V.Refusal, match="exactly one of end_reference"):
        V.check_seal(repo, receipt)


def test_seal_refuses_both_tiers_items(tmp_path):
    repo, receipt = make_repo(tmp_path)
    receipt["items"]["tiers_release"] = dict(receipt["items"]["tiers_summary"])
    with pytest.raises(V.Refusal, match="exactly one of tiers_summary"):
        V.check_seal(repo, receipt)


def test_seal_refuses_a_commit_that_is_not_an_ancestor_of_head(tmp_path):
    repo, receipt = make_repo(tmp_path)
    run_git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("x")
    run_git(repo, "add", "-A")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "side")
    side = head(repo)
    run_git(repo, "checkout", "-q", "--detach", receipt["commit"])
    receipt["commit"] = side
    with pytest.raises(V.Refusal, match="ancestor"):
        V.check_seal(repo, receipt)


def test_seal_refuses_wrong_completion_counts(tmp_path):
    repo, receipt = make_repo(tmp_path, completion_counts=(2999, 900))
    with pytest.raises(V.Refusal, match="counted_primary_blocks"):
        V.check_seal(repo, receipt)


def test_seal_refuses_the_old_completion_shape(tmp_path):
    # A completion receipt with a nested "counted" object, not the §7 field names, is refused.
    repo, receipt = make_repo(tmp_path)
    completion = dict(reporting_complete=True, outcomes_sealed=True, counted=dict(primary=3000, guard=900))
    (repo / "seal" / "completion.bin").write_bytes(json.dumps(completion).encode())
    run_git(repo, "add", "-A")
    run_git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "old")
    receipt["commit"] = head(repo)
    receipt["items"]["completion"]["sha256"] = V.sha256_file(repo / "seal" / "completion.bin")
    with pytest.raises(V.Refusal, match="counted_primary_blocks"):
        V.check_seal(repo, receipt)


def test_no_release_and_no_synthetic_refuses_before_any_game(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    out = tmp_path / "out.json"
    code, result = cli(["--root", str(root), "--out", str(out)])
    assert code == 2 and result["status"] == "REFUSED"
    assert "no release receipt" in result["reason"]


def test_bad_release_refuses_before_games_are_opened(tmp_path):
    # The tree has descriptors and game names but no game bytes. A seal failure must win over any game error.
    root = tmp_path / "tree"
    root.mkdir()
    (root / "primary-0000").mkdir()
    (root / "primary-0000" / "complete.json").write_text("{}")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(dict(coordinator_thread="wrong", study="PREREG-K4S", authorization_message_id="x",
                                       authorized_at_utc="x", commit="0", items={})))
    out = tmp_path / "out.json"
    code, result = cli(["--root", str(root), "--release", str(receipt), "--out", str(out)])
    assert code == 2 and result["status"] == "REFUSED"
    assert "coordinator" in result["reason"]


def test_synthetic_marker_needs_the_flag(tmp_path):
    root = synthetic_root(tmp_path)
    out = tmp_path / "out.json"
    code, result = cli(["--root", str(root), "--release", str(tmp_path / "r.json"), "--out", str(out)])
    assert code == 2 and "SYNTHETIC" in result["reason"]


def test_synthetic_flag_needs_the_marker(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    out = tmp_path / "out.json"
    code, result = cli(["--root", str(root), "--synthetic", "--out", str(out)])
    assert code == 2 and "SYNTHETIC" in result["reason"]


def test_test_counts_are_refused_outside_synthetic_trees(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    out = tmp_path / "out.json"
    code, result = cli(["--root", str(root), "--release", str(tmp_path / "r.json"),
                        "--test-counts", COUNTS_ARG, "--out", str(out)])
    assert code == 2 and result["status"] == "REFUSED"


# ---------- counting, ledger and replacements (spec §3, §6.2) ----------

def test_full_tree_without_losses_counts_every_logical_block(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root)
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code in (0, 1), result.get("errors")
    assert result["counts"]["logical"]["primary"]["counted"] == 100
    assert result["counts"]["logical"]["guard"]["counted"] == 36
    assert result["counts"]["games"] == 100 * 8 + 50 * 2 + 36 * 8 + 18 * 2


def test_replacement_chain_names_the_logical_original_and_is_accepted(tmp_path):
    root = synthetic_root(tmp_path)
    lost_original = make_desc("primary", 3, 3)  # cell 3
    write_originals(root, skip={("primary", 3)})
    first = replacement(root, lost_original, k=0, logical=3)  # index 100 + 0 + 3 = 103
    assert first["index"] == 103
    second = replacement(root, first, k=1, logical=3, replaces=lost_original["id"])  # index 100 + 50 + 3 = 153
    assert second["index"] == 153 and second["replaces"] == "primary-0003"
    events = [dict(lost=lost_original, replacement=first), dict(lost=first, replacement=second)]
    ledger = tmp_path / "ledger.json"
    write_ledger(ledger, events)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger)))
    assert code in (0, 1), result.get("errors")
    assert result["counts"]["logical"]["primary"]["counted"] == 100
    assert result["counts"]["replacements"]["primary"] == 2


def test_replaces_must_name_the_logical_original_not_the_lost_replacement():
    lost_original = make_desc("primary", 3, 3)
    first = make_desc("primary", 103, 3, replaces="primary-0003")
    second = make_desc("primary", 153, 3, replaces=first["id"])  # the immediate lost id: refused by §3
    errors = []
    V.check_ledger([dict(lost=lost_original, replacement=first), dict(lost=first, replacement=second)],
                   POPS_T, errors)
    assert any("replaces primary-0103 is not the logical original primary-0003" in e for e in errors)


def test_single_level_replacement_must_also_name_the_original():
    lost = make_desc("primary", 3, 3)
    errors = []
    V.check_ledger([dict(lost=lost, replacement=make_desc("primary", 103, 3, replaces="primary-0099"))],
                   POPS_T, errors)
    assert any("is not the logical original primary-0003" in e for e in errors)


def test_wrong_replacement_index_is_an_error(tmp_path):
    lost = make_desc("primary", 3, 3)
    bad = make_desc("primary", 104, 3, replaces="primary-0003")  # should be 103 for k=0
    errors = []
    V.check_ledger([dict(lost=lost, replacement=bad)], POPS_T, errors)
    assert any("index 104" in e for e in errors)


def test_replacement_must_keep_the_lost_cell(tmp_path):
    lost = make_desc("primary", 3, 3)
    bad = make_desc("primary", 103, 3, cell=4, replaces="primary-0003")
    errors = []
    V.check_ledger([dict(lost=lost, replacement=bad)], POPS_T, errors)
    assert any("population or cell differs" in e for e in errors)


def test_replacement_bank_cap_per_cell(tmp_path):
    # k = 12 is past the bank for primary (max_k = 11). Build 13 losses in one cell, each replacing the last.
    lost = make_desc("primary", 3, 3)
    events = []
    current = lost
    for k in range(13):
        index = POPS_T["primary"]["n"] + POPS_T["primary"]["cells"] * k + 3
        rep = make_desc("primary", index, 3, replaces=lost["id"])
        events.append(dict(lost=current, replacement=rep))
        current = rep
    errors = []
    V.check_ledger(events, POPS_T, errors)
    assert any("bank cap" in e for e in errors)


def test_population_replacement_cap(tmp_path):
    # 10% of 100 primary is 10. Eleven replacements in distinct cells breaks the cap.
    events = []
    for cell in range(11):
        lost = make_desc("primary", cell, cell)
        rep = make_desc("primary", POPS_T["primary"]["n"] + cell, cell, replaces=lost["id"])
        events.append(dict(lost=lost, replacement=rep))
    errors = []
    V.check_ledger(events, POPS_T, errors)
    assert any("10% cap" in e for e in errors)


def test_unreplaced_loss_is_an_error(tmp_path):
    lost = make_desc("primary", 3, 3)
    errors = []
    V.check_ledger([dict(lost=lost, replacement=None)], POPS_T, errors)
    assert any("unreplaced" in e for e in errors)


def test_missing_logical_block_is_an_error(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root, skip={("guard", 5)})
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("guard: 1 logical blocks missing" in e for e in result["errors"])


def test_arm_set_must_equal_descriptor_order(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root)
    games_file = next((root / "primary-0007" / "games").iterdir())
    games_file.unlink()  # one game gone: the arm set no longer matches
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("primary-0007" in e for e in result["errors"])


def test_tampered_game_fails_the_sha256_check(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root)
    target = next((root / "primary-0004" / "games").iterdir())
    target.write_text(target.read_text().replace('"terminal": true', '"terminal": true, "x": 1'))
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("sha256 mismatch" in e for e in result["errors"])


def test_non_terminal_game_is_an_error():
    errors = []
    desc = make_desc("guard", 0, 0)
    rec = game_record("guard", desc["id"], desc, "K4-200", None)
    rec["metadata"]["terminal"] = False
    V.check_game(rec, desc["id"], "guard", desc, "K4-200", errors, "0.9", DECKS)
    assert any("non-terminal" in e for e in errors)


def test_a_qualification_record_in_a_counted_block_is_an_error(tmp_path):
    errors = []
    desc = make_desc("primary", 0, 0)
    rec = game_record("primary", desc["id"], desc, "K4-200", None)
    rec["metadata"]["freeze_manifest_sha256"] = None
    V.check_game(rec, desc["id"], "primary", desc, "K4-200", errors, "0.9", DECKS)
    assert any("freeze_manifest_sha256" in e for e in errors)


# ---------- integer outcomes (spec §6.2) ----------

def test_loss_and_draw_rule_on_integer_tables(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root)
    errors, flags = [], []
    counting = V.reduce_tree(root, POPS_T, [], "0.9", DECKS, errors, flags)
    assert errors == []
    col = V.ALL_ARMS.index("K4-200")
    table = counting["tables"]["primary"]
    for logical in range(100):
        desc = make_desc("primary", logical, logical)
        seat = desc["seat"]
        winner = outcome_mixed("primary", logical, "K4-200", seat)
        if winner is None:
            expect_loss, expect_draw = 0, 1
        else:
            expect_loss, expect_draw = int(winner != seat), 0
        assert table["loss"][logical, col] == expect_loss, logical
        assert table["draw"][logical, col] == expect_draw, logical


# ---------- percentiles and bootstrap (spec §6.3) ----------

def test_exact_percentile_matches_a_hand_computation():
    # R = 5, sorted [0,1,2,3,4], n = 50.
    # lower: pos = 4/40 = 1/10, value = 0 + (1/10)(1 - 0) = 1/10, times 100/50 = 1/5.
    # upper: pos = 4 * 39/40 = 39/10, value = 3 + (9/10)(4 - 3) = 39/10, times 2 = 39/5.
    vals = [0, 1, 2, 3, 4]
    assert V.exact_percentile(vals, V.Q_LO, 50) == Fraction(1, 5)
    assert V.exact_percentile(vals, V.Q_HI, 50) == Fraction(39, 5)


def test_exact_percentile_is_exact_at_an_integer_position():
    vals = list(range(10_001))  # R - 1 = 10000; 10000 / 40 = 250 exactly
    assert V.exact_percentile(vals, V.Q_LO, 100) == Fraction(250)


def test_bootstrap_draws_one_index_set_per_cell_in_ascending_order():
    rng = np.random.default_rng(1)
    matrix = np.arange(12).reshape(6, 2).astype(np.int64)
    counts = V.bootstrap(rng, matrix, rows=list(range(6)), cells=3, reps=4)
    ref_rng = np.random.default_rng(1)
    expect = np.zeros((4, 2), dtype=np.int64)
    for cell in range(3):
        idx = np.array([i for i in range(6) if i % 3 == cell])
        expect += matrix[idx[ref_rng.integers(0, idx.size, size=(4, idx.size))]].sum(axis=1)
    assert (counts == expect).all()


# ---------- judgements (spec §6.5) ----------

def test_strict_superiority_is_strict_and_margins_are_inclusive():
    flags = []
    assert V.judge("sup", fake(0), "<", 0, 600, flags)["holds"] is False
    assert V.judge("sup", fake(-Fraction(1, 10000)), "<", 0, 600, flags)["holds"] is True
    assert V.judge("margin", fake(5), "<=", 5, 3000, flags)["holds"] is True
    assert V.judge("margin", fake(Fraction(50001, 10000)), "<=", 5, 3000, flags)["holds"] is False
    assert any(f["code"] == "exact_boundary" for f in flags)


def test_within_one_step_flag_fires_inside_one_count():
    flags = []
    V.judge("near", fake(Fraction(5) + Fraction(1, 6000)), "<=", 5, 3000, flags)  # 1/60 pp < 100/3000 pp
    assert any(f["code"] == "within_one_step" for f in flags)


def test_sequence_stops_at_the_first_failure():
    contracts = all_contracts(-1)
    contracts[("dref", "0.7")] = fake(11)  # H2 = B(0.7) fails its part 1
    flags = []
    steps = V.run_sequence("0.9", contracts, N_OF, flags)
    assert list(steps) == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
    assert steps["H1"]["passed"] is True
    assert steps["H2"]["passed"] is False
    for later in ("H3", "H4", "H5", "H6", "H7"):
        assert steps[later]["reached"] is False and steps[later]["passed"] is None
    assert V.admission(steps, "0.8") == "B"
    assert V.admission(steps, "0.7") is None
    assert V.admission(steps, "0.9") is None


def test_h4_is_dropped_under_c_star_0_8():
    flags = []
    steps = V.run_sequence("0.8", all_contracts(-1), N_OF, flags)
    assert list(steps) == ["H1", "H2", "H3", "H5", "H6", "H7"]
    assert V.admission(steps, "0.9") is None
    assert V.admission(steps, "0.8") == "A"


def test_level_a_needs_its_own_step_and_falls_back_to_b():
    contracts = all_contracts(-1)
    contracts[("dref", "0.8")] = fake(7)  # passes B (<= 10), fails A (<= 5)
    flags = []
    steps = V.run_sequence("0.9", contracts, N_OF, flags)
    assert steps["H1"]["passed"] is True
    assert steps["H5"]["reached"] is True and steps["H5"]["passed"] is False
    assert V.admission(steps, "0.8") == "B"


def test_veto_gates_the_0_9_cell_and_is_inclusive_at_5():
    flags = []
    assert V.judge("veto", fake(5), "<=", V.VETO_MAX, 3000, flags)["holds"] is True
    assert V.judge("veto", fake(Fraction(50001, 10000)), "<=", V.VETO_MAX, 3000, flags)["holds"] is False
    admissions = {"0.9": "A", "0.8": None, "0.7": None, "0.6": None}
    assert V.usable_cells(admissions, veto_pass=True)["0.9"] is True
    assert V.usable_cells(admissions, veto_pass=False)["0.9"] is False


def test_usable_cells_at_levels_a_and_b():
    admissions = {"0.9": None, "0.8": "B", "0.7": "A", "0.6": None}
    usable = V.usable_cells(admissions, veto_pass=True)
    assert usable == {"0.9": False, "0.8": True, "0.7": True, "0.6": False}


def test_validity_window_is_inclusive_at_10_and_30_percent():
    flags = []
    assert V.validity(300, 3000, flags)["status"] == "OK"  # exactly 10%
    assert V.validity(900, 3000, flags)["status"] == "OK"  # exactly 30%
    assert V.validity(299, 3000, flags)["status"] == "SUSPENDED"
    assert V.validity(901, 3000, flags)["status"] == "SUSPENDED"
    assert sum(f["code"] == "exact_boundary" for f in flags) == 2


def test_contrast_record_exact_bounds_match_the_helper():
    diff = np.zeros(10_000, dtype=np.int64)
    diff[-250:] = 1
    boot = np.zeros((10_000, len(V.ALL_ARMS)), dtype=np.int64)
    boot[:, V.ALL_ARMS.index("K4S-180")] = diff
    losses = {"K4S-180": 0, "K4-180": 0}
    flags = []
    rec = V.contrast_record("veto", "P_full", 3000, "K4S-180", "K4-180", boot, losses, flags)
    assert rec["point_exact"] == "0"
    assert Fraction(rec["upper_exact"]) == V.exact_percentile(sorted(diff.tolist()), V.Q_HI, 3000)
    assert rec["lower_exact"] == "0"


def test_arm_roles_and_cells_match_the_spec_table():
    # §3.1 / K4S-SPEC §1: budgets 200c and the c labels for each arm.
    for arm, spec in V.ARM_SPEC.items():
        assert spec["budget"] == round(200 * float(spec["c"])), arm
    assert V.ARM_SPEC["K4-200"]["kernel"] == "K4-anytime"
    assert V.ARM_SPEC["K4S-200"]["kernel"] == "K4-anytime-sdefault"
    assert V.ARM_SPEC["K4-140"]["c"] == "0.7" and V.ARM_SPEC["K4-120"]["c"] == "0.6"


def test_layout_matches_the_rotation_and_subsample_rule():
    # Primary L=0: rho 0, in the subsample. K4-140 follows rotated position 3, K4-120 follows position 6.
    order, rho, sub = V.expected_layout("primary", 0, V.POPS)
    assert rho == 0 and sub is True
    assert order == V.CORE[0:3] + ["K4-140"] + V.CORE[3:6] + ["K4-120"] + V.CORE[6:8]
    # Guard L=400: rho = (400 // 18) % 8 = 6, outside the guard subsample (L < 300).
    order, rho, sub = V.expected_layout("guard", 400, V.POPS)
    assert rho == 6 and sub is False and order == V.CORE[6:] + V.CORE[:6]


# ---------- verifier_view comparison (spec §6.7) ----------

def cnt(losses, draws, n):
    return dict(losses=losses, draws=draws, n=n)


def hand_view():
    """A verifier_view written out by hand from the §6.7 table. It is not computed by the verifier."""
    return {
        "schema": "clasher.k4s.verifier-view.v1",
        "counts": {
            "P_full": {
                "K4-200": cnt(1000, 40, 3000), "K4S-200": cnt(990, 42, 3000), "K4-180": cnt(1010, 38, 3000),
                "K4S-180": cnt(1005, 35, 3000), "K4-160": cnt(1040, 30, 3000), "K4S-160": cnt(1030, 33, 3000),
                "K4S-140": cnt(1049, 31, 3000), "K4S-120": cnt(1060, 29, 3000),
            },
            "G_full": {
                "K4-200": cnt(330, 12, 900), "K4S-200": cnt(325, 11, 900), "K4-180": cnt(333, 9, 900),
                "K4S-180": cnt(331, 10, 900), "K4-160": cnt(340, 8, 900), "K4S-160": cnt(338, 7, 900),
                "K4S-140": cnt(342, 9, 900), "K4S-120": cnt(347, 6, 900),
            },
            "P_sub": {
                "K4-200": cnt(200, 8, 600), "K4S-200": cnt(198, 7, 600), "K4-180": cnt(202, 6, 600),
                "K4S-180": cnt(201, 5, 600), "K4-160": cnt(208, 6, 600), "K4S-160": cnt(206, 4, 600),
                "K4S-140": cnt(210, 5, 600), "K4S-120": cnt(212, 4, 600), "K4-140": cnt(207, 6, 600),
                "K4-120": cnt(214, 5, 600),
            },
            "G_sub": {
                "K4-200": cnt(100, 4, 300), "K4S-200": cnt(99, 3, 300), "K4-180": cnt(101, 3, 300),
                "K4S-180": cnt(100, 2, 300), "K4-160": cnt(104, 3, 300), "K4S-160": cnt(103, 2, 300),
                "K4S-140": cnt(105, 2, 300), "K4S-120": cnt(106, 1, 300), "K4-140": cnt(104, 2, 300),
                "K4-120": cnt(107, 2, 300),
            },
        },
        "contrasts": {
            "P_full:dref@0.9": dict(lower=[-3, 1], upper=[4, 1]),
            "P_full:dref@0.8": dict(lower=[-2, 1], upper=[7, 1]),
            "P_full:dref@0.7": dict(lower=[1, 1], upper=[9, 1]),
            "P_full:dref@0.6": dict(lower=[2, 1], upper=[12, 1]),
            "G_full:drefg@0.9": dict(lower=[-5, 1], upper=[9, 1]),
            "G_full:drefg@0.8": dict(lower=[-4, 1], upper=[11, 1]),
            "G_full:drefg@0.7": dict(lower=[-2, 1], upper=[12, 1]),
            "G_full:drefg@0.6": dict(lower=[1, 1], upper=[14, 1]),
            "P_full:dsame@0.8": dict(lower=[-6, 1], upper=[-1, 1]),
            "P_sub:dsame@0.7": dict(lower=[-3, 1], upper=[2, 1]),
            "P_sub:dsame@0.6": dict(lower=[-4, 1], upper=[1, 1]),
            "P_full:veto@0.9": dict(lower=[-4, 1], upper=[3, 1]),
        },
        "sequence": [
            dict(step="H1", hypothesis="B(0.8)", tested=True, passed=True),
            dict(step="H2", hypothesis="B(0.7)", tested=True, passed=True),
            dict(step="H3", hypothesis="B(0.6)", tested=True, passed=False),
            dict(step="H4", hypothesis="A(0.9)", tested=False, passed=None),
            dict(step="H5", hypothesis="A(0.8)", tested=False, passed=None),
            dict(step="H6", hypothesis="A(0.7)", tested=False, passed=None),
            dict(step="H7", hypothesis="A(0.6)", tested=False, passed=None),
        ],
        "admitted": {"0.9": None, "0.8": "B", "0.7": "B", "0.6": None},
        "veto_pass": True,
        "usable_cells": ["0.8", "0.7"],
        "validity_inside": True,
    }


def compare_with(reducer_view):
    return V.compare_verifier_view(hand_view(), {"verifier_view": reducer_view})


def test_hand_built_view_matches_itself_item_for_item():
    result = compare_with(hand_view())
    assert result["mismatched"] == 0 and result["mismatches"] == []
    assert result["matched"] == result["items"] > 100


@pytest.mark.parametrize("pair", [[14, 2], [-14, -2], [7, -1], [-7, -1], [0, 5], [7, 0], [1, 1.0]])
def test_noncanonical_rational_forms_are_mismatches(pair):
    # §6.7: lowest terms with a positive denominator. The value is 7, but these forms are not the canonical pair.
    reducer = hand_view()
    reducer["contrasts"]["P_full:dref@0.8"]["upper"] = pair
    result = compare_with(reducer)
    assert result["mismatched"] == 1
    assert result["mismatches"][0]["path"] == "verifier_view.contrasts.P_full:dref@0.8.upper"


def test_canonical_rational_forms_match():
    assert compare_with(hand_view())["mismatched"] == 0


def test_usable_cells_are_compared_as_a_set_in_any_order():
    reducer = hand_view()
    reducer["usable_cells"] = ["0.7", "0.8"]  # §6.7 compares usable_cells as a set
    assert compare_with(reducer)["mismatched"] == 0


@pytest.mark.parametrize("cells", [["0.8", "0.5"], ["0.8", 0.7], ["0.8", None], "0.8,0.7"])
def test_usable_cells_must_be_valid_cell_strings(cells):
    reducer = hand_view()
    reducer["usable_cells"] = cells
    assert compare_with(reducer)["mismatched"] == 1


def _set(*path, value):
    """A mutator that sets one nested item of the view. Missing keys are created by the caller's own edits."""
    def mutate(view):
        target = view
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return mutate


def _bump(*path, by=1):
    def mutate(view):
        target = view
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] += by
    return mutate


def _drop(*path):
    def mutate(view):
        target = view
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]
    return mutate


def _swap_sequence(view):
    view["sequence"][0], view["sequence"][1] = view["sequence"][1], view["sequence"][0]


PERTURBATIONS = [
    ("count losses +1", _bump("counts", "P_full", "K4-200", "losses")),
    ("count draws +1", _bump("counts", "G_sub", "K4-120", "draws")),
    ("count n changed", _set("counts", "P_sub", "K4S-120", "n", value=599)),
    ("count losses as float", _set("counts", "P_full", "K4-160", "losses", value=1040.0)),
    ("count arm missing", _drop("counts", "P_full", "K4S-180")),
    ("count arm extra in full analysis", _set("counts", "P_full", "K4-140", value=cnt(1, 1, 3000))),
    ("analysis missing", _drop("counts", "G_sub")),
    ("bound numerator changed", _bump("contrasts", "P_full:dref@0.9", "upper", 0)),
    ("bound denominator changed", _set("contrasts", "P_full:dref@0.9", "lower", value=[-3, 2])),
    ("bound as float", _set("contrasts", "G_full:drefg@0.6", "lower", value=[1.0, 1])),
    ("contrast key missing", _drop("contrasts", "P_full:veto@0.9")),
    ("contrast key extra", _set("contrasts", "P_full:dref@0.5", value=dict(lower=[0, 1], upper=[1, 1]))),
    ("sequence passed flipped", _set("sequence", 0, "passed", value=False)),
    ("sequence tested flipped", _set("sequence", 3, "tested", value=True)),
    ("sequence untested passed not null", _set("sequence", 3, "passed", value=False)),
    ("sequence step name changed", _set("sequence", 2, "step", value="H9")),
    ("sequence hypothesis changed", _set("sequence", 6, "hypothesis", value="A(0.5)")),
    ("sequence entry key missing", _drop("sequence", 0, "hypothesis")),
    ("sequence entry key extra", _set("sequence", 0, "note", value="x")),
    ("sequence shortened", lambda v: v["sequence"].pop()),
    ("sequence reordered", _swap_sequence),
    ("admitted level changed", _set("admitted", "0.8", value="A")),
    ("admitted level None to string", _set("admitted", "0.6", value="none")),
    ("admitted extra key", _set("admitted", "0.5", value=None)),
    ("admitted key missing", _drop("admitted", "0.6")),
    ("veto flipped", _set("veto_pass", value=False)),
    ("usable cell dropped", _set("usable_cells", value=["0.8"])),
    ("usable cell not a cell string", _set("usable_cells", value=["0.8", "0.5"])),
    ("validity flipped", _set("validity_inside", value=False)),
    ("bool as int", _set("validity_inside", value=1)),
    ("schema changed", _set("schema", value="clasher.k4s.verifier-view.v0")),
    ("top-level key extra", _set("extra", value=1)),
    ("top-level key missing", _drop("veto_pass")),
]


@pytest.mark.parametrize("name, mutate", PERTURBATIONS, ids=[p[0] for p in PERTURBATIONS])
def test_single_item_perturbation_is_a_mismatch(name, mutate):
    view = copy.deepcopy(hand_view())
    mutate(view)
    result = compare_with(view)
    assert result["mismatched"] >= 1, name
    assert result["matched"] + result["mismatched"] == result["items"]


def test_missing_verifier_view_in_the_reducer_is_a_mismatch():
    result = V.compare_verifier_view(hand_view(), {"counts": {}})
    assert result["mismatched"] == 1 and result["mismatches"][0]["path"] == "verifier_view"


def test_a_view_the_verifier_did_not_produce_is_a_mismatch():
    result = V.compare_verifier_view(None, {"verifier_view": hand_view()})
    assert result["mismatched"] == 1


# ---------- end to end and compare ----------

def build_scenario(tmp_path, c_star=0.9):
    root = synthetic_root(tmp_path)
    lost = make_desc("primary", 3, 3)
    write_originals(root, skip={("primary", 3), ("guard", 2)}, c_star=c_star)
    rep1 = replacement(root, lost, k=0, logical=3, c_star=c_star)
    g_lost = make_desc("guard", 2, 2)
    g_rep = replacement(root, g_lost, k=0, logical=2, c_star=c_star)
    ledger = tmp_path / "ledger.json"
    write_ledger(ledger, [dict(lost=lost, replacement=rep1), dict(lost=g_lost, replacement=g_rep)])
    return root, ledger


VIEW_KEYS = {"schema", "counts", "contrasts", "sequence", "admitted", "veto_pass", "usable_cells", "validity_inside"}
CONTRAST_KEYS = {"P_full:dref@0.9", "P_full:dref@0.8", "P_full:dref@0.7", "P_full:dref@0.6",
                 "G_full:drefg@0.9", "G_full:drefg@0.8", "G_full:drefg@0.7", "G_full:drefg@0.6",
                 "P_full:dsame@0.8", "P_sub:dsame@0.7", "P_sub:dsame@0.6", "P_full:veto@0.9"}


def test_end_to_end_run_with_replacements_is_clean(tmp_path):
    root, ledger = build_scenario(tmp_path)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger)))
    assert code in (0, 1), result.get("errors")
    assert result["status"] in ("OK", "SUSPENDED")
    assert set(result["contrasts"]) == CONTRAST_KEYS
    assert result["c_star"] == "0.9"


def test_verifier_view_has_exactly_the_spec_keys(tmp_path):
    root, ledger = build_scenario(tmp_path)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger)))
    view = result["verifier_view"]
    assert set(view) == VIEW_KEYS
    assert view["schema"] == "clasher.k4s.verifier-view.v1"
    assert set(view["counts"]) == {"P_full", "G_full", "P_sub", "G_sub"}
    assert set(view["counts"]["P_full"]) == set(V.CORE)
    assert set(view["counts"]["P_sub"]) == set(V.ALL_ARMS)
    assert set(view["contrasts"]) == CONTRAST_KEYS
    assert set(view["admitted"]) == {"0.9", "0.8", "0.7", "0.6"}
    assert all(set(c) == {"lower", "upper"} for c in view["contrasts"].values())
    assert all(len(v) == 2 and all(type(x) is int for x in v)
               for c in view["contrasts"].values() for v in c.values())


def test_compare_with_own_output_matches_and_tampering_is_caught(tmp_path):
    root, ledger = build_scenario(tmp_path)
    first = tmp_path / "reducer.json"
    code, _ = cli(base_argv(root, first, "--ledger", str(ledger)))
    assert code in (0, 1)

    second = tmp_path / "second.json"
    code2 = V.main(base_argv(root, second, "--ledger", str(ledger), "--compare", str(first)))
    result = json.loads(second.read_text())
    assert code2 in (0, 1), result["compare"]
    assert result["compare"]["mismatched"] == 0 and result["compare"]["mismatches"] == []
    assert result["compare"]["matched"] == result["compare"]["items"]

    tampered = json.loads(first.read_text())
    tampered["verifier_view"]["counts"]["P_full"]["K4-200"]["losses"] += 1
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(tampered))
    third = tmp_path / "third.json"
    code3 = V.main(base_argv(root, third, "--ledger", str(ledger), "--compare", str(bad)))
    assert code3 == 2
    compare = json.loads(third.read_text())["compare"]
    assert compare["mismatched"] == 1
    assert compare["mismatches"][0]["path"] == "verifier_view.counts.P_full.K4-200.losses"


def test_compare_against_a_reducer_without_verifier_view_exits_2(tmp_path):
    root, ledger = build_scenario(tmp_path)
    reducer = tmp_path / "reducer.json"
    reducer.write_text(json.dumps({"analysis": {}}))
    out = tmp_path / "out.json"
    code = V.main(base_argv(root, out, "--ledger", str(ledger), "--compare", str(reducer)))
    assert code == 2
    assert json.loads(out.read_text())["compare"]["mismatched"] == 1


def write_plan(tmp_path, c_star, marked=True, name="plan.json"):
    """A test-only plan fixture. The SYNTHETIC marker is what lets --synthetic read it."""
    path = tmp_path / name
    doc = dict(study="PREREG-K4S", c_star=c_star)
    if marked:
        doc["synthetic_marker"] = "SYNTHETIC"
    path.write_text(json.dumps(doc))
    return path


def test_default_plan_is_the_frozen_plan_json_and_binds_c_star_0_9(tmp_path):
    # (c) The default --plan is the frozen plan.json beside the verifier. Its c_star is 0.9, and the output records
    # the path and sha256 of the bytes that were read.
    assert V.PLAN_PATH == Path(V.__file__).resolve().parent.parent / "plan.json"
    root, ledger = build_scenario(tmp_path)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger)))
    assert code in (0, 1), result.get("errors")
    assert result["c_star"] == "0.9"
    assert result["plan"]["path"] == str(V.PLAN_PATH)
    assert result["plan"]["sha256"] == V.sha256_file(V.PLAN_PATH)
    assert result["plan"]["c_star"] == "0.9"
    assert list(result["hypotheses"]) == ["H1", "H2", "H3", "H4", "H5", "H6", "H7"]


def test_frozen_plan_is_0_9_and_is_read_as_data():
    doc = json.loads(V.PLAN_PATH.read_text())
    assert doc["c_star"] == 0.9 and "synthetic_marker" not in doc


def test_frozen_0_8_plan_refuses_a_mutually_consistent_0_9_cli_and_games(tmp_path):
    # (a) The plan says 0.8. The games record 0.9 and the CLI says 0.9, so the two agree with each other but not with
    # the frozen value. Refused before any decision or view.
    root, ledger = build_scenario(tmp_path, c_star=0.9)
    plan = write_plan(tmp_path, 0.8)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger), "--plan", str(plan),
                                 "--c-star", "0.9"))
    assert code == 2 and result["status"] == "REFUSED"
    assert "--c-star 0.9 != frozen plan c_star 0.8" in result["reason"]
    assert "verifier_view" not in result and "admission" not in result and "hypotheses" not in result


def test_frozen_0_8_plan_with_games_recording_0_9_is_an_input_error(tmp_path):
    # (a) without --c-star: the games' recorded 0.9 disagrees with the frozen 0.8, so no decision and no view.
    root, ledger = build_scenario(tmp_path, c_star=0.9)
    plan = write_plan(tmp_path, 0.8)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger), "--plan", str(plan)))
    assert code == 2 and result["status"] == "ERRORS"
    assert any("c_star 0.9 != frozen plan c_star 0.8" in e for e in result["errors"])
    assert "verifier_view" not in result and "admission" not in result and "hypotheses" not in result


def test_frozen_0_8_plan_with_games_recording_0_8_runs_the_normal_invocation(tmp_path):
    # (b) The normal invocation, with no --c-star. The plan is 0.8, the games record 0.8, and H4 is dropped.
    root, ledger = build_scenario(tmp_path, c_star=0.8)
    plan = write_plan(tmp_path, 0.8)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger), "--plan", str(plan)))
    assert code in (0, 1), result.get("errors")
    assert result["c_star"] == "0.8" and result["plan"]["c_star"] == "0.8"
    assert result["plan"]["sha256"] == V.sha256_file(plan)
    assert list(result["hypotheses"]) == ["H1", "H2", "H3", "H5", "H6", "H7"]
    assert result["usable_cells"]["0.9"] is False
    assert [s["step"] for s in result["verifier_view"]["sequence"]] == ["H1", "H2", "H3", "H5", "H6", "H7"]
    assert result["verifier_view"]["admitted"]["0.9"] is None


def test_c_star_on_the_cli_that_equals_the_frozen_0_8_plan_runs(tmp_path):
    root, ledger = build_scenario(tmp_path, c_star=0.8)
    plan = write_plan(tmp_path, 0.8)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger), "--plan", str(plan),
                                 "--c-star", "0.8"))
    assert code in (0, 1), result.get("errors")
    assert list(result["hypotheses"]) == ["H1", "H2", "H3", "H5", "H6", "H7"]


def test_c_star_on_the_cli_that_disagrees_with_the_frozen_plan_is_refused(tmp_path):
    # The plan says 0.9 and the CLI says 0.8, and the games record 0.8. The refusal is at the plan, not in the games.
    root, ledger = build_scenario(tmp_path, c_star=0.8)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger), "--c-star", "0.8"))
    assert code == 2 and result["status"] == "REFUSED"
    assert "--c-star 0.8 != frozen plan c_star 0.9" in result["reason"]
    assert "verifier_view" not in result and "hypotheses" not in result


def test_one_game_recording_another_c_star_is_an_input_error(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root)
    write_block(root, make_desc("guard", 0, 0), 0, c_star=0.8)  # one block, recorded at 0.8, in a 0.9 study
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("c_star 0.8 != frozen plan c_star 0.9" in e for e in result["errors"])
    assert "verifier_view" not in result


def test_plan_other_than_the_frozen_one_needs_synthetic(tmp_path):
    # A production tree with a valid seal, so the refusal comes from the plan rule and not from the release.
    repo, receipt = make_repo(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt))
    root, ledger = production_tree(tmp_path)
    plan = write_plan(tmp_path, 0.8)
    out = tmp_path / "out.json"
    code = V.main(["--root", str(root), "--ledger", str(ledger), "--plan", str(plan), "--out", str(out),
                   "--release", str(receipt_path), "--repo", str(repo)])
    reason = json.loads(out.read_text())["reason"]
    assert code == 2 and "--plan other than the frozen plan.json needs --synthetic" in reason


def test_test_plan_needs_the_synthetic_marker(tmp_path):
    root, ledger = build_scenario(tmp_path)
    plan = write_plan(tmp_path, 0.8, marked=False)
    out = tmp_path / "out.json"
    code = V.main(base_argv(root, out, "--ledger", str(ledger), "--plan", str(plan)))
    assert code == 2 and "needs the SYNTHETIC marker" in json.loads(out.read_text())["reason"]


@pytest.mark.parametrize("value", [0.7, "0.9", 1, None, True])
def test_plan_c_star_must_be_0_9_or_0_8(tmp_path, value):
    root, ledger = build_scenario(tmp_path)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(dict(c_star=value, synthetic_marker="SYNTHETIC")))
    out = tmp_path / "out.json"
    code = V.main(base_argv(root, out, "--ledger", str(ledger), "--plan", str(plan)))
    assert code == 2 and "c_star" in json.loads(out.read_text())["reason"]


def test_plan_that_is_not_json_is_refused(tmp_path):
    root, ledger = build_scenario(tmp_path)
    plan = tmp_path / "plan.json"
    plan.write_text("{")
    out = tmp_path / "out.json"
    code = V.main(base_argv(root, out, "--ledger", str(ledger), "--plan", str(plan)))
    assert code == 2 and "not JSON" in json.loads(out.read_text())["reason"]


# ---------- evidence refusals: no outcome or comparison file is read after a seal refusal (§7) ----------

@pytest.fixture
def read_spy(monkeypatch):
    """Records every path read through Path.open, Path.read_bytes or Path.read_text."""
    opened = []
    real_open, real_bytes, real_text = Path.open, Path.read_bytes, Path.read_text

    def spy_open(self, mode="r", *args, **kwargs):
        if not any(flag in mode for flag in "wax+"):  # reads only; the test's own writes are not recorded
            opened.append(str(self))
        return real_open(self, mode, *args, **kwargs)

    def spy_bytes(self):
        opened.append(str(self))
        return real_bytes(self)

    def spy_text(self, *args, **kwargs):
        opened.append(str(self))
        return real_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spy_open)
    monkeypatch.setattr(Path, "read_bytes", spy_bytes)
    monkeypatch.setattr(Path, "read_text", spy_text)
    return opened


def production_tree(tmp_path):
    """A production-shaped tree: no SYNTHETIC marker, so every refusal below is a production refusal."""
    root, ledger = build_scenario(tmp_path)
    (root / "SYNTHETIC").unlink()
    return root, ledger


def refusal_cases(tmp_path):
    """Every refusal path that --compare could follow, each with the reason it must give."""
    bad_receipt = tmp_path / "bad-receipt.json"
    bad_receipt.write_text(json.dumps(dict(coordinator_thread="wrong", study="PREREG-K4S", authorization_message_id="x",
                                           authorized_at_utc="x", commit="0", items={})))
    not_json = tmp_path / "not-json.json"
    not_json.write_text("{")
    return {"no release": ([], "no release receipt"),
            "bad coordinator": (["--release", str(bad_receipt)], "coordinator"),
            "unreadable receipt": (["--release", str(not_json)], "cannot read release receipt")}


@pytest.mark.parametrize("case", ["no release", "bad coordinator", "unreadable receipt"])
def test_no_game_or_comparison_file_is_read_after_a_seal_refusal(tmp_path, read_spy, case):
    root, ledger = production_tree(tmp_path)
    compare = tmp_path / "reducer.json"
    compare.write_text(json.dumps({"verifier_view": {}}))
    out = tmp_path / "out.json"
    extra, reason = refusal_cases(tmp_path)[case]
    argv = ["--root", str(root), "--ledger", str(ledger), "--out", str(out), "--compare", str(compare), *extra]
    code = V.main(argv)
    result = json.loads(out.read_text())
    assert code == 2 and result["status"] == "REFUSED"
    assert reason in result["reason"]
    assert "compare" not in result
    opened = set(read_spy)
    assert str(compare) not in opened
    assert str(V.PLAN_PATH) not in opened
    assert not any(p.startswith(str(root)) for p in opened)  # no block, complete.json or game file is read


def seal_failure_cases(repo, receipt):
    """Post-parse seal failures (§7): each mutates the receipt or the repository after the receipt parsed."""
    def absent_path(r):
        r["items"]["production_checks"]["path"] = "seal/absent.bin"

    def bad_sha(r):
        r["items"]["production_checks"]["sha256"] = "0" * 64

    def tree_differs(r):  # the receipt stays as committed; only the working-tree bytes change
        (repo / "seal" / "production_checks.bin").write_bytes(b"edited after the release commit\n")

    return {"missing committed item": (absent_path, "git show"),
            "bad sha": (bad_sha, "sha256"),
            "working-tree bytes differ": (tree_differs, "working-tree bytes differ")}


@pytest.mark.parametrize("case", ["missing committed item", "bad sha", "working-tree bytes differ"])
def test_post_parse_seal_failures_read_no_game_or_comparison(tmp_path, read_spy, case):
    repo, receipt = make_repo(tmp_path)
    mutate, reason = seal_failure_cases(repo, receipt)[case]
    mutate(receipt)
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt))
    root, ledger = production_tree(tmp_path)
    compare = tmp_path / "reducer.json"
    compare.write_text(json.dumps({"verifier_view": {}}))
    out = tmp_path / "out.json"
    code = V.main(["--root", str(root), "--ledger", str(ledger), "--out", str(out), "--compare", str(compare),
                   "--release", str(receipt_path), "--repo", str(repo)])
    result = json.loads(out.read_text())
    assert code == 2 and result["status"] == "REFUSED"
    assert reason in result["reason"]
    assert "compare" not in result
    opened = set(read_spy)
    assert str(compare) not in opened
    assert str(V.PLAN_PATH) not in opened
    assert not any(p.startswith(str(root)) for p in opened)


def test_synthetic_marker_refusal_reads_no_game_or_comparison(tmp_path, read_spy):
    root, ledger = build_scenario(tmp_path)
    (root / "SYNTHETIC").unlink()
    compare = tmp_path / "reducer.json"
    compare.write_text("{}")
    out = tmp_path / "out.json"
    code = V.main(["--root", str(root), "--ledger", str(ledger), "--synthetic", "--out", str(out),
                   "--test-counts", COUNTS_ARG, "--compare", str(compare)])
    assert code == 2 and "needs a SYNTHETIC file" in json.loads(out.read_text())["reason"]
    assert str(compare) not in read_spy
    assert not any(p.startswith(str(root)) for p in read_spy)


@pytest.mark.parametrize("extra, marked, reason", [
    (["--synthetic"], False, "needs a SYNTHETIC file"),
    (["--test-counts", COUNTS_ARG], True, "tree is marked SYNTHETIC"),
    (["--test-counts", COUNTS_ARG], False, "--test-counts is for SYNTHETIC trees only"),
])
def test_other_refusals_read_no_game_or_comparison(tmp_path, read_spy, extra, marked, reason):
    # --synthetic on a tree without the marker, a marked tree run without --synthetic, or --test-counts on a
    # production tree: all refused, each for its own reason.
    root, ledger = build_scenario(tmp_path)
    if not marked:
        (root / "SYNTHETIC").unlink()
    compare = tmp_path / "reducer.json"
    compare.write_text("{}")
    out = tmp_path / "out.json"
    code = V.main(["--root", str(root), "--ledger", str(ledger), "--out", str(out), "--compare", str(compare),
                   *extra])
    result = json.loads(out.read_text())
    assert code == 2 and result["status"] == "REFUSED" and reason in result["reason"]
    assert str(compare) not in read_spy
    assert not any(p.startswith(str(root)) for p in read_spy)


# ---------- hub acknowledgement (spec §6.1, r3 §4.4) ----------

def test_remote_host_block_without_hub_ack_file_is_not_counted(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root, skip={("primary", 10)})
    write_block(root, make_desc("primary", 10, 10), 10, host="127x03")
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2
    assert any("primary-0010" in e and "hub-ack.json" in e for e in result["errors"])
    assert any("primary: 1 logical blocks missing" in e for e in result["errors"])


def test_complete_json_hub_ack_key_is_not_proof(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root, skip={("primary", 10)})
    write_block(root, make_desc("primary", 10, 10), 10, host="127x03")
    doc = json.loads((root / "primary-0010" / "complete.json").read_text())
    doc["hub_ack"] = True
    (root / "primary-0010" / "complete.json").write_text(json.dumps(doc))
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("hub-ack.json" in e for e in result["errors"])


def test_remote_host_block_with_hub_ack_file_counts(tmp_path):
    root = synthetic_root(tmp_path)
    write_originals(root, skip={("primary", 10)})
    write_block(root, make_desc("primary", 10, 10), 10, host="127x03")
    write_hub_ack(root, "primary-0010")
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code in (0, 1), result.get("errors")
    assert result["counts"]["logical"]["primary"]["counted"] == 100


# ---------- winner key and deck identities (spec §6.2, §2) ----------

def test_missing_winner_key_is_an_error_not_a_draw():
    errors = []
    desc = make_desc("primary", 0, 0)
    rec = game_record("primary", desc["id"], desc, "K4-200", None)
    del rec["metadata"]["winner"]
    assert V.check_game(rec, desc["id"], "primary", desc, "K4-200", errors, "0.9", DECKS) is None
    assert any("winner key missing" in e for e in errors)


def test_explicit_null_winner_is_a_draw():
    errors = []
    desc = make_desc("primary", 0, 0)
    rec = game_record("primary", desc["id"], desc, "K4-200", None)
    meta, winner = V.check_game(rec, desc["id"], "primary", desc, "K4-200", errors, "0.9", DECKS)
    assert errors == [] and winner is None and "winner" in meta


def test_missing_winner_in_an_end_to_end_tree_is_an_error(tmp_path):
    root = synthetic_root(tmp_path)

    def drop_winner(arm, rec):
        if arm == "K4-200":
            del rec["metadata"]["winner"]

    write_originals(root)
    write_block(root, make_desc("primary", 4, 4), 4, edit=drop_winner)
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("winner key missing" in e for e in result["errors"])


def test_wrong_deck_index_in_a_descriptor_is_an_error():
    errors = []
    desc = make_desc("primary", 3, 3)
    desc["own_index"] = 999
    V.check_descriptor("primary-0003", desc, 3, errors, POPS_T, DECKS)
    assert any("own_index" in e and "§2" in e for e in errors)


def test_guard_opponent_index_must_follow_cell_div_6():
    errors = []
    desc = make_desc("guard", 7, 7)  # cell 7: opponent index 7 // 6 = 1
    desc["opponent_index"] = 0
    V.check_descriptor("guard-0007", desc, 7, errors, POPS_T, DECKS)
    assert any("opponent_index" in e for e in errors)


def test_game_with_another_cells_own_deck_is_an_error():
    errors = []
    desc = make_desc("primary", 3, 3)
    rec = game_record("primary", desc["id"], desc, "K4-200", None)
    rec["metadata"]["own_deck"] = V.scheduled_decks("primary", 4, DECKS)["own"]
    V.check_game(rec, desc["id"], "primary", desc, "K4-200", errors, "0.9", DECKS)
    assert any("own_deck != the scheduled own deck" in e for e in errors)


def test_one_arm_with_a_different_opponent_deck_is_an_error(tmp_path):
    root = synthetic_root(tmp_path)

    def swap_opponent(arm, rec):
        if arm == "K4S-200":
            rec["metadata"]["opponent_deck"] = V.scheduled_decks("primary", 5, DECKS)["opponent"]  # cell 5 -> primary[1]

    write_originals(root)
    write_block(root, make_desc("primary", 3, 3), 3, edit=swap_opponent)
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code == 2 and any("opponent_deck != the scheduled opponent deck" in e for e in result["errors"])


def test_shuffled_deck_order_is_accepted(tmp_path):
    root = synthetic_root(tmp_path)

    def shuffle(arm, rec):
        rec["metadata"]["own_deck"] = list(reversed(rec["metadata"]["own_deck"]))

    write_originals(root)
    write_block(root, make_desc("primary", 3, 3), 3, edit=shuffle)
    code, result = cli(base_argv(root, tmp_path / "out.json"))
    assert code in (0, 1), result.get("errors")


def test_guard_decks_must_match_the_pinned_sha256(tmp_path):
    bad = tmp_path / "guard-decks.json"
    bad.write_bytes(b'{"primary": []}')
    with pytest.raises(V.Refusal, match="pinned sha256"):
        V.load_decks(bad)


# ---------- replacement ledger replay (spec §3) ----------

def test_a_replacement_lost_before_its_allocation_is_an_error():
    # Event 1 loses the k=1 replacement of primary-0003 before any event allocated it.
    lost_original = make_desc("primary", 3, 3)
    first = make_desc("primary", 103, 3, replaces="primary-0003")
    second = make_desc("primary", 153, 3, replaces="primary-0003")
    errors = []
    V.check_ledger([dict(lost=second, replacement=first), dict(lost=lost_original, replacement=second)],
                   POPS_T, errors)
    assert any("primary-0153 before an earlier event allocated it" in e for e in errors)


def test_a_disconnected_chain_is_an_error():
    # Event 2 loses primary-0103, which is the active block of logical 3, but names logical 5 as its original.
    lost_original = make_desc("primary", 3, 3)
    first = make_desc("primary", 103, 3, replaces="primary-0003")
    other = make_desc("primary", 105, 5, replaces="primary-0005")
    bad = dict(first, replaces="primary-0005")
    errors = []
    V.check_ledger([dict(lost=lost_original, replacement=first), dict(lost=bad, replacement=other)], POPS_T, errors)
    assert any("primary-0103 differs from its allocated descriptor" in e or
               "primary-0103 is not the active block" in e for e in errors)


def test_losing_an_original_twice_is_an_error():
    lost_original = make_desc("primary", 3, 3)
    first = make_desc("primary", 103, 3, replaces="primary-0003")
    second = make_desc("primary", 153, 3, replaces="primary-0003")
    errors = []
    V.check_ledger([dict(lost=lost_original, replacement=first), dict(lost=lost_original, replacement=second)],
                   POPS_T, errors)
    assert any("primary-0003 is not the active block" in e for e in errors)


def test_chain_replay_accepts_a_valid_two_step_chain():
    lost_original = make_desc("primary", 3, 3)
    first = make_desc("primary", 103, 3, replaces="primary-0003")
    second = make_desc("primary", 153, 3, replaces="primary-0003")
    errors = []
    lost_ids, rep_ids, descs, per_pop, logical_of, active = V.check_ledger(
        [dict(lost=lost_original, replacement=first), dict(lost=first, replacement=second)], POPS_T, errors)
    assert errors == []
    assert active[("primary", 3)] == "primary-0153"
    assert lost_ids == {"primary-0003", "primary-0103"}


def test_an_unlisted_replacement_for_a_replaced_original_is_not_counted(tmp_path):
    # The tree has a stale replacement for logical 3 that the ledger does not name: it is refused, not counted.
    root, ledger = build_scenario(tmp_path)
    stale = make_desc("primary", 203, 3, replaces="primary-0003")
    write_block(root, stale, 3)
    code, result = cli(base_argv(root, tmp_path / "out.json", "--ledger", str(ledger)))
    assert code == 2 and any("primary-0203: replacement block not in the ledger" in e for e in result["errors"])


