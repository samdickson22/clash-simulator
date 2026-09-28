from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.build_tv_royale_public_contact_sheets import build_contact_sheets


def test_builds_arena_and_chronology_stratified_sheets(tmp_path: Path) -> None:
    records = []
    for arena_number, color in ((12, "red"), (13, "blue")):
        arena = f"arena_{arena_number}"
        for game_index in range(3):
            replay = f"replay-{arena_number}-{game_index}"
            game_root = tmp_path / "games" / arena / replay
            audit_root = game_root / "audit"
            audit_root.mkdir(parents=True)
            outputs = []
            for phase in range(2):
                output = audit_root / f"00{phase}.jpg"
                Image.new("RGB", (40, 80), color).save(output)
                outputs.append(str(output))
            (game_root / "corpus.npz").write_bytes(b"fixture")
            (game_root / "manifest.json").write_text(
                json.dumps(
                    {
                        "arena": arena,
                        "replay": replay,
                        "audit_outputs": outputs,
                    }
                )
            )
            records.append(
                {
                    "status": "complete",
                    "arena": arena,
                    "replay": replay,
                    "corpus": str(game_root / "corpus.npz"),
                }
            )
    run_manifest = tmp_path / "run_manifest.json"
    run_manifest.write_text(json.dumps({"records": records}))

    result = build_contact_sheets(
        run_manifest_path=run_manifest,
        output_dir=tmp_path / "sheets",
        quantiles=3,
        expected_arenas=2,
    )

    assert result["completed_games_at_render"] == 6
    assert result["run_manifest_sha256"] == hashlib.sha256(
        run_manifest.read_bytes()
    ).hexdigest()
    assert result["arenas"] == ["arena_12", "arena_13"]
    assert len(result["sheets"]) == 6
    assert all(len(sheet["sources"]) == 2 for sheet in result["sheets"])
    assert {
        source["replay"]
        for sheet in result["sheets"]
        if sheet["quantile"] == 1
        for source in sheet["sources"]
    } == {"replay-12-1", "replay-13-1"}
    for sheet in result["sheets"]:
        with Image.open(sheet["output"]) as image:
            assert image.size == (1200, 384)
