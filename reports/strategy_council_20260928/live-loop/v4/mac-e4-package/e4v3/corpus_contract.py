"""T1 ba3dc8b0 public row contract; no suspended private work is admitted."""
import math
import bisect
from receipts import TIERS

REQUIRED_ROW = ("id", "tier", "seed", "info", "reserved_packet", "pending", "opponent_elixir",
    "d1_before", "d1_events", "d1", "policy_rng_state", "candidate_rng_state", "belief_before",
    "belief_had_suspended_transaction", "belief_rng_state", "opponent", "root_rng_state",
    "root", "root_digest", "strata")


def validate_row(row, tier=None):
    if not isinstance(row, dict) or set(row) != set(REQUIRED_ROW):
        missing = set(REQUIRED_ROW)-set(row) if isinstance(row,dict) else set(REQUIRED_ROW)
        extra = set(row)-set(REQUIRED_ROW) if isinstance(row,dict) else set()
        raise ValueError("Public corpus allowlist: missing="+repr(sorted(missing))+" extra="+repr(sorted(extra)))
    if row["tier"] not in TIERS or tier is not None and row["tier"] != tier:
        raise ValueError("Wrong own-tier reference row")
    if not isinstance(row["id"],str) or not row["id"] or type(row["seed"]) is not int:
        raise ValueError("Corpus needs string identity and integer seed")
    if not isinstance(row["d1_before"],dict) or "builder" in row["d1_before"]:
        raise ValueError("d1_before is a tracker state dictionary excluding builder")
    if getattr(row["belief_before"],"_pending",None) is not None:
        raise ValueError("Only committed posterior copies with _pending=None are admitted")
    if type(row["belief_had_suspended_transaction"]) is not bool:
        raise ValueError("Suspended-transaction disclosure must be Boolean")
    strata=row["strata"]
    if not isinstance(strata,dict) or set(strata) != {"elixir","legal_play_count","bins"}:
        raise ValueError("Strata allowlist: elixir, legal_play_count, bins only")
    if not math.isfinite(float(strata["elixir"])) or type(strata["legal_play_count"]) is not int or strata["legal_play_count"] < 0:
        raise ValueError("Invalid preregistered strata")
    if strata["bins"] != [bisect.bisect_right([3,6],strata["elixir"]),bisect.bisect_right([1,128],strata["legal_play_count"])]:
        raise ValueError("Stratum bins do not match the preregistered elixir/legal-count bins")
    if not math.isfinite(float(row["opponent_elixir"])):
        raise ValueError("Opponent elixir must be public and finite")


def validate_capture_receipt(bundle,manifest,backend):
    """Retain the excluded capture's health and selected-state SHA inventory."""
    import json
    from pathlib import Path
    name=manifest["corpus_receipt"]
    if name not in manifest["files"]:
        raise ValueError("Corpus capture health/inventory receipt must be SHA-pinned")
    receipt=json.loads((Path(bundle)/name).read_text())
    if receipt.get("outcomes_read") is not False:
        raise ValueError("Corpus receipt must declare no outcome reads")
    for tier in TIERS:
        selected=manifest["sets"]["speed"][tier]
        row=receipt["tiers"][tier]
        inventory=row["state_inventory"]
        if row["states"] != 300 or len(inventory) != 300 or len({v["id"] for v in inventory}) != 300 or set(v["id"] for v in inventory) != set(selected):
            raise ValueError("Selected-state inventory differs from own-tier fixed300")
        if any(len(v["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in v["sha256"]) for v in inventory):
            raise ValueError("Invalid selected-state SHA inventory")
        health=row["capture_health"]
        eligible=health["eligible_search_opportunities"]
        if type(eligible) is not int or eligible < 300 or any(type(health[k]) is not int or not 0 <= health[k] <= eligible for k in ("deadline_cut","suspended_transaction")):
            raise ValueError("Invalid excluded-capture health counts")
        if row["selected_suspended_transaction_states"] != sum(backend.by_id[i]["belief_had_suspended_transaction"] for i in selected):
            raise ValueError("Suspended-transaction disclosure differs from selected rows")
    return receipt
