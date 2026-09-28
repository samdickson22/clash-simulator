"""Exercise the public information boundary on opened native captures."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

from clasher.data import CardDataLoader
from clasher.rl.native_match_registry import canonical_digest
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_reference_checks import (
    check_reference_entities,
    check_reference_packet,
    reference_token_maps,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_private(ordinary, rich, owner):
    """Keep declared reference labels only, including effect identity attestation.

    This does not claim that native HP, position or level readings are camera
    measurements. The remaining fields are the inputs of the reference adapter.
    """
    frame_keys = (
        "ok",
        "generation",
        "stateEpoch",
        "tick",
        "ended",
        "finalized",
        "count",
        "returned",
        "truncated",
    )
    object_keys = ("nativeObjectId", "owner", "cardId", "x", "y", "hp", "maxHp")
    rename = {
        o["nativeObjectId"]: o["nativeObjectId"] + 100000000
        for o in ordinary["objects"]
    }

    def body(o):
        v = {k: o[k] for k in object_keys if k in o}
        v["nativeObjectId"] = rename[o["nativeObjectId"]]
        return v

    clean = {k: ordinary[k] for k in frame_keys}
    clean["objects"] = [body(o) for o in reversed(ordinary["objects"])]
    own = next(p for p in ordinary["players"] if p["owner"] == owner)
    card_keys = ("handIndex", "cardId", "commandCardId")
    clean["players"] = [
        {
            "owner": owner,
            "elixirRaw": own["elixirRaw"],
            "hand": [
                {k: c[k] for k in card_keys if k in c} for c in reversed(own["hand"])
            ],
            "nextCard": {
                k: own["nextCard"][k] for k in card_keys if k in own["nextCard"]
            },
        }
    ]
    clean_rich = {
        k: rich[k]
        for k in (*frame_keys[:4], "schema", "count", "returned", "truncated")
    }
    clean_rich["objects"] = []
    for obj in reversed(rich["objects"]):
        v = body(obj)
        if obj.get("hp") is None:
            v["dataGlobalId"] = obj.get("dataGlobalId")
            projectile = obj.get("projectile")
            if projectile is not None:
                v["projectile"] = {
                    k: projectile[k]
                    for k in ("projectileDataGlobalId", "nativePhase", "terminal")
                }
        clean_rich["objects"].append(v)
    return clean, clean_rich, rename


def audit_capture(source, catalog):
    paths = [
        source / p for p in ("plan.json", "gamedata.json", "native-frames.jsonl.gz")
    ]
    before = {str(p): digest(p) for p in paths}
    plan = json.loads(paths[0].read_text())
    loader = CardDataLoader(paths[1])
    independent_vocabulary = plan.get("public_card_roster") is not None
    if independent_vocabulary:
        if plan["public_card_roster"] != list(PUBLIC_REFERENCE_CARDS):
            raise ValueError("capture public roster differs from declared reference scope")
        names = PUBLIC_REFERENCE_CARDS
        builder = public_reference_builder(loader, catalog)
        if plan.get("token_vocabulary_sha256") != canonical_digest(builder.token_names):
            raise ValueError("capture token vocabulary differs from public roster")
    else:
        # Preserve historical diagnostics, but never admit their match-specific
        # vocabularies as independent public policy inputs.
        names = sorted({n for deck in plan["decks"] for n in deck})
        base = StructuredObservationBuilder(card_loader=loader, card_vocab=names)
        tokens = ["<pad>", "<unknown>", *sorted(set(base.token_names[2:]) | set(catalog.names))]
        builder = StructuredObservationBuilder(
            card_loader=loader, card_vocab=names, token_names=tokens,
            canonical_lane_globals=True, public_entity_levels=True,
            card_semantics_version=4,
        )
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", before[str(paths[1])]),
        card_names=tuple(names),
        projectile_catalog=catalog,
    )
    masker = PublicActionMaskBuilder(builder)
    card_tokens, body_tokens, effect_tokens, tower_tokens = reference_token_maps(
        builder, names, catalog
    )
    count, max_entities, canaries, coverage, errors = 0, 0, 0, Counter(), []
    with gzip.open(paths[2], "rt") as stream:
        for line in stream:
            record = json.loads(line)
            ordinary, rich, levels = (
                record["ordinary"],
                record["rich"],
                record["level_source"],
            )
            evidence = NativePublicLevelEvidence(
                tick=ordinary["tick"],
                generation=ordinary["generation"],
                state_epoch=ordinary["stateEpoch"],
                source_sha256=hashlib.sha256(
                    json.dumps(levels, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                levels={int(k): v for k, v in levels["levels"].items()},
                confidence={int(k): 1.0 for k in levels["levels"]},
            )
            for owner in (0, 1):
                try:
                    original = adapter.project(
                        ordinary, owner, rich_snapshot=rich, level_evidence=evidence
                    )
                    failures = check_reference_packet(
                        ordinary, original, owner, card_tokens=card_tokens
                    )
                    failures += check_reference_entities(
                        ordinary,
                        rich,
                        original,
                        owner,
                        body_tokens=body_tokens,
                        effect_tokens=effect_tokens,
                        tower_tokens=tower_tokens,
                        levels=evidence.levels,
                        level_confidence=evidence.confidence,
                    )
                    if failures:
                        raise ValueError("; ".join(failures))
                    clean, clean_rich, renamed = strip_private(ordinary, rich, owner)
                    clean_evidence = replace(
                        evidence,
                        levels={renamed[k]: v for k, v in evidence.levels.items()},
                        confidence={
                            renamed[k]: v for k, v in evidence.confidence.items()
                        },
                    )
                    stripped = adapter.project(
                        clean,
                        owner,
                        rich_snapshot=clean_rich,
                        level_evidence=clean_evidence,
                    )
                    a = PublicPolicySequence.from_observations(
                        builder, [original]
                    ).arrays
                    b = PublicPolicySequence.from_observations(
                        builder, [stripped]
                    ).arrays
                    if a.keys() != b.keys() or any(
                        not np.array_equal(a[k], b[k]) for k in a
                    ):
                        raise ValueError(
                            "actor serialization depends on stripped private state or native identity"
                        )
                    masks = [
                        masker.build(
                            PublicActionMaskInput.from_confidence_observation(v)
                        )
                        for v in (original, stripped)
                    ]
                    if not np.array_equal(*masks):
                        raise ValueError("legal action mask changed")
                    # A public HUD perturbation must change the output: avoid a
                    # vacuous invariance success from a constant projection.
                    hud = clean["players"][0]
                    hud["elixirRaw"] += -1 if hud["elixirRaw"] == 100000 else 1
                    changed = adapter.project(
                        clean,
                        owner,
                        rich_snapshot=clean_rich,
                        level_evidence=clean_evidence,
                    )
                    if np.array_equal(
                        original.observation.global_features,
                        changed.observation.global_features,
                    ):
                        raise ValueError("public HUD sensitivity canary failed")
                    canaries += 1
                    count += 1
                    entity_ids = original.observation.entity_ids[
                        original.observation.entity_mask
                    ]
                    max_entities = max(max_entities, len(entity_ids))
                    coverage.update(builder.token_names[i] for i in entity_ids)
                except (ValueError, KeyError, TypeError) as error:
                    errors.append(
                        {"tick": ordinary["tick"], "owner": owner, "error": str(error)}
                    )
    unchanged = before == {str(p): digest(p) for p in paths}
    return {
        "source": str(source),
        "sources": before,
        "sources_unchanged": unchanged,
        "hidden_deck_independent_vocabulary": independent_vocabulary,
        "paired_frames_passed": count,
        "public_hud_canaries_passed": canaries,
        "max_entities": max_entities,
        "entity_token_occurrences": dict(coverage),
        "errors": errors,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", nargs="+", type=Path, required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--catalog-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    catalog = NativeProjectileCatalog.from_csv(
        args.catalog, expected_sha256=args.catalog_sha256
    )
    source_paths = sorted(Path("src/clasher").rglob("*.py")) + [Path(__file__)]
    producer = {str(path): digest(path) for path in source_paths}
    rows = []
    for source in args.capture:
        row = audit_capture(source, catalog)
        rows.append(row)
        print(
            source.name,
            row["paired_frames_passed"],
            "passed;",
            len(row["errors"]),
            "errors",
            flush=True,
        )
    unchanged = producer == {str(path): digest(path) for path in source_paths}
    report = {
        "producer_sources": producer,
        "producer_sources_unchanged": unchanged,
        "role": "opened development",
        "acceptance_passed": False,
        "training_authorized": False,
        "scope": "Reference adapter invariance with no own accepted-play history; no camera/noise calibration claim.",
        "auditor_sha256": digest(Path(__file__)),
        "catalog_sha256": catalog.sha256,
        "rows": rows,
    }
    with args.output.open("x") as f:
        f.write(json.dumps(report, indent=2) + "\n")
    if not unchanged or any(r["errors"] or not r["sources_unchanged"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
