"""Record one interrupted development prefix claim as a failed capture.

Uses the existing ownership API under the original claim nonce. Partial native
artifacts are hashed and preserved; the native episode is never rerun.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from clasher.rl.readiness_capture_ownership import (
    CaptureReceipt,
    EpisodeClaim,
    record_capture,
)
from clasher.rl.readiness_execution import file_sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--family-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.registry.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT record FROM episode_claims WHERE attempt_id=? AND family_id=? AND nonce=?",
            (args.attempt_id, args.family_id, args.nonce),
        ).fetchone()
        if row is None:
            raise SystemExit("claim not found")
        if db.execute(
            "SELECT 1 FROM captures WHERE attempt_id=? AND family_id=?",
            (args.attempt_id, args.family_id),
        ).fetchone():
            raise SystemExit("claim already has a capture receipt")
    claim = EpisodeClaim.model_validate_json(row[0])
    output = Path(claim.output_path)
    if (output / "capture-receipt.json").exists():
        raise SystemExit("capture receipt already exists on disk")
    failure = {
        "family_id": args.family_id,
        "status": "failed",
        "failure": args.reason,
        "claimed": True,
        "output": str(output),
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
        "native_read_session_closed_verified": (output / "native-read-session.json").exists(),
    }
    with (output / "collector-failure.json").open("x") as stream:
        stream.write(json.dumps(failure, indent=2) + "\n")
    receipt = CaptureReceipt(
        claim_nonce=claim.nonce,
        design_sha256=claim.design_sha256,
        family_id=claim.family_id,
        config_sha256=claim.config_sha256,
        native_attestation_sha256=claim.native_attestation_sha256,
        status="failed",
        prefix_complete=False,
        failure=args.reason,
        artifact_hashes={
            str(path.relative_to(output)): file_sha(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        },
    )
    record_capture(args.registry, claim, receipt)
    print(json.dumps({"family_id": claim.family_id, "status": "failed", "artifacts": len(receipt.artifact_hashes)}))


if __name__ == "__main__":
    main()
