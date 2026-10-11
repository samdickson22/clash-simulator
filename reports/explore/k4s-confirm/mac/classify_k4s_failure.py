#!/usr/bin/env python3
"""Mechanical K4S Mac session classification and cross-session reduction (r3 §1.4 integrity).

* ``classify``: reads one sealed K4S receipt directory (and, optionally, the TIERS session
  it ran inside) and assigns exactly one category from receipts only:
  - ``valid``: complete, no technical-failure evidence;
  - ``gate-failure``: an exactness/agreement gate failed. A valid session; no repeat;
  - ``technical-failure``: one of the pre-listed technical failures (TIERS addendum §F):
    harness/load exception, host sleep/reboot, CPU speed limit < 100% before the K4S
    load starts, a foreign process > 1 core for > 60 s, a staging pin mismatch. Invalid;
    one repeat may be authorised;
  - ``invalid-tiers-session``: the K4S block ran inside a session that TIERS's own frozen
    classifier marks technically invalid (RECHECK-r3 R3). Invalid; does not use up the
    K4S repeat allowance;
  - ``precondition-refusal``: nothing was measured; not a session.
  Low speed, failed gates or noisy values are never technical failures. A human cannot
  declare one.
* ``reduce``: minimum r and the worst value of every gate input across valid sessions,
  then the frozen §1.4 mapping.

It never writes into, re-runs or re-classifies anything TIERS owns: TIERS's classifier is
imported read-only and only its pure ``classify`` function is called. Output goes to a
fresh directory that may not overlap any TIERS path or the classified receipts.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k4s_logic as L  # noqa: E402

PRE_LOAD_PHASES = ("K0", "K0-census", "K1")
AUTHORITY = "classification only; a repeat still needs separate session authorization"


def classify_records(*, failure_error=None, refusal=None, capacity_rows=(), complete=None,
                     tiers_classification=None, cleanup_error=None, status="complete"):
    """``status`` is the sealed receipt-manifest status; it must agree with the receipts."""
    reasons = []
    base = dict(final=False, authority=AUTHORITY, tiers_classification_untouched=True)
    if refusal is not None:
        if status != "refused" or failure_error:
            return dict(base, category="technical-failure", session=True, valid=False, technical_repeat_candidate=True,
                        counts_toward_repeat_allowance=True,
                        reasons=["sealed status disagrees with the refusal receipt (" + str(status) + ")"])
        return dict(base, category="precondition-refusal", session=False, valid=False,
                    technical_repeat_candidate=False, counts_toward_repeat_allowance=False,
                    reasons=[refusal.get("error", "refused")])
    if tiers_classification is not None and tiers_classification.get("technical_repeat_candidate"):
        return dict(base, category="invalid-tiers-session", session=True, valid=False,
                    technical_repeat_candidate=True, counts_toward_repeat_allowance=False,
                    reasons=["K4S block inside a TIERS-technically-invalid session"]
                    + list(tiers_classification.get("reasons", [])))
    error = failure_error or ""
    gate_failure = any(word in error for word in L.TIERS_GATE_FAILURE_WORDS)
    if error and not gate_failure:
        if "Pin mismatch" in error or "manifest SHA mismatch" in error:
            reasons.append("staging pin mismatch")
        elif "Traceback (most recent call last)" in error:
            reasons.append("harness/load exception")
    if cleanup_error:
        reasons.append("harness/load cleanup exception (cleanup-failure.json)")
    if any(p.get("foreign_over_one_core_seconds", 0) > 60 for r in capacity_rows for p in r.get("processes", ())):
        reasons.append("foreign process above one core for over 60 seconds")
    boot = {r["boottime"]["stdout"] for r in capacity_rows if "boottime" in r}
    if len(boot) > 1 or any(abs(r.get("wall_monotonic_offset_change_seconds", 0)) > 3 for r in capacity_rows):
        reasons.append("host sleep/reboot clock evidence")
    pre = [r for r in capacity_rows if r.get("phase") in PRE_LOAD_PHASES]
    if any(any(int(x) < 100 for x in re.findall(r"CPU_Speed_Limit\s*[=:]\s*(\d+)",
                                                  (r.get("thermal") or {}).get("stdout", ""))) for r in pre):
        reasons.append("pre-load CPU speed limit below 100 percent")
    if gate_failure:
        # Exactness evidence governs and never earns a repeat. The sealed status and any cleanup
        # exception are reconciled explicitly (recorded), never allowed to turn it into a pass or
        # a technical repeat. Admission forces gate 0 false for every such session (read_entry).
        notes = ["exactness gate failure (gate 0)"]
        if status != "failed":
            notes.append("sealed status " + str(status) + " disagrees with the failure receipt; exactness governs")
        if complete and complete.get("completed") is True:
            notes.append("failure after the summary/completion receipt; any written summary is superseded (gate 0 false)")
        notes += [r for r in reasons if "cleanup" in r]
        return dict(base, category="gate-failure", session=True, valid=True, technical_repeat_candidate=False,
                    counts_toward_repeat_allowance=False, reasons=notes, gate0_failed=True)
    if reasons:
        return dict(base, category="technical-failure", session=True, valid=False, technical_repeat_candidate=True,
                    counts_toward_repeat_allowance=True, reasons=reasons)
    if error or not (complete and complete.get("completed") is True):
        return dict(base, category="technical-failure", session=True, valid=False, technical_repeat_candidate=True,
                    counts_toward_repeat_allowance=True, reasons=["incomplete session without a gate failure"])
    if status != "complete":
        return dict(base, category="technical-failure", session=True, valid=False, technical_repeat_candidate=True,
                    counts_toward_repeat_allowance=True,
                    reasons=["sealed status " + str(status) + " disagrees with the completion receipt"])
    return dict(base, category="valid", session=True, valid=True, technical_repeat_candidate=False,
                counts_toward_repeat_allowance=False, reasons=[])


def _load(directory, name, files):
    if name not in files:
        return None
    text = (directory / name).read_text()
    return json.loads(text.splitlines()[0]) if name.endswith(".json") else text


def classify(directory, tiers_dir=None, tiers_sha256=None, tiers_classify=None):
    directory = Path(directory)
    manifest_path = directory / "receipt-manifest.json"
    manifest = json.loads(manifest_path.read_text().splitlines()[0])
    L.verify_pinned(directory, manifest["files"], "K4S receipts")
    files = manifest["files"]
    failure = _load(directory, "failure.json", files)
    cleanup = _load(directory, "cleanup-failure.json", files)
    refusal = _load(directory, "refusal.json", files)
    complete = _load(directory, "k4s-complete.json", files)
    capacity = _load(directory, "capacity.jsonl", files)
    rows = [json.loads(line) for line in capacity.splitlines() if line.endswith("}")] if capacity else []
    tiers_classification = None
    if tiers_dir is not None:
        tiers_dir = Path(tiers_dir)
        if L.sha(tiers_dir / "receipt-manifest.json") != tiers_sha256:
            raise L.PreconditionRefusal("TIERS receipt SHA mismatch")
        summary = _load(directory, "k4s-mac-summary.json", files) or _load(directory, "k4s-preconditions.json", files)
        named = [s["receipt_manifest_sha256"] for s in ((summary or {}).get("tiers_inputs") or (summary or {}).get("tiers") or {}).get("sessions", [])]
        if named and tiers_sha256 not in named:
            raise L.PreconditionRefusal("K4S session did not use this TIERS session")
        if tiers_classify is None:
            sys.path.insert(0, str(L.REPO_ROOT / L.E4V3_REL))
            from classify_failure import classify as tiers_classify
        tiers_classification = tiers_classify(tiers_dir)
    result = classify_records(failure_error=(failure or {}).get("error"), refusal=refusal, capacity_rows=rows,
                              complete=complete, tiers_classification=tiers_classification,
                              cleanup_error=(cleanup or {}).get("error", "cleanup failure") if cleanup is not None else None,
                              status=manifest["status"])
    return dict(result, source_manifest_sha256=L.sha(manifest_path), status=manifest["status"],
                tiers_receipt_manifest_sha256=tiers_sha256)


def gate_failure_summary(tiers_inputs, parts=None):
    """A valid session that stopped on an exactness gate failure: gate 0 failed, nothing else.

    Any summary the session wrote before the failure is superseded: its measurements are not
    reduced, and only its gate 0 parts are carried (all forced together with the failure part)."""
    parts = dict(parts or {}, k4s_exactness_gate_failure=False)
    return dict(tiers_inputs=tiers_inputs, provisional=True,
                gate_inputs=dict(gate0=dict(passes=False, parts=parts), r_k4s=None))


def reduce_sessions(entries, c_star):
    """entries: [(summary, classification)]. Worst inputs across valid sessions, then §1.4."""
    valid = [(s, c) for s, c in entries if c["valid"] is True]
    if not valid:
        raise L.GateInputError("No valid K4S session to reduce")
    for s, c in valid:
        if (c.get("category") == "gate-failure" or c.get("gate0_failed") is True) \
                and s["gate_inputs"]["gate0"]["passes"] is not False:
            raise L.GateInputError("A gate-failure classification contradicts a passing gate 0 summary")
    tiers = valid[0][0]["tiers_inputs"]
    if any(L.canonical(s["tiers_inputs"]) != L.canonical(tiers) for s, _ in valid):
        raise L.GateInputError("Valid sessions read different TIERS inputs; reduce per TIERS final verdict first")
    measured = [s["gate_inputs"] for s, c in valid if s["gate_inputs"].get("r_k4s") is not None]
    gate0_failed = any(s["gate_inputs"]["gate0"]["passes"] is not True or c.get("gate0_failed") is True
                       for s, c in valid)
    if gate0_failed or not measured:
        parts = {}
        for s, _ in valid:
            for k, v in s["gate_inputs"]["gate0"].get("parts", {}).items():
                parts[k] = parts.get(k, True) and v is True
        inputs = dict(gate0=dict(passes=False, parts=parts), poll_p99_seconds=None)
        mapping = dict(cells=None, provisional_cell=None, gate6_trail=[], c_M_k4s=None, mac_infeasible=True,
                       reason="gate 0 failed in a valid session")
    else:
        inputs = L.combine_k4s_sessions(measured)
        mapping = L.map_cell(inputs)
    final = L.final_cell(tiers, mapping, c_star)
    return dict(valid_sessions=len(valid), excluded_sessions=len(entries) - len(valid), gate_inputs=inputs,
                cell_mapping=mapping, tiers_inputs=tiers, kill=L.kill_flags(inputs, tiers), **final,
                provisional=any(s.get("provisional", True) for s, _ in valid), final=False,
                rule="minimum r and worst value of every gate input across valid K4S sessions (r3 §1.4)")


SESSION_SCOPES = ("K4S-MAC-REPLAY", "K4S-LINUX-DRY-RUN")
CLASSIFICATION_SCOPE = "K4S-MECHANICAL-FAILURE-CLASSIFICATION"


def read_entry(session, digest, cdir, cdigest):
    """One (summary, classification) pair, each read only from its own verified seal.

    The classification seal must be complete and must include classification.json, whose
    bytes are re-hashed against that seal before they are read; it must name this session's
    seal. The session's summary/preconditions are consumed only if listed in the session's
    own verified inventory (an unlisted file on disk is refused, never read).
    """
    session, cdir = Path(session), Path(cdir)
    cmanifest = L.read_sealed(cdir, cdigest, scopes=(CLASSIFICATION_SCOPE,), statuses=("complete",),
                              required=("classification.json",), label="classification")
    classification = L.read_sealed_json(cdir, cmanifest, "classification.json")
    if classification.get("source_manifest_sha256") != digest:
        raise L.PreconditionRefusal("Classification belongs to a different session")
    smanifest = L.read_sealed(session, digest, scopes=SESSION_SCOPES, label="K4S session")
    if classification.get("status") != smanifest["status"]:
        raise L.PreconditionRefusal("Classification status disagrees with the session seal")
    for name in ("k4s-mac-summary.json", "k4s-preconditions.json"):
        if (session / name).exists() and name not in smanifest["files"]:
            raise L.PreconditionRefusal("Session file is not in its own sealed inventory: " + name)
    summary = L.read_sealed_json(session, smanifest, "k4s-mac-summary.json")
    files = smanifest["files"]
    if classification["valid"] is not True:
        return summary, classification
    if classification.get("category") == "valid":
        # Re-derived from the session's own seal: complete status, a completion receipt, and no
        # failure, cleanup-failure or refusal evidence.
        complete = L.read_sealed_json(session, smanifest, "k4s-complete.json")
        if smanifest["status"] != "complete" or not (complete and complete.get("completed") is True) \
                or any(name in files for name in ("failure.json", "cleanup-failure.json", "refusal.json")):
            raise L.PreconditionRefusal("A 'valid' classification contradicts the session's sealed status/receipts")
        if summary is None:
            raise L.GateInputError("Valid session without a summary")
        return summary, classification
    if classification.get("category") != "gate-failure" or classification.get("gate0_failed") is not True:
        raise L.PreconditionRefusal("Unknown valid classification category")
    # A gate failure (incl. one raised AFTER a passing summary was written, e.g. the post-run bundle
    # re-validation): re-read the sealed failure trace, then force gate 0 false. Any earlier summary is
    # superseded; only its TIERS inputs and gate 0 parts are kept.
    failure = L.read_sealed_json(session, smanifest, "failure.json")
    if not failure or not any(w in failure.get("error", "") for w in L.TIERS_GATE_FAILURE_WORDS):
        raise L.PreconditionRefusal("Gate-failure classification without a sealed exactness failure trace")
    if summary is not None:
        parts = (summary.get("gate_inputs") or {}).get("gate0", {}).get("parts", {})
        return gate_failure_summary(summary["tiers_inputs"], parts), classification
    pre = L.read_sealed_json(session, smanifest, "k4s-preconditions.json")
    if pre is None:
        raise L.PreconditionRefusal("Gate-failure session lacks its sealed preconditions")
    return gate_failure_summary(pre["tiers"]), classification


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--receipts", type=Path, required=True)
    c.add_argument("--tiers-receipts", type=Path)
    c.add_argument("--tiers-receipt-sha256")
    c.add_argument("--output", type=Path, required=True)
    r = sub.add_parser("reduce")
    r.add_argument("--session", type=Path, action="append", required=True)
    r.add_argument("--session-sha256", action="append", required=True)
    r.add_argument("--classification", type=Path, action="append", required=True)
    r.add_argument("--classification-sha256", action="append", required=True)
    r.add_argument("--c-star", default="0.9")
    r.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "classify":
        forbidden = L.forbidden_roots(L.REPO_ROOT, [p for p in (args.tiers_receipts,) if p], None, [args.receipts])
        store = L.K4SStore(args.output, CLASSIFICATION_SCOPE, forbidden)
        try:
            store.write("classification.json", classify(args.receipts, args.tiers_receipts, args.tiers_receipt_sha256))
            store.seal("complete")
        except BaseException:
            store.seal("failed")
            raise
        return 0
    counts = {len(args.session), len(args.session_sha256), len(args.classification), len(args.classification_sha256)}
    if len(counts) != 1:
        raise L.PreconditionRefusal("Every session needs its receipt SHA and its classification receipt + SHA")
    pairs = list(zip(args.session, args.session_sha256))
    cpairs = list(zip(args.classification, args.classification_sha256))
    store = L.K4SStore(args.output, "K4S-SESSION-REDUCTION",
                       L.forbidden_roots(L.REPO_ROOT, (), None, [p for p, _ in pairs] + [p for p, _ in cpairs]))
    try:
        entries = [read_entry(session, digest, cdir, cdigest) for (session, digest), (cdir, cdigest) in zip(pairs, cpairs)]
        store.write("k4s-mac-final.json", reduce_sessions(entries, args.c_star))
        store.seal("complete")
    except BaseException:
        store.seal("failed")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
