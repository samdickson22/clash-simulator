"""S4 r4 regression controls (SOL-REVIEW-END-S2S4-r3: S4-R3-F1 git indirection, S4-R3-F2 receipt-name families,
S4-R3-F3 metadata-before-blob ordering) and the E5 hook, each through the assembler's entrypoint (A.main via
World.run) on the synthetic World of test_assemble_fleet_reference.

Every git attack is paired with a POSITIVE CONTROL showing raw git (inherited environment, replacement objects
honoured) really serves the synthetic canary in that fixture. Checks use ok() (an explicit raise), never a bare
assert, so they keep their force under python -O."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from test_assemble_fleet_reference import (A, ALIAS_TARGET, E4, E4_OTHERS, EXCEPTION, GIT, HOST, World, audited,  # noqa
                                           canary, entry, fsha, inode, never_touched, ok, put, refused,
                                           runtime_pin_names, world)

CANARY = b'{"OUTCOME-CANARY": "synthetic sealed outcome bytes; must never reach S4"}\n'
MARK = b"OUTCOME-CANARY"


def git(repo, *args, env=None):
    return subprocess.run(GIT + ["-C", str(repo), *args], check=True, capture_output=True, env=env).stdout


def oid(repo, spec):
    return git(repo, "rev-parse", spec).decode().strip()


def plant_canary(world):
    """A synthetic outcome canary committed under games/ (a non-member blob in the object store)."""
    put(world.repo / "games" / "outcome.json", CANARY)
    world.commit()
    return oid(world.repo, "HEAD:games/outcome.json")


def bundle_has_no_canary(out):
    for path in Path(out).rglob("*"):
        if path.is_file():
            ok(MARK not in path.read_bytes(), "canary bytes reached the bundle: " + str(path))


class GitLog:
    """Wraps si.git_run (the only git spawn point): records argv and every object id requested via cat-file --batch."""

    def __init__(self, monkeypatch):
        self.calls, self.objects = [], []
        real = A.si.git_run

        def wrapper(repo, args, *rest, **kwargs):
            stdin = kwargs.get("stdin_bytes", rest[2] if len(rest) > 2 else None)
            self.calls.append(list(args))
            if list(args) == ["cat-file", "--batch"]:
                self.objects.append(stdin.decode().strip())
            return real(repo, args, *rest, **kwargs)
        monkeypatch.setattr(A.si, "git_run", wrapper)


# ---------------------------------------------------------------- S4-R3-F1: replacement refs / inherited environment

def test_replace_refs_never_substitute_e4_or_evidence_bytes(world):
    canary_oid = plant_canary(world)
    e2_oid, evidence_oid = oid(world.repo, "HEAD:" + EXCEPTION), oid(world.repo, "HEAD:" + A.EVIDENCE_REPO_DIR + "/end-evidence.json")
    git(world.repo, "replace", e2_oid, canary_oid)
    git(world.repo, "replace", evidence_oid, canary_oid)
    ok(git(world.repo, "cat-file", "blob", e2_oid) == CANARY, "positive control: the replace ref is live")
    ok(git(world.repo, "show", "HEAD:" + A.EVIDENCE_REPO_DIR + "/end-evidence.json") == CANARY)
    code, out = world.run()
    ok(code == 0, "the true blobs (pinned SHAs) must be read")
    manifest = json.loads((out / A.MANIFEST).read_text())
    ok(manifest["files"][A.EVIDENCE_NAME] == world.request["end_evidence"]["sha256"] != hashlib.sha256(CANARY).hexdigest())
    bundle_has_no_canary(out)


def foreign_repo(world):
    """A second repository whose E2 path, evidence and admissions hold the canary."""
    root = world.tmp / "foreign"
    root.mkdir()
    git(root, "init", "-q")
    for rel in (EXCEPTION, A.EVIDENCE_REPO_DIR + "/end-evidence.json", world.admission_rel("system-bus-admission.json")):
        put(root / rel, CANARY)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "foreign")
    return root


ENV_ATTACKS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_INDEX_FILE",
               "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_REPLACE_REF_BASE", "HOME", "XDG_CONFIG_HOME")


def apply_env(monkeypatch, attack, world, foreign):
    if attack == "GIT_DIR":
        monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    elif attack == "GIT_WORK_TREE":
        monkeypatch.setenv("GIT_WORK_TREE", str(foreign))
    elif attack in ("GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        monkeypatch.setenv(attack, str(foreign / ".git" / "objects"))
    elif attack == "GIT_INDEX_FILE":
        monkeypatch.setenv(attack, str(foreign / ".git" / "index"))
    elif attack == "GIT_CONFIG_PARAMETERS":
        monkeypatch.setenv(attack, "'core.hookspath'='%s'" % (world.tmp / "hooks"))
    elif attack == "GIT_CONFIG_COUNT":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "/bin/false")
    elif attack == "GIT_REPLACE_REF_BASE":
        monkeypatch.setenv(attack, "refs/heads/")
    else:
        home = world.tmp / "home"
        (home / "git").mkdir(parents=True, exist_ok=True)
        (home / ".gitconfig").write_text("[core]\n\tfsmonitor = /bin/false\n")
        (home / "git" / "config").write_text("[core]\n\tfsmonitor = /bin/false\n")
        monkeypatch.setenv(attack, str(home))


def test_inherited_git_dir_redirects_raw_git(world):
    """Positive control for the GIT_DIR probe (Sol r3): raw `git -C <permitted repo>` serves the foreign bytes."""
    foreign = foreign_repo(world)
    env = dict(os.environ, GIT_DIR=str(foreign / ".git"))
    ok(git(world.repo, "show", "HEAD:" + EXCEPTION, env=env) == CANARY)


@pytest.mark.parametrize("attack", ENV_ATTACKS)
def test_inherited_git_environment_cannot_redirect_s4(world, monkeypatch, attack):
    foreign = foreign_repo(world)
    apply_env(monkeypatch, attack, world, foreign)
    code, out = world.run()
    ok(code == 0, "the declared repository's true bytes must be read")
    bundle_has_no_canary(out)


@pytest.mark.parametrize("kind", ["alternates", "http-alternates", "grafts", "shallow", "hooks-config",
                                  "fsmonitor-config", "filter-config", "include-config", "worktree-config",
                                  "gitfile", "commondir"])
def test_static_repository_indirection_refused_before_git_runs(world, kind):
    foreign = foreign_repo(world)
    gitdir = world.repo / ".git"
    if kind in ("alternates", "http-alternates"):
        (gitdir / "objects" / "info").mkdir(exist_ok=True)
        (gitdir / "objects" / "info" / kind).write_text(str(foreign / ".git" / "objects") + "\n")
    elif kind == "grafts":
        (gitdir / "info").mkdir(exist_ok=True)
        (gitdir / "info" / "grafts").write_text(oid(world.repo, "HEAD") + "\n")
    elif kind == "shallow":
        (gitdir / "shallow").write_text(oid(world.repo, "HEAD") + "\n")
    elif kind == "hooks-config":
        git(world.repo, "config", "core.hooksPath", str(world.tmp / "hooks"))
    elif kind == "fsmonitor-config":
        git(world.repo, "config", "core.fsmonitor", "/bin/false")
    elif kind == "filter-config":
        git(world.repo, "config", "filter.x.smudge", "cat")
    elif kind == "include-config":
        git(world.repo, "config", "include.path", str(world.tmp / "other.cfg"))
    elif kind == "worktree-config":
        git(world.repo, "config", "core.worktree", str(foreign))
    elif kind == "gitfile":
        os.rename(gitdir, world.tmp / "moved.git")
        (world.repo / ".git").write_text("gitdir: %s\n" % (foreign / ".git"))
    else:
        (gitdir / "commondir").write_text(str(foreign / ".git") + "\n")
    runs = A.si.GIT_COUNTERS["runs"]
    refused(world, r"--repository.*: safe_input refused \[(indirection|root)\]")
    ok(A.si.GIT_COUNTERS["runs"] == runs, "git ran before the static indirection refusal")


# ---------------------------------------------------------------- S4-R3-F3: whole-tree metadata before any blob

@pytest.mark.parametrize("rel", ["zz-outcome/complete.json", "zzz/COMPLETE.json/x.txt", "a/b/c/Complete.json"])
def test_late_unlisted_complete_json_aborts_before_any_object_read(world, monkeypatch, rel):
    """Sol r3's reproduction: the four E4 stand-ins (accepted), then a later unlisted complete.json: phase 1 refuses
    the whole tree with ZERO object reads (no cat-file --batch at all), not just without reading the fifth blob."""
    put(world.repo / rel, CANARY)
    world.commit()
    log = GitLog(monkeypatch)
    reads = A.si.GIT_COUNTERS["object_reads"]
    refused(world, r"--repository HEAD tree: safe_input refused \[name\]: tracked complete.json outside the exact E4 list")
    ok(A.si.GIT_COUNTERS["object_reads"] == reads and log.objects == [], "an object was read: %r" % log.objects)
    ok(["cat-file", "--batch"] not in log.calls)


@pytest.mark.parametrize("change", ["bytes", "mode-755", "symlink"])
def test_changed_e4_identity_refused_before_any_object_read(world, monkeypatch, change):
    name = E4_OTHERS[0]
    if change == "bytes":
        put(world.repo / name, b"synthetic changed bytes\n")
    elif change == "mode-755":
        os.chmod(world.repo / name, 0o755)
    else:
        os.remove(world.repo / name)
        os.symlink("elsewhere.json", world.repo / name)
    world.commit()
    log = GitLog(monkeypatch)
    refused(world, r"safe_input refused \[exemption\]: E4 entry " + re.escape(name) + " is not the pinned 100644 blob")
    ok(log.objects == [], "an object was read before the E4 identity refusal: %r" % log.objects)


def test_non_member_outcome_blobs_are_never_requested(world, monkeypatch):
    """D1-style membership: tracked games/, hub-ack.returned.json, END-FINAL, attempt-*.json blobs that S4 does not
    need are never requested (only planned members' OIDs reach cat-file --batch)."""
    for rel in ("games/outcome.json", "x/hub-ack.returned.json", "y/END-FINAL.json", "z/attempt-00.json",
                "w/end-raw.json", "v/interference.json"):
        put(world.repo / rel, CANARY)
    world.commit()
    forbidden = {oid(world.repo, "HEAD:games/outcome.json")}
    log = GitLog(monkeypatch)
    code, out = world.run()
    ok(code == 0 and not forbidden & set(log.objects), "a non-member outcome blob was requested")
    wanted = {oid(world.repo, "HEAD:" + p) for p in [A.E1_ALIAS, ALIAS_TARGET, A.EVIDENCE_REPO_DIR + "/end-evidence.json",
                                                      *[r for _, r, _ in world.committed], *E4]}
    ok(set(log.objects) <= wanted, "an unplanned object was requested: %r" % (set(log.objects) - wanted))
    bundle_has_no_canary(out)


# ---------------------------------------------------------------- S4-R3-F2: END receipt / outcome name families

F2_NAMES = ("END-FINAL.json", "attempt-00.json", "end-raw-copy.json", "complete-v2.json",          # Sol r3 exact four
            "End-Final.JSON", "ATTEMPT-01.json", "End_Raw.json", "COMPLETE-V2.JSON", "x-END-JOB.json",
            "Hub-Ack.json", "hub_ack-smoke-0001.json", "Interference.Json", "incomplete.json", "end-complete.json")


@pytest.mark.parametrize("name", F2_NAMES)
@pytest.mark.parametrize("cls", ["sets", "guard-freeze", "model-calibration"])
def test_standalone_end_receipt_names_refused_before_access(world, audited, cls, name):
    """Valid input bytes at a family name OUTSIDE the strict END pair: refused by name, never opened (by inode)."""
    if cls == "sets":
        data, key = (A.canonical(world.sets) + "\n").encode(), ("sets",)
    elif cls == "guard-freeze":
        data, key = (world.guard / "FROZEN-T1.json").read_bytes(), ("guard", "freeze")
    else:
        data, key = (world.models / "R3a-calibration.json").read_bytes(), ("models", "R3a-calibration.json")
    target = canary(world.tmp / "aux" / name, data)
    holder = world.request
    for k in key[:-1]:
        holder = holder[k]
    holder[key[-1]] = dict(source=str(target), sha256=hashlib.sha256(data).hexdigest())
    refused(world, r"safe_input refused \[name\]: (outcome|END claim) name family")
    never_touched(audited, target)


@pytest.mark.parametrize("component", ["GAMES", "Games.tmp", "old-games", "x_games_y", "Hub-Blocks", "hub_block"])
def test_case_and_variant_outcome_directories_refused(world, audited, component):
    data = (A.canonical(world.sets) + "\n").encode()
    target = canary(world.tmp / component / "sets.json", data)
    world.request["sets"] = dict(source=str(target), sha256=hashlib.sha256(data).hexdigest())
    refused(world, r"sets: safe_input refused \[name\]: outcome name family (games|hub-blocks)")
    never_touched(audited, target)


@pytest.mark.parametrize("name", ["data/END-FINAL.json", "data/attempt-00.json", "data/end-raw-copy.json",
                                  "data/complete-v2.json", "data/Complete.JSON"])
def test_runtime_inventory_names_refused(world, audited, name):
    target = canary(world.runtime / name)
    runtime_pin_names(world, name)
    refused(world, r"runtime tree: safe_input refused \[name\]")
    never_touched(audited, target)


@pytest.mark.parametrize("name", ["run-r1/END-FINAL.json", "run-r1/attempt-00.json", "run-r1/end-raw-copy.json",
                                  "run-r1/complete-v2.json"])
def test_evidence_artifact_names_refused_before_any_open(world, audited, name):
    target = canary(world.artifacts / name, b'{"synthetic": "completion.json"}\n')
    world.evidence_doc["completion"].update(path=name, sha256=fsha(world.artifacts / "run-r1/completion/completion.json"),
                                            repository_path=A.EVIDENCE_REPO_DIR + "/" + name)
    os.chmod(target, 0o644)
    world.write_evidence()
    os.chmod(target, 0)
    refused(world, r"evidence artifact " + re.escape(name) + r": safe_input refused \[name\]")
    never_touched(audited, target)


def test_declared_health_filenames_stay_readable(world):
    """Control: the legitimate names (launch.json, supervisor-exit.json, mhz.jsonl, census.jsonl, plan.json,
    end-evidence.json, the E3 admissions) pass the shared denylist; the happy path is unchanged."""
    code, _ = world.run()
    ok(code == 0)


# ---------------------------------------------------------------- E5 hook (exact path + blob OID; production EMPTY)

E5_PATH = "reports/explore/k4s-confirm/check_games.py"
E5_BYTES = b"# synthetic stand-in for a tracked *games*.py runtime member\n"


def blob_oid(data):
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def add_e5(world, data=E5_BYTES, oid_=None):
    put(world.runtime / E5_PATH, data)
    world.pin(lambda p: p.update(e5_runtime_exempt={E5_PATH: oid_ or blob_oid(data)}))


def test_e5_production_constant_is_empty_and_fixed():
    ok(A.E5_RUNTIME_EXEMPT == {} and A.PRODUCTION_PINS["e5_runtime_exempt"] == {})
    bad = json.loads(json.dumps(A.PRODUCTION_PINS))
    bad["e5_runtime_exempt"] = {E5_PATH: blob_oid(E5_BYTES)}
    with pytest.raises(A.AssemblyError, match="E5 runtime exemptions must be exactly the production constant"):
        A.check_exemptions(bad, synthetic=False)


def test_e5_empty_refuses_a_family_named_runtime_member(world, audited):
    target = canary(world.runtime / E5_PATH, E5_BYTES)
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family games: .*check_games.py")
    never_touched(audited, target)


def test_e5_exact_entry_accepted_in_test_mode(world, audited):
    add_e5(world)
    world.request["runtime_files_sha256"] = A.canonical_sha(A.runtime_files(world.runtime, world.pins))
    code, out = world.run()
    ok(code == 0, "an exact (path, oid) E5 entry must be accepted in test mode")
    manifest = json.loads((out / A.MANIFEST).read_text())
    ok(manifest["runtime_files"][E5_PATH] == hashlib.sha256(E5_BYTES).hexdigest())
    receipt = json.loads((out / A.RECEIPT).read_text())
    ok(receipt["e5_runtime_exempt"] == [E5_PATH] and receipt["production_pins"] is False)
    identity = inode(world.runtime / E5_PATH)
    ok(len([p for p, inodes in audited.events if identity in inodes]) == 1, "E5 entry must be opened exactly once")


def test_e5_wrong_oid_refused(world):
    add_e5(world, oid_="0" * 40)
    refused(world, r"runtime tree: safe_input refused \[exemption\]: E5 entry " + re.escape(E5_PATH) + " is not blob")


def test_e5_entry_hard_linked_or_symlinked_refused_unread(world, audited):
    add_e5(world)
    outcome = canary(world.tmp / "games" / "e5" / "complete.json", E5_BYTES)
    os.remove(world.runtime / E5_PATH)
    os.link(outcome, world.runtime / E5_PATH)
    refused(world, r"runtime tree: safe_input refused \[nlink\]")
    never_touched(audited, outcome)
    os.remove(world.runtime / E5_PATH)
    os.symlink(outcome, world.runtime / E5_PATH)
    refused(world, r"runtime tree: safe_input refused \[symlink\]")
    never_touched(audited, outcome)


def test_e5_only_exempts_the_exact_path(world, audited):
    add_e5(world)
    other = canary(world.runtime / "reports/explore/k4s-confirm/qualify_games.py", E5_BYTES)
    refused(world, r"runtime tree: safe_input refused \[name\]: outcome name family games: .*qualify_games.py")
    never_touched(audited, other)


def test_e5_entry_must_be_a_runtime_member(world):
    rel = "data/games-notes.txt"
    put(world.runtime / rel, E5_BYTES)
    world.pin(lambda p: p.update(e5_runtime_exempt={rel: blob_oid(E5_BYTES)}))
    refused(world, "E5 entries that are not runtime members refused")


@pytest.mark.parametrize("rel,oid_", [
    (EXCEPTION, "0" * 40),                                                  # an E4 path
    ("x/END-FINAL.json", "0" * 40),                                         # an END-claim name
    ("reports/explore/k4s-confirm/end/x_games.py", "0" * 40),               # inside the strict END pair
    ("src/a.py", "0" * 40),                                                 # not a family name at all
    (E5_PATH, "z" * 40),                                                    # not an OID
    ("../x_games.py", "0" * 40),                                            # not a relative path
])
def test_e5_entries_are_validated(world, rel, oid_):
    world.pin(lambda p: p.update(e5_runtime_exempt={rel: oid_}))
    refused(world, "E5 entry|Unsafe relative path")


# ---------------------------------------------------------------- the pinned safe_input loader and its re-check

HERE = Path(__file__).resolve().parent
PINNED = "f9ca49267dd350cf7ca6fc64b25ce93f53d8e63e9326356dbc72574ec380b648"


def copied_assembler(tmp_path, mutate_layer=None, pin_layer_sha=False, link_layer=False):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    source = (HERE / "assemble_fleet_reference.py").read_text()
    layer = (HERE / "safe_input.py").read_bytes()
    if mutate_layer:
        layer = mutate_layer(layer)
    (pkg / "safe_input.py").write_bytes(layer)
    if pin_layer_sha:
        ok(source.count(PINNED) == 1)
        source = source.replace(PINNED, hashlib.sha256(layer).hexdigest())
    (pkg / "assemble_fleet_reference.py").write_text(source)
    if link_layer:
        os.link(pkg / "safe_input.py", tmp_path / "layer-alias.py")
    return pkg / "assemble_fleet_reference.py"


def run_help(script):
    return subprocess.run([sys_executable(), "-I", "-B", str(script), "--help"], capture_output=True, text=True)


def sys_executable():
    import sys
    return sys.executable


@pytest.mark.parametrize("case,message", [
    ("other-bytes", "is not the pinned safe_input r2"),
    ("fingerprint", "constants fingerprint differs"),
    ("hard-link", "single-link regular file"),
    ("control", None),
])
def test_loader_pins_the_layer(tmp_path, case, message):
    kwargs = {"other-bytes": dict(mutate_layer=lambda b: b + b"\n# extra\n"),
              "fingerprint": dict(mutate_layer=lambda b: b.replace(b"a2f94dd0ce1ab1f4b233d63201a454318dc0ecff",
                                                                   b"a2f94dd0ce1ab1f4b233d63201a454318dc0ecfe", 1),
                                  pin_layer_sha=True),
              "hard-link": dict(link_layer=True), "control": {}}[case]
    done = run_help(copied_assembler(tmp_path, **kwargs))
    if message is None:
        ok(done.returncode == 0 and "usage" in done.stdout, done.stderr)
    else:
        ok(done.returncode != 0 and message in done.stderr, done.stderr)


def test_production_run_refuses_an_in_process_edited_layer(world, monkeypatch):
    """A production run re-checks the layer's constants fingerprint: an E4 value edited in process refuses."""
    monkeypatch.delenv(A.SYNTHETIC_ENV)
    from test_assemble_fleet_reference import real_e4
    real_e4(monkeypatch)
    monkeypatch.setitem(A.si.E4_GIT_BLOB_OIDS, EXCEPTION, "0" * 40)
    refused(world, "safe_input constants were changed in process", out=world.tmp / "out" / "bundle")


# ---------------------------------------------------------------- every input name-gated before ANY input is opened

def test_a_late_forbidden_source_refuses_before_any_earlier_input_is_opened(world, audited):
    """The forbidden name is the LAST input planned (a seed); the models/sets/freeze that plan_bundle reads earlier
    must never be opened: Sources gates every request source by name before the first access."""
    seed = sorted(world.request["guard"]["seed_inputs"])[-1]
    data = (world.guard / "repo" / seed).read_bytes()
    bad = canary(world.tmp / "aux" / "END-FINAL.json", data)
    world.request["guard"]["seed_inputs"][seed] = dict(source=str(bad), sha256=hashlib.sha256(data).hexdigest())
    refused(world, r"seed .*: safe_input refused \[name\]: END claim name family end-final")
    never_touched(audited, bad, *[world.models / n for n in A.MODEL_NAMES], world.tmp / "sets.json",
                  world.guard / "FROZEN-T1.json", world.runtime / "src/a.py")


# ---------------------------------------------------------------- production reads carry expected SHA-256s

def test_s1_runtime_pin_is_read_with_its_pinned_sha(world):
    put(world.runtime / A.S1_RUNTIME_PINS[0], {"files": ["data/x.json", "src/a.py", EXCEPTION, "src/a.py"]})
    refused(world, "S1 runtime pin differs from its pin: " + re.escape(A.S1_RUNTIME_PINS[0]))


def test_s1_qualified_binding_is_read_with_its_pinned_sha(world):
    put(world.runtime / A.S1_QUALIFIED, {"qualified_source_files": {}})
    refused(world, "S1 qualified binding differs from its pin")


def test_json_inputs_are_read_with_the_request_sha(world):
    """pinned_json: the request SHA is checked by si BEFORE the bytes are parsed (states-rows.json, sets, freeze)."""
    path = world.models / "states-rows.json"
    os.chmod(path, 0o644)
    path.write_bytes(path.read_bytes().replace(b'"verified": true', b'"verified": false'))
    refused(world, "Pin mismatch: model states-rows.json")


def test_evidence_artifact_label_is_the_pre_open_name_gate(world, audited):
    """The refusal comes from the upfront name pass ('evidence artifact <name>'), not from a later open."""
    name = "run-r1/END-FINAL.json"
    world.evidence_doc["completion"].update(path=name, repository_path=A.EVIDENCE_REPO_DIR + "/" + name)
    world.write_evidence()
    refused(world, r"^evidence artifact " + re.escape(name) + r": safe_input refused \[name\]")
