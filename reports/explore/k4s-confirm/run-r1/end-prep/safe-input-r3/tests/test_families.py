"""r2 shared family denylist (ruling P2-4, S4-R3-F2): case-insensitive name FAMILIES, prefix/suffix variants, the
two classes (OUTCOME never grantable; END-CLAIM only via the exact-name grant), and refusal before any syscall."""
import os

import pytest

from conftest import HOST, ok, policy, refusal, role, si

OUTCOME_VARIANTS = {
    "games": ["games", "GAMES", "Games", ".games", "games.tmp", "games-old", "old-games", "x_games_y", "games2",
              "games~", "k4s-games"],
    "hub-blocks": ["hub-blocks", "HUB-BLOCKS", "hub_blocks", "hubblocks", "hub-block", ".hub-blocks.partial",
                   "old-hub-blocks"],
    "complete-json": ["complete.json", "COMPLETE.JSON", "Complete.Json", "complete.json.tmp", ".complete.json.swp",
                      "complete-v2.json", "local-complete.json", "end-complete.json", "tiers-complete.json",
                      "main01-complete.json", "fits_x_complete.json", "incomplete.json", "complete.jsonl"],
    "interference-json": ["interference.json", "INTERFERENCE.JSON", "interference-r2.json", "old-interference.json",
                          ".interference.json.tmp"],
    "hub-ack-json": ["hub-ack.json", "hub-ack.returned.json", "HUB-ACK.JSON", "hub_ack.json", "huback.json",
                     "hub-ack-smoke-0001.json", "x-hub-ack.json.tmp"],
    "end-raw-json": ["end-raw.json", "END-RAW.JSON", "end_raw.json", "endraw.json", "end-raw-copy.json",
                     "end-raw.json.partial", ".end-raw.json"],
}
END_CLAIM_VARIANTS = {
    "end-job": ["END-JOB.json", "end-job.json", "END_JOB.json", "endjob.json", "END-JOB.json.tmp", ".END-JOB.json",
                "x-END-JOB.json", "END-JOBS.json"],
    "end-final": ["END-FINAL.json", "end-final.json", "END_FINAL", "x.END-FINAL.json", "END-FINAL-r2.json"],
    "attempt-json": ["attempt-00.json", "ATTEMPT-01.JSON", "attempt_00.json", "attempt-claim.json",
                     ".attempt-00.json.tmp", "x-attempt-00.json"],
}
NOT_IN_ANY_FAMILY = ["endgames", "gamestate.py", "minigames", "game-001.json", "complete", "complete.txt",
                     "incomplete", "attempt1.log", "attempt.json", "backend-jobs.py", "send-jobs", "end-raw-phases",
                     "interference.txt", "hub-ack", "notes.json", "k4s-end-r1", "end-received"]


@pytest.mark.parametrize("family,name", [(f, n) for f, names in OUTCOME_VARIANTS.items() for n in names])
def test_outcome_family_variants(family, name):
    ok(si.outcome_family(name) == family, "%r -> %r" % (name, si.outcome_family(name)))
    for path in ("/r/" + name, "/r/" + name + "/x.py", "/r/a/" + name + "/b/c.txt"):
        refusal("name", si.name_gate, path, "127x05", si.GRANTS)       # no grant can lift an outcome family


@pytest.mark.parametrize("family,name", [(f, n) for f, names in END_CLAIM_VARIANTS.items() for n in names])
def test_end_claim_family_variants(family, name):
    ok(si.end_claim_family(name) == family and si.outcome_family(name) is None, name)
    refusal("name", si.name_gate, "/r/" + name, "127x05", ("reporting-job-exact", "end-json-exact", "guard-job"))
    si.name_gate("/r/" + name, "127x05", ("end-claim-exact",))           # only the exact-name claim grant lifts it


@pytest.mark.parametrize("name", NOT_IN_ANY_FAMILY)
def test_names_outside_every_family(name):
    ok(si.outcome_family(name) is None and si.end_claim_family(name) is None, name)
    si.name_gate("/r/" + name, "127x05", ())


@pytest.mark.parametrize("name", [n for names in OUTCOME_VARIANTS.values() for n in names[:4]]
                         + [n for names in END_CLAIM_VARIANTS.values() for n in names[:3]])
def test_family_names_refuse_before_any_syscall_in_every_api(base, rec, name):
    p = policy([role("all", base, patterns=("**",), exemptions=("E1", "E4")),
                role("w", base, access="write", patterns=("**",))])
    with rec:
        for rel in (name, "a/" + name, name + "/b.json"):
            refusal("name", si.read_bytes, p, "all", rel)
            refusal("name", si.sha256_input, p, "all", rel)
            refusal("name", si.open_input, p, "all", rel)
            refusal("name", si.check_absent, p, "all", rel)
            refusal("name", si.gate_names, p, "all", rel)
            refusal("name", si.build_remote_request, policy([role("h", base, patterns=("**",))], remote=True),
                    [{"role": "h", "rel": rel, "kind": "file"}])
    ok(rec.calls == [] and rec.open_attempts == [], "a syscall happened before the name refusal: %r" % rec.calls)


def test_family_inside_role_roots_and_writes(base):
    for name in ("games", "x-hub-ack.json", "END-FINAL.json", "attempt-00.json"):
        refusal("name", si.Policy, HOST, [role("r", base + "/" + name, exact=("x",))])
    p = policy([role("w", base, access="write", patterns=("**",))])
    with si.Writer(p, "w") as w:
        for rel in ("Games", "a.COMPLETE.json", "end-raw.json.tmp", "END-JOB.json", "attempt-03.json"):
            refusal("name", w.mkdir_excl, rel)
            refusal("name", w.create_excl, rel, b"x")
    ok(os.listdir(base) == [], "a forbidden name was created")


def test_claim_grant_is_exact_names_only(base):
    refusal("policy", si.Role, name="r", root=base, access="read", max_size=1, patterns=("registry/*.json",),
            grants=("end-claim-exact",))
    p = policy([role("s6-receive", base, exact=("registry/attempt-00.json", "durable-measurement/attempt-claim.json"),
                     grants=("end-claim-exact",))])
    os.makedirs(os.path.join(base, "registry"))
    with open(os.path.join(base, "registry", "attempt-00.json"), "wb") as stream:
        stream.write(b'{"attempt": 0}')
    ok(si.read_json(p, "s6-receive", "registry/attempt-00.json", 1024) == {"attempt": 0})
    refusal("allowlist", si.read_bytes, p, "s6-receive", "registry/attempt-01.json")
    refusal("name", si.read_bytes, p, "s6-receive", "registry/end-raw.json")     # outcome: never via the grant


def test_e4_and_d3_leaf_flags_are_exact_and_final_only():
    si.name_gate("/r/a/complete.json", "127x05", (), e4_leaf=True)
    si.name_gate("/r/a/end-raw.json", "127x05", (), d3_leaf=True)
    si.name_gate("/r/a/end-complete.json", "127x05", (), d3_leaf=True)
    for path, flags in (("/r/a/Complete.json", dict(e4_leaf=True)), ("/r/a/complete.json.tmp", dict(e4_leaf=True)),
                        ("/r/complete.json/x", dict(e4_leaf=True)), ("/r/a/end-complete.json", dict(e4_leaf=True)),
                        ("/r/a/end-raw.json", dict(e4_leaf=True)), ("/r/a/complete.json", dict(d3_leaf=True)),
                        ("/r/a/END-RAW.json", dict(d3_leaf=True)), ("/r/a/end-raw.json.tmp", dict(d3_leaf=True)),
                        ("/r/end-raw.json/x", dict(d3_leaf=True)), ("/r/games/end-raw.json", dict(d3_leaf=True)),
                        ("/r/a/interference.json", dict(e4_leaf=True, d3_leaf=True)),
                        ("/r/a/hub-ack.json", dict(e4_leaf=True, d3_leaf=True))):
        refusal("name", si.name_gate, path, "127x05", si.GRANTS, **flags)


def test_families_are_in_the_fingerprint():
    ok(si.OUTCOME_FAMILIES[0][0] == "games" and len(si.OUTCOME_FAMILIES) == 6 and len(si.END_CLAIM_FAMILIES) == 3)
    ok("end-claim-exact" in si.GRANTS and set(si.EXEMPTIONS) == {"E1", "E4", "D3", "E5"})
