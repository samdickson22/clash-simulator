"""Collect claimed readiness-v2 root prefixes from an already running reference.

This command never starts an emulator, creates an attempt, retries a claimed
family, evaluates branches, or labels a prefix as a complete game.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from contextlib import contextmanager
from pathlib import Path

from read_native_public_levels import VerifiedNativeReadSession
from run_readiness_v2 import public_views
from smoke_reference_battle import request as native_request

from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.public_reference_checks import reference_token_maps
from clasher.rl.readiness_capture_ownership import (
    CaptureReceipt,
    claim_episode,
    get_attempt,
    record_capture,
    verify_pins,
)
from clasher.rl.readiness_execution import (
    CAPTURE_FILES,
    CaptureBinding,
    canonical_sha,
    file_sha,
)
from clasher.rl.readiness_native_config import ConfigManifest
from clasher.rl.readiness_prefix import collect_prefix
from clasher.rl.readiness_root_bank import RootBank
from clasher.rl.training_readiness_v2 import Family


def collect(args):
    declaration = get_attempt(args.registry, args.attempt_id)
    manifest = ConfigManifest.model_validate_json(args.manifest.read_text())
    if file_sha(args.manifest) != declaration.converter_manifest_sha256:
        raise ValueError("converter manifest differs from declared attempt")
    bank_path = args.manifest.parent / "root-bank.json"
    bank = RootBank.model_validate_json(bank_path.read_text())
    if canonical_sha(bank.model_dump(mode="json")) != declaration.root_bank_sha256:
        raise ValueError("root bank differs from declared attempt")
    if file_sha(bank_path) != manifest.root_bank_file_sha256:
        raise ValueError("converter root-bank file changed")
    gamedata = Path(manifest.gamedata_path)
    if (
        file_sha(gamedata) != declaration.gamedata_sha256
        or manifest.gamedata_sha256 != declaration.gamedata_sha256
    ):
        raise ValueError("capture gamedata differs from declared attempt")
    if (
        file_sha(args.catalog) != args.catalog_sha256
        or args.catalog_sha256 != declaration.catalog_sha256
        or args.catalog_sha256 not in declaration.input_pins.values()
    ):
        raise ValueError("projectile catalog is not pinned by the attempt")
    requested = args.family_id or [
        episode.family_id for episode in declaration.episodes
    ]
    if len(set(requested)) != len(requested) or not set(requested) <= {
        e.family_id for e in declaration.episodes
    }:
        raise ValueError("requested families must be distinct declared episodes")
    # Freeze the full simulator/public package, plus the concrete native helpers,
    # so indirect imports cannot change outside the producer identity.
    workspace = Path(__file__).resolve().parents[1]
    required = [
        Path(__file__),
        workspace / "scripts/read_native_public_levels.py",
        workspace / "scripts/smoke_reference_battle.py",
        workspace / "scripts/run_readiness_v2.py",
        *sorted((workspace / "src/clasher").rglob("*.py")),
    ]
    pinned_paths = {Path(path).resolve() for path in declaration.source_pins}
    if any(path.resolve() not in pinned_paths for path in required):
        raise ValueError(
            "attempt source freeze omits collector/public/transport dependencies"
        )
    if (
        file_sha(workspace / "src/clasher/rl/readiness_root_bank.py")
        != declaration.generator_sha256
    ):
        raise ValueError("root generator source differs from declaration")

    def command(text):
        return native_request(args.port, text)

    def verify():
        verify_pins(declaration.source_pins)
        verify_pins(declaration.input_pins)
        if canonical_sha(command("attest")) != declaration.native_attestation_sha256:
            raise ValueError("native attestation differs from declared attempt")

    verify()
    loader = CardDataLoader(gamedata)
    catalog = NativeProjectileCatalog.from_csv(
        args.catalog, expected_sha256=args.catalog_sha256
    )
    builder = public_reference_builder(
        loader, catalog, card_semantics_version=4, public_contract_version=4
    )
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", declaration.gamedata_sha256),
        card_names=tuple(PUBLIC_REFERENCE_CARDS),
        projectile_catalog=catalog,
    )
    maps = reference_token_maps(builder, PUBLIC_REFERENCE_CARDS, catalog)

    active_read_session = []

    def read_frame():
        before = command("observe")
        if len(active_read_session) != 1:
            raise ValueError("public frame read requires one verified native session")
        levels = active_read_session[0].read_levels()
        rich = command("observe-rich")
        if levels["ordinary"] != before or command("observe") != before:
            raise ValueError("native frame changed across public level/rich reads")
        return {"ordinary": before, "rich": rich, "level_source": levels}

    args.output.mkdir(parents=True, exist_ok=False)
    source_archive = args.output / "producer-source.zip"
    with zipfile.ZipFile(
        source_archive, "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name, expected in sorted(declaration.source_pins.items()):
            path = Path(name).resolve()
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(f"source changed while archiving: {name}")
            relative = (
                str(path.relative_to(workspace))
                if path.is_relative_to(workspace)
                else f"external/{expected}/{path.name}"
            )
            archive.writestr(relative, data)
        archive.writestr(
            "attempt-declaration.json", declaration.model_dump_json(indent=2)
        )
    summary = {
        "schema": "readiness-v2-prefix-batch-v1",
        "attempt_id": args.attempt_id,
        "evidence_role": declaration.evidence_role,
        "requested_families": requested,
        "game_complete": False,
        "producer_source_sha256": file_sha(source_archive),
        "episodes": [],
    }
    for number, family_id in enumerate(requested):
        episode = next(e for e in declaration.episodes if e.family_id == family_id)
        output = args.output / f"episode-{number:02d}"
        holder = []
        try:
            root = next(r for r in bank.requests if r.family_id == family_id)
            entry = next(e for e in manifest.episodes if e.family_id == family_id)
            if (
                entry.status != "configured"
                or entry.config_sha256 != episode.config_sha256
                or entry.source_episode_id != episode.source_episode_id
                or root.source_episode_id != episode.source_episode_id
                or root.root_owner != episode.root_owner
                or canonical_sha(root.model_dump(mode="json"))
                != episode.root_request_sha256
                or (args.manifest.parent / entry.config_path).resolve()
                != Path(episode.config_path).resolve()
            ):
                raise ValueError(
                    "episode request/config bindings differ from declaration"
                )
            config = json.loads(Path(episode.config_path).read_text())
            if (
                canonical_sha(config) != episode.config_sha256
                or file_sha(Path(episode.config_path)) != episode.config_file_sha256
            ):
                raise ValueError("episode config changed")

            def claim(family_id=family_id, output=output, holder=holder):
                value = claim_episode(
                    args.registry,
                    attempt_id=args.attempt_id,
                    family_id=family_id,
                    output_path=output,
                    native_attestation_sha256=declaration.native_attestation_sha256,
                )
                holder.append(value)
                return value

            @contextmanager
            def read_session_scope(output=output):
                session = VerifiedNativeReadSession(
                    args.adb,
                    port=args.port,
                    serial=args.serial,
                    expected_attestation_sha256=declaration.native_attestation_sha256,
                )
                try:
                    with session as opened:
                        if active_read_session:
                            raise ValueError(
                                "another native read session is already active"
                            )
                        active_read_session.append(opened)
                        yield
                finally:
                    active_read_session.clear()
                    # Provenance is only read and attached after context exit,
                    # including failed enter/close receipts for the same claim.
                    provenance = session.provenance
                    (output / "native-read-session.json").write_text(
                        json.dumps(provenance, indent=2) + "\n"
                    )
                if provenance["status"] != "verified":
                    raise ValueError("native read session did not close verified")

            result = collect_prefix(
                root,
                config,
                output=output,
                role=declaration.evidence_role,
                builder=builder,
                command=command,
                read_frame=read_frame,
                project=lambda frame, history: public_views(
                    frame, adapter, maps, history
                ),
                claim=claim,
                verify_producer=verify,
                source_archive=source_archive,
                read_session_scope=read_session_scope,
            )
            capture_binding = None
            family = None
            if result["status"] == "selected":
                selected = result["selection"]
                frame = json.loads((output / "root-frame.json").read_text())
                capture_binding = CaptureBinding(
                    family_id=family_id,
                    capture_path=str(output.resolve()),
                    root_tick=selected["root_tick"],
                    input_hashes={
                        name: file_sha(output / name) for name in CAPTURE_FILES
                    },
                    config_sha256=episode.config_sha256,
                    root_frame_sha256=canonical_sha(frame),
                )
                family = Family(
                    family_id=family_id,
                    independence_id=episode.source_episode_id,
                    root_sha256=capture_binding.root_sha256,
                    public_packet_sha256=selected["public_packet_sha256"],
                    root_owner=episode.root_owner,
                    role=declaration.evidence_role,
                    candidates=tuple(selected["candidates"]),
                    original_recommendation=selected["original_recommendation"],
                )
            failure = None
            if result["status"] == "failed":
                failure = json.dumps(
                    result["failure"]
                    or result["selection"]
                    or {"error": "incomplete prefix"}
                )
            receipt = CaptureReceipt(
                claim_nonce=holder[0].nonce,
                design_sha256=holder[0].design_sha256,
                family_id=family_id,
                config_sha256=episode.config_sha256,
                native_attestation_sha256=declaration.native_attestation_sha256,
                status=result["status"],
                prefix_complete=result["prefix_complete"],
                artifact_hashes={
                    str(path.relative_to(output)): file_sha(path)
                    for path in output.rglob("*")
                    if path.is_file()
                },
                selected_family=family,
                capture_binding=capture_binding,
                failure=failure,
            )
            record_capture(args.registry, holder[0], receipt)
            summary["episodes"].append(
                {
                    "family_id": family_id,
                    "status": result["status"],
                    "output": str(output.resolve()),
                    "claim_nonce": holder[0].nonce,
                }
            )
        except (
            ValueError,
            RuntimeError,
            OSError,
            KeyError,
            TypeError,
            StopIteration,
            sqlite3.Error,
        ) as error:
            # A claimed failure is never retried or replaced by a new root.
            row = {
                "family_id": family_id,
                "status": "failed",
                "failure": str(error),
                "claimed": bool(holder),
                "output": str(output.resolve()),
            }
            if (
                holder
                and output.exists()
                and not (output / "capture-receipt.json").exists()
            ):
                # Preserve post-claim conversion/serialization failures in the same
                # append-only ledger identity. Never rerun the native episode.
                (output / "collector-failure.json").write_text(
                    json.dumps(row, indent=2) + "\n"
                )
                failed = CaptureReceipt(
                    claim_nonce=holder[0].nonce,
                    design_sha256=holder[0].design_sha256,
                    family_id=family_id,
                    config_sha256=episode.config_sha256,
                    native_attestation_sha256=declaration.native_attestation_sha256,
                    status="failed",
                    prefix_complete=False,
                    failure=str(error),
                    artifact_hashes={
                        str(path.relative_to(output)): file_sha(path)
                        for path in output.rglob("*")
                        if path.is_file()
                    },
                )
                try:
                    record_capture(args.registry, holder[0], failed)
                except (ValueError, OSError, sqlite3.Error) as ledger_error:
                    row["ledger_failure"] = str(ledger_error)
            summary["episodes"].append(row)
        (args.output / "batch-result.json").write_text(
            json.dumps(summary, indent=2) + "\n"
        )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--catalog-sha256", required=True)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument("--serial", default="emulator-5580")
    parser.add_argument("--family-id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args)
    print(
        json.dumps(
            {
                "attempt_id": result["attempt_id"],
                "statuses": [e["status"] for e in result["episodes"]],
            }
        )
    )
    raise SystemExit(
        0 if all(e["status"] == "selected" for e in result["episodes"]) else 1
    )


if __name__ == "__main__":
    main()
