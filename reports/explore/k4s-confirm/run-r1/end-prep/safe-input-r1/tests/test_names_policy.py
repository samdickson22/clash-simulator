"""Policy/role construction, constants, and every NAME refusal (no syscall may happen before a name refusal)."""
import os

import pytest

from conftest import HOST, ok, policy, refusal, role, si


# ---------------------------------------------------------------- constants (single source of truth)
def test_constants_are_the_ruled_values():
    ok(si.APPROVED_K4S_MANIFEST_SHA256 == "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357")
    ok(si.END_BASES == {"127x03": "/mpac/sdicks02/jobs/clasher/k4s-end-r1",
                        "127x04": "/mpac/sdicks02/jobs-k4s/k4s-end-r1"})
    ok(si.Q4_GUARD_PARENTS == {"127x03": "/mpac/sdicks02/jobs/clasher", "127x04": "/mpac/sdicks02/jobs-k4s"})
    ok(si.E1_ALIAS == "visualize_battle.py" and si.E1_LINK_TEXT == "examples/visualize_battle.py")
    ok(si.E4_COMPLETE_JSON == {
        "imitation/model/receipts/throughput-0935/complete.json":
            "d1492d0f49d4f9c7836ca0c1fc48240e8749545e2855c6fa61c70e2b192eb5fc",
        "reports/strategy_council_20260928/live-loop/v4/emulator-host/complete.json":
            "0a4906396b270206e900b62ca9dbc0f44e2de6aefb512c7990824a4b2fed836f",
        "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-gap-export-20261012-r1/complete.json":
            "9c84b7a8b8c821921dd9cd0ddf1e814a24dc99c56d82829ff5894add34040c81",
        "reports/strategy_council_20260928/live-loop/v4/l1/receipts/b08-supplemental-proof-export-20261012-r1/"
        "complete.json": "724ee1d7032442e192994236a28abf0cd61951ffc096f412b50c359737049d2d"})
    ok(si.E2_PATH in si.E4_COMPLETE_JSON)
    ok(len(si.T1_LAUNCH_NAMESPACES) == 5)
    ok(si.PERCEPTION_PREFIXES == {"127x04": ("/mpac/sdicks02/jobs",)})
    ok(si.GLOBAL_FORBIDDEN_PREFIXES == ("/mpac/sdicks02/repos/clasher-v4-cache",))
    for good in ("k4s-end-guard-r1-rd01-a02", "k4s-end-guard-r1-pf01", "k4s-end-guard-r12-pf99"):
        ok(si.GUARD_JOB_NAME.fullmatch(good) is not None, good)
    for bad in ("k4s-end-guard-r1", "k4s-end-guard-r0-pf01", "k4s-end-guard-r1-pf1", "k4s-end-guard-r1-rd01"):
        ok(si.GUARD_JOB_NAME.fullmatch(bad) is None, bad)
    ok(si.STRICT_END_DIR == "reports/explore/k4s-confirm/end")
    for base in si.END_BASES.values():
        si.name_gate(base, "127x03", ())                      # the END bases themselves are not forbidden names


# ---------------------------------------------------------------- policy / role construction
def test_unknown_role_refuses(base):
    p = policy([role("a", base, exact=("x.json",))])
    refusal("policy", p.role, "b")
    refusal("policy", p.role, None)
    refusal("policy", si.read_bytes, p, "nope", "x.json")


@pytest.mark.parametrize("kwargs", [
    dict(exact=(), patterns=()),                                  # declares nothing
    dict(access="readwrite", exact=("a",)),
    dict(max_size=0, exact=("a",)),
    dict(max_size=True, exact=("a",)),
    dict(max_size=1.5, exact=("a",)),
    dict(max_size=(64 << 30) + 1, exact=("a",)),
    dict(exact=("a",), exemptions=("E9",)),
    dict(exact=("a",), grants=("everything",)),
    dict(patterns=("*.json",), grants=("reporting-job-exact",)),  # grants require exact names
    dict(patterns=("*.json",), grants=("end-json-exact",)),
    dict(exact=("END-JOB.txt",), grants=("end-json-exact",)),     # END grant: .json names only
    dict(patterns=("a**",)),                                      # ** only as a whole component
    dict(exact=("../a",)),
    dict(exact=("/a",)),
    dict(exact="a.json"),                                         # a bare string is not a collection
])
def test_bad_roles_refuse(base, kwargs):
    args = dict(name="r", root=base, access="read", max_size=10)
    args.update(kwargs)
    refusal("path" if kwargs.get("exact") in (("../a",), ("/a",)) else "policy", si.Role, **args)


@pytest.mark.parametrize("root", ["relative/x", "/", "/a/../b", "/a//b", "/a/", "/a/\x00b", "/a/b\nc"])
def test_bad_role_roots_refuse(root):
    refusal("path", si.Role, name="r", root=root, access="read", max_size=1, exact=("a",))


def test_bad_role_name_refuses(base):
    for name in ("", "A", "-x", "a b", "x" * 70, 3):
        refusal("policy", si.Role, name=name, root=base, access="read", max_size=1, exact=("a",))


def test_role_is_immutable(base):
    r = role("a", base, exact=("x",))
    refusal("policy", setattr, r, "root", "/")
    ok(r.root == base)


def test_policy_checks(base):
    r = role("a", base, exact=("x",))
    refusal("policy", si.Policy, "127x99", [r])
    refusal("policy", si.Policy, HOST, [])
    refusal("policy", si.Policy, HOST, [r, role("a", base, exact=("y",))])
    refusal("policy", si.Policy, HOST, ["not a role"])
    refusal("policy", si.Policy, HOST, [r], remote="yes")
    other = "127x03" if HOST != "127x03" else "127x04"
    refusal("policy", si.Policy, other, [r])                     # local policy must run on its host
    si.Policy(other, [r], remote=True)                           # a remote policy describes another host
    refusal("name", si.Policy, HOST, [role("g", base + "/games", exact=("x",))])


def test_access_kinds_enforced(base):
    p = policy([role("w", base, access="write", exact=("x",)), role("r", base, exact=("x",))])
    refusal("policy", si.read_bytes, p, "w", "x")
    refusal("policy", si.Writer, p, "r")


# ---------------------------------------------------------------- name refusals: before ANY syscall
FORBIDDEN_RELS = [
    "games/x.json", "a/games/x.json", "a/b/games", "GAMES/x.json", "games.tmp/x.json", ".games/x",
    "hub-blocks/b.json", "a/hub-blocks", "hub-blocks.partial/x",
    "complete.json", "a/complete.json", "complete.json/x", "complete.json.tmp", ".complete.json.swp",
    "COMPLETE.JSON", "local-complete.json", "end-complete.json", "interference.json", "a/interference.json.tmp",
    "hub-ack.json", "hub-ack.returned.json", "x/hub-ack.returned.json", "end-raw.json", "end-raw.json.partial",
    "k4s-confirm-reporting-r1/launch.json", "x/k4s-confirm-replacement-r4/system-bus-admission.json",
    "k4s-end-guard-r1-pf01/a.py", "x/K4S-END-GUARD-r1-rd01-a01/a",
    "reports/explore/k4s-confirm/end/END-JOB.json", "k4s-confirm/end", "k4s-confirm/end/receipts/x.json",
    "K4S-Confirm/End/x.json",
]


@pytest.mark.parametrize("rel", FORBIDDEN_RELS)
def test_forbidden_names_refuse_with_zero_syscalls(base, rec, rel):
    p = policy([role("all", base, patterns=("**",))])
    with rec:
        refusal("name", si.read_bytes, p, "all", rel)
        refusal("name", si.open_input, p, "all", rel)
        refusal("name", si.sha256_input, p, "all", rel)
        refusal("name", si.read_json, p, "all", rel, 100)
    ok(rec.calls == [] and rec.open_attempts == [], "a syscall happened before the name refusal: %r" % rec.calls)


@pytest.mark.parametrize("path", list(si.T1_LAUNCH_NAMESPACES) + [ns + "/a/b.json" for ns in si.T1_LAUNCH_NAMESPACES]
                         + ["/mpac/sdicks02/repos/clasher-v4-cache", "/mpac/sdicks02/repos/clasher-v4-cache/x"])
def test_t1_and_cache_namespaces_refuse_on_every_host(path):
    for host in ("127x03", "127x04", "127x05"):
        refusal("name", si.name_gate, path, host, si.GRANTS)     # no grant lifts these


def test_perception_root_on_04_only():
    for path in ("/mpac/sdicks02/jobs", "/mpac/sdicks02/jobs/clasher", "/mpac/sdicks02/jobs/clasher/k4s-end-r1/x"):
        refusal("name", si.name_gate, path, "127x04", si.GRANTS)
        si.name_gate(path, "127x03", si.GRANTS)
    si.name_gate("/mpac/sdicks02/jobs-k4s/k4s-end-r1/x", "127x04", ())   # 04's K4S root is not perception


@pytest.mark.parametrize("rel", ["", ".", "..", "a/../b", "./a", "a/.", "a//b", "a/", "/abs", "a\x00b", "a\\b",
                                 "a\nb", "a\x7fb"])
def test_malformed_relative_paths_refuse_with_zero_syscalls(base, rec, rel):
    p = policy([role("all", base, patterns=("**",))])
    with rec:
        refusal("path", si.read_bytes, p, "all", rel)
    ok(rec.calls == [])


def test_unknown_host_refuses_in_name_gate():
    refusal("policy", si.name_gate, "/a/b", "laptop", ())


def test_grants_lift_only_their_namespace():
    rj = "/mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/system-bus-admission.json"
    si.name_gate(rj, "127x03", ("reporting-job-exact",))
    refusal("name", si.name_gate, rj, "127x03", ("guard-job", "end-json-exact"))
    refusal("name", si.name_gate, rj.replace("system-bus-admission.json", "games/x.json"), "127x03", si.GRANTS)
    refusal("name", si.name_gate, rj.replace("system-bus-admission.json", "complete.json"), "127x03", si.GRANTS)
    end = "/r/reports/explore/k4s-confirm/end/END-JOB.json"
    si.name_gate(end, "127x05", ("end-json-exact",))
    refusal("name", si.name_gate, end, "127x05", ("reporting-job-exact", "guard-job"))
    refusal("name", si.name_gate, "/r/k4s-confirm/end/notes.txt", "127x05", ("end-json-exact",))
    refusal("name", si.name_gate, "/r/k4s-confirm/end", "127x05", ("end-json-exact",))
    refusal("name", si.name_gate, "/r/k4s-confirm/end/end-raw.json", "127x05", si.GRANTS)
    guard = "/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf01/t1-freeze.json"
    si.name_gate(guard, "127x04", ("guard-job",))
    refusal("name", si.name_gate, guard, "127x04", ("reporting-job-exact",))


def test_e4_leaf_flag_exempts_only_a_final_complete_json():
    si.name_gate("/r/a/complete.json", "127x05", (), e4_leaf=True)
    for path in ("/r/complete.json/x", "/r/games/complete.json", "/r/hub-ack.json/complete.json",
                 "/r/a/complete.json.tmp", "/r/a/end-raw.json", "/r/k4s-confirm-x/complete.json"):
        refusal("name", si.name_gate, path, "127x05", (), e4_leaf=True)


def test_lookalike_names_are_not_outcomes():
    for path in ("/r/main01-complete.json", "/r/hub-ack-smoke-0001.json", "/r/incomplete/x.json",
                 "/r/k4s-confirm/end-guard-admissions/127x03-system-bus-admission.json", "/r/endgames.txt",
                 "/r/k4s-confirm/run-r1/x.json", "/r/k4s-end-r1/x"):
        si.name_gate(path, "127x05", ())


# ---------------------------------------------------------------- allowlist
def test_allowlist_exact_and_component_patterns(base, rec):
    p = policy([role("r", base, exact=("a/x.json",), patterns=("p/*.json", "deep/**/z.txt"))])
    ok(p.role("r").allows("a/x.json") and p.role("r").allows("p/q.json"))
    ok(p.role("r").allows("deep/z.txt") and p.role("r").allows("deep/1/2/z.txt"))
    ok(not p.role("r").allows("p/s/q.json"))                     # '*' never crosses '/'
    ok(not p.role("r").allows("a/y.json") and not p.role("r").allows("deep/z.txtx"))
    with rec:
        refusal("allowlist", si.read_bytes, p, "r", "a/y.json")
        refusal("allowlist", si.read_bytes, p, "r", "p/s/q.json")
    ok(rec.calls == [])
    ok(si.gate_names(p, "r", "a/x.json") == base + "/a/x.json")
