import json
from pathlib import Path

from scripts.filter_tv_royale_youtube_inventory import filter_inventory


def test_filter_inventory_excludes_only_hashable_complete_sources(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "input.jsonl"
    inventory.write_text(
        "".join(json.dumps({"id": value}) + "\n" for value in ("a", "b", "c")),
        encoding="utf-8",
    )
    root = tmp_path / "sources"
    for video_id, status in (("a", "complete"), ("b", "partial")):
        path = root / video_id / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"status": status, "source": {"video_id": video_id}}),
            encoding="utf-8",
        )
    output = tmp_path / "output.jsonl"
    result = filter_inventory(inventory, [root], output, tmp_path / "manifest.json")
    assert [json.loads(line)["id"] for line in output.read_text().splitlines()] == [
        "b",
        "c",
    ]
    assert result["input_rows"] == 3
    assert result["excluded_complete_video_ids"] == 1
    assert result["retained_rows"] == 2


def test_filter_inventory_accepts_published_semantic_manifests(tmp_path: Path) -> None:
    inventory = tmp_path / "input.jsonl"
    inventory.write_text(json.dumps({"id": "a"}) + "\n", encoding="utf-8")
    root = tmp_path / "semantics"
    manifest = root / "a" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schema": "clasher.youtube.fullmatch.extraction_manifest.v3",
                "source": {"video_id": "a"},
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output.jsonl"
    result = filter_inventory(inventory, [root], output, tmp_path / "manifest.json")
    assert output.read_text(encoding="utf-8") == ""
    assert result["excluded_complete_video_ids"] == 1
