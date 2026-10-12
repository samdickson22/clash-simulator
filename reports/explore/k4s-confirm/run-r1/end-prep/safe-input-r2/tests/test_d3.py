"""Ruling D3: the S6-only hash-only role for exactly end-raw.json / end-complete.json inside a SEALED attempt directory
under the declared S6 receive parent. Synthetic files under tmp_path only (D3_RECEIVE_BASE is patched to tmp)."""
import hashlib
import os

import pytest

from conftest import canary_unchanged, ident, make_canary, make_file, ok, policy, refusal, role, si

RAW = b'{"synthetic": "raw"}\n'
DONE = b'{"synthetic": "complete"}\n'


@pytest.fixture
def received(base, monkeypatch):
    recv = os.path.join(base, "end-received")
    monkeypatch.setattr(si, "D3_RECEIVE_BASE", recv)
    root = os.path.join(recv, "127x03")
    data = os.path.join(root, "k4s-end-r1-rd01-a01", si.D3_SEALED_DIR)
    make_file(os.path.join(data, "receipt-manifest.json"), b'{"scope": "K4S-END-REFERENCE"}\n')
    make_file(os.path.join(data, "receipt-manifest.sha256"), b"0" * 64 + b"  receipt-manifest.json\n")
    make_file(os.path.join(data, "end-raw.json"), RAW)
    make_file(os.path.join(data, "sub", "end-complete.json"), DONE)
    return root


RAW_REL = "k4s-end-r1-rd01-a01/durable-measurement/end-raw.json"
DONE_REL = "k4s-end-r1-rd01-a01/durable-measurement/sub/end-complete.json"


def d3_policy(root, name="s6-sealed-end", exact=(RAW_REL, DONE_REL)):
    return policy([role(name, root, exact=exact, exemptions=("D3",), max_size=1 << 20)])


def test_d3_hash_only_happy_path(received, rec):
    p = d3_policy(received)
    with rec:
        got = si.hash_sealed_end_member(p, "s6-sealed-end", RAW_REL, hashlib.sha256(RAW).hexdigest())
    ok(got == {"path": RAW_REL, "sha256": hashlib.sha256(RAW).hexdigest(), "size": len(RAW)})
    seal = os.path.join(received, "k4s-end-r1-rd01-a01", si.D3_SEALED_DIR, "receipt-manifest.json")
    ok(ident(seal) not in rec.read_inodes, "a seal file was read (only stat/open-gated)")
    got = si.hash_sealed_end_member(p, "s6-sealed-end", DONE_REL, hashlib.sha256(DONE).hexdigest())
    ok(got["size"] == len(DONE) and "data" not in got and "bytes" not in got)


def test_d3_seal_sha_mismatch_and_missing_seal(received):
    p = d3_policy(received)
    refusal("sha", si.hash_sealed_end_member, p, "s6-sealed-end", RAW_REL, "0" * 64)
    refusal("policy", si.hash_sealed_end_member, p, "s6-sealed-end", RAW_REL, None)
    refusal("policy", si.hash_sealed_end_member, p, "s6-sealed-end", RAW_REL, "A" * 64)
    os.unlink(os.path.join(received, "k4s-end-r1-rd01-a01", si.D3_SEALED_DIR, "receipt-manifest.sha256"))
    refusal("missing", si.hash_sealed_end_member, p, "s6-sealed-end", RAW_REL, hashlib.sha256(RAW).hexdigest())


def test_d3_hard_linked_member_canary_never_opened(base, received, rec):
    canary = make_canary(base)
    target = os.path.join(received, "k4s-end-r1-rd01-a01", si.D3_SEALED_DIR, "end-raw.json")
    os.unlink(target)
    os.link(canary, target)
    with rec:
        refusal("nlink", si.hash_sealed_end_member, d3_policy(received), "s6-sealed-end", RAW_REL, "0" * 64)
    ok(not rec.touched(ident(canary)) and canary_unchanged(canary))
    os.unlink(target)
    os.symlink(canary, target)
    refusal("symlink", si.hash_sealed_end_member, d3_policy(received), "s6-sealed-end", RAW_REL, "0" * 64)


def test_d3_hard_linked_seal_refuses(base, received):
    seal = os.path.join(received, "k4s-end-r1-rd01-a01", si.D3_SEALED_DIR, "receipt-manifest.json")
    os.link(seal, os.path.join(base, "seal-alias"))
    refusal("nlink", si.hash_sealed_end_member, d3_policy(received), "s6-sealed-end", RAW_REL,
            hashlib.sha256(RAW).hexdigest())


def test_d3_never_through_ordinary_reads(received, rec):
    p = d3_policy(received)
    with rec:
        for fn in (si.read_bytes, si.sha256_input, si.open_input):
            refusal("name", fn, p, "s6-sealed-end", RAW_REL)
        refusal("name", si.read_json, p, "s6-sealed-end", RAW_REL, 1024)
        refusal("name", si.gate_names, p, "s6-sealed-end", RAW_REL)
        refusal("policy", si.walk_tree, policy([role("plain", received, patterns=("**",))]), "nope")
    ok(rec.calls == [] and rec.open_attempts == [])
    plain = policy([role("s6-plain", received, patterns=("**",))])
    refusal("name", si.walk_tree, plain, "s6-plain")                   # the walk refuses the name, no pruning
    refusal("exemption", si.hash_sealed_end_member, plain, "s6-plain", RAW_REL, "0" * 64)
    exact_only = policy([role("s6-exact", received, exact=(RAW_REL,))])      # declares the name, lacks D3
    refusal("exemption", si.hash_sealed_end_member, exact_only, "s6-exact", RAW_REL, hashlib.sha256(RAW).hexdigest())


@pytest.mark.parametrize("kwargs,code", [
    (dict(name="s5-sealed"), "policy"),                                # S6 only
    (dict(patterns=("**",), exact=()), "policy"),
    (dict(grants=("end-claim-exact",)), "policy"),
    (dict(exemptions=("D3", "E4")), "policy"),
    (dict(access="write"), "policy"),
    (dict(sub="127x05"), "policy"),                                    # only the 03/04 receive parents
    (dict(sub="127x03/k4s-end-r1-rd01-a01"), "policy"),                # root must be the parent, not the attempt
    (dict(exact=("k4s-end-r1-rd01-a01/end-raw.json",)), "policy"),     # not inside durable-measurement
    (dict(exact=("k4s-end-r1-rd01-a01/durable-measurement/metrics.json",)), "policy"),
    (dict(exact=("k4s-end-r1-rd01-a01/durable-measurement/END-RAW.json",)), "policy"),
    (dict(exact=("k4s-end-r1-rd01-a01/durable-measurement/end-raw.json.tmp",)), "policy"),
    (dict(exact=("k4s-end-r1-rd01-a01/other/end-raw.json",)), "policy"),
])
def test_d3_role_construction(received, kwargs, code):
    args = dict(name="s6-sealed-end", root=received, access="read", max_size=1 << 20, exact=(RAW_REL,),
                exemptions=("D3",))
    sub = kwargs.pop("sub", None)
    if sub is not None:
        args["root"] = os.path.join(si.D3_RECEIVE_BASE, sub)
    args.update(kwargs)
    refusal(code, si.Role, **args)


def test_d3_name_gate_still_applies_to_other_components(received):
    bad = "games/durable-measurement/end-raw.json"
    r = si.Role(name="s6-g", root=received, access="read", max_size=1 << 20, exact=(bad,), exemptions=("D3",))
    refusal("name", si.hash_sealed_end_member, policy([r]), "s6-g", bad, "0" * 64)   # D3 lifts only the leaf
    r = si.Role(name="s6-x", root=received, access="read", max_size=1 << 20,
                exact=("attempt-01.json-x/durable-measurement/end-raw.json",), exemptions=("D3",))
    refusal("name", si.hash_sealed_end_member, policy([r]), "s6-x",
            "attempt-01.json-x/durable-measurement/end-raw.json", "0" * 64)  # END-claim family in the attempt name
    r = si.Role(name="s6-y", root=received, access="read", max_size=1 << 20,
                exact=("Games-r1/durable-measurement/end-raw.json",), exemptions=("D3",))
    refusal("name", si.hash_sealed_end_member, policy([r]), "s6-y", "Games-r1/durable-measurement/end-raw.json",
            "0" * 64)
