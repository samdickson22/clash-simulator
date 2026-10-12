"""D1 plan re-run with safe_input r3 against origin/main TREE METADATA (names/modes/OIDs/sizes). No git object
content is read (GIT_COUNTERS['object_reads'] and the argv log prove it). The D1 member rule needs the runtime-pin-r2
name list: it is read from the clean working-tree file (not the object store) with expected SHA-256 f81f3655, and its
git blob OID is recomputed and compared with the ls-tree OID at the same commit."""
import hashlib, importlib.util, json, sys
R3 = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/safe-input-r3/safe_input.py"
spec = importlib.util.spec_from_file_location("safe_input", R3)
si = importlib.util.module_from_spec(spec)
spec.loader.exec_module(si)
# GIT is an argv-logging wrapper: #!/bin/sh / echo "ARGV $*" >> /dev/shm/si-r3-d1/git-argv.log / exec /usr/bin/git "$@"
REPO, GIT = "/mpac/sdicks02/repos/clasher", "/dev/shm/si-r3-d1/gitlog.sh"
PIN_REL, PIN_SHA = "reports/explore/s1/receipts/runtime-pin-r2.json", "f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d"
commit = si.git_run(REPO, ["rev-parse", "--verify", "origin/main^{commit}"], git_binary=GIT).stdout.decode().strip()
P = si.Policy("127x05", [si.Role("repo-tree", REPO, "read", 1 << 30, patterns=("**",), exemptions=("E1", "E4", "E5")),
                         si.Role("pins", REPO, "read", 64 << 20, exact=(PIN_REL,))])
entries = si.git_ls_tree(REPO, commit, git_binary=GIT)
by_path = {e["path"]: e for e in entries}
raw = si.read_bytes(P, "pins", PIN_REL, expected_sha256=PIN_SHA)
pin_oid = hashlib.sha1(b"blob %d\x00" % len(raw) + raw).hexdigest()
assert pin_oid == by_path[PIN_REL]["oid"], (pin_oid, by_path[PIN_REL])
pins = set(si.loads_strict(raw, PIN_REL)["files"])
member = lambda e: e["path"] in pins or e["path"].endswith(".py")
members = [e for e in entries if member(e)]
reads0 = si.GIT_COUNTERS["object_reads"]
# global rule (every entry, member or not): E4 fail-closed
global_refusal = None
try:
    si._screen_tree(P, "repo-tree", entries, ())
except si.Refusal as error:
    global_refusal = str(error)
# per-member screening (each member alone; the E1 alias with its target), so every refusal is counted, not just the first
refused = []
for e in members:
    sub = [e] + ([by_path[si.E1_LINK_TEXT]] if e["path"] == si.E1_ALIAS and si.E1_LINK_TEXT in by_path else [])
    try:
        si._screen_tree(P, "repo-tree", sub, None)
    except si.Refusal as error:
        refused.append({"path": e["path"], "code": error.code, "reason": error.reason})
family = [e["path"] for e in members if any(si.outcome_family(c) or si.end_claim_family(c) for c in e["path"].split("/"))]
# the definitive D1 plan (phase 1 only), through git_plan exactly as S9 would call it
plan_refusal, plan = None, None
try:
    plan = si.git_plan(P, "repo-tree", REPO, commit, members=member, git_binary=GIT)
except si.Refusal as error:
    plan_refusal = str(error)
argv_log = open("/dev/shm/si-r3-d1/git-argv.log").read()
e5_tree = {p: (by_path[p]["mode"], by_path[p]["type"], by_path[p]["oid"]) if p in by_path else None for p in si.E5_PATHS}
out = {"commit": commit, "safe_input_sha256": hashlib.sha256(open(R3, "rb").read()).hexdigest(),
       "constants_fingerprint": si.constants_fingerprint(), "tracked_entries": len(entries),
       "pin_list": {"rel": PIN_REL, "sha256": PIN_SHA, "git_oid_recomputed": pin_oid, "names": len(pins),
                    "source": "working-tree file read via si.read_bytes(expected_sha256); blob OID == ls-tree OID"},
       "members": len(members), "members_matching_a_family": family,
       "global_e4_rule_refusal": global_refusal, "member_refusal_count": len(refused), "member_refusals": refused,
       "git_plan_refusal": plan_refusal,
       "plan": None if plan is None else {"files": len(plan.files), "e4": [e["path"] for e in plan.e4],
                                          "e5": [(e["path"], e["mode"], e["oid"]) for e in plan.e5],
                                          "e1": None if plan.e1 is None else plan.e1["path"]},
       "e5_tree_metadata": e5_tree,
       "e5_constant_equals_tree": all(e5_tree[p] == ("100644", "blob", o) for p, o in si.E5_RUNTIME_MEMBERS),
       "object_reads": si.GIT_COUNTERS["object_reads"] - reads0, "git_runs": si.GIT_COUNTERS["runs"],
       "cat_file_batch_in_argv_log": "--batch" in argv_log,
       "git_argv_subcommands": sorted(set(l.split()[-1] if "cat-file" not in l else " ".join(l.split()[-2:]) for l in argv_log.splitlines()))}
print(json.dumps(out, indent=1))
