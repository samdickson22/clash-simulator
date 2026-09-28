"""Build arena- and chronology-stratified contact sheets from retained audits."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_write_json, file_sha256


def _arena_number(name: str) -> int:
    prefix, separator, value = name.rpartition("_")
    if not separator or prefix != "arena" or not value.isdigit():
        raise ValueError(f"invalid arena name: {name}")
    return int(value)


def _select_quantile(records: list[dict[str, Any]], index: int, count: int) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot select from an empty arena")
    if count <= 0 or not 0 <= index < count:
        raise ValueError("invalid quantile index/count")
    position = 0 if count == 1 else round(index * (len(records) - 1) / (count - 1))
    return records[position]


def _audit_paths(record: dict[str, Any], *, run_root: Path) -> tuple[Path, Path]:
    corpus_path = Path(str(record["corpus"])).resolve()
    if not corpus_path.is_relative_to(run_root):
        raise ValueError(f"corpus escapes run root: {corpus_path}")
    game_manifest_path = corpus_path.parent / "manifest.json"
    game = json.loads(game_manifest_path.read_text(encoding="utf-8"))
    if game.get("arena") != record.get("arena") or game.get("replay") != record.get(
        "replay"
    ):
        raise ValueError(f"game identity mismatch: {game_manifest_path}")
    outputs = sorted(Path(str(value)).resolve() for value in game.get("audit_outputs", []))
    if not outputs:
        raise ValueError(f"game has no retained audit images: {game_manifest_path}")
    for output in outputs:
        if not output.is_relative_to(run_root) or not output.is_file():
            raise ValueError(f"invalid retained audit image: {output}")
    return outputs[0], outputs[-1]


def _render_sheet(
    rows: list[tuple[str, str, Path]],
    *,
    output: Path,
    columns: int = 5,
    cell_width: int = 240,
    cell_height: int = 384,
) -> None:
    if not rows:
        raise ValueError("contact sheet has no rows")
    grid_rows = (len(rows) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cell_width, grid_rows * cell_height), "black")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    header_height = 16
    for index, (arena, replay, path) in enumerate(rows):
        column = index % columns
        row = index // columns
        x0 = column * cell_width
        y0 = row * cell_height
        label = f"{arena} {replay[:8]}"
        draw.text((x0 + 4, y0 + 2), label, fill="white", font=font)
        with Image.open(path) as source:
            image = source.convert("RGB")
        image.thumbnail((cell_width, cell_height - header_height), Image.Resampling.LANCZOS)
        x = x0 + (cell_width - image.width) // 2
        y = y0 + header_height + (cell_height - header_height - image.height) // 2
        canvas.paste(image, (x, y))
    temporary = output.with_suffix(output.suffix + ".tmp")
    canvas.save(temporary, format="JPEG", quality=92, optimize=True)
    os.replace(temporary, output)


def build_contact_sheets(
    *,
    run_manifest_path: Path,
    output_dir: Path,
    quantiles: int,
    expected_arenas: int,
) -> dict[str, Any]:
    if quantiles <= 0 or expected_arenas <= 0:
        raise ValueError("quantiles and expected_arenas must be positive")
    run_manifest_path = run_manifest_path.resolve()
    run_root = run_manifest_path.parent
    run = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    by_arena: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in run.get("records", []):
        if record.get("status") == "complete":
            by_arena[str(record["arena"])].append(record)
    arenas = sorted(by_arena, key=_arena_number)
    if len(arenas) != expected_arenas:
        raise ValueError(
            f"completed run has {len(arenas)} arenas; expected {expected_arenas}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    expected_outputs = [
        output_dir / f"q{quantile:02d}_{phase}.jpg"
        for quantile in range(quantiles)
        for phase in ("early", "late")
    ]
    existing = [str(path) for path in (*expected_outputs, manifest_path) if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite contact-sheet outputs: " + ", ".join(existing))

    sheets: list[dict[str, Any]] = []
    for quantile in range(quantiles):
        phase_rows: dict[str, list[tuple[str, str, Path]]] = {
            "early": [],
            "late": [],
        }
        phase_sources: dict[str, list[dict[str, str]]] = {
            "early": [],
            "late": [],
        }
        for arena in arenas:
            record = _select_quantile(by_arena[arena], quantile, quantiles)
            early, late = _audit_paths(record, run_root=run_root)
            for phase, path in (("early", early), ("late", late)):
                replay = str(record["replay"])
                phase_rows[phase].append((arena, replay, path))
                phase_sources[phase].append(
                    {
                        "arena": arena,
                        "replay": replay,
                        "source": str(path),
                        "source_sha256": file_sha256(path),
                    }
                )
        for phase in ("early", "late"):
            output = output_dir / f"q{quantile:02d}_{phase}.jpg"
            _render_sheet(phase_rows[phase], output=output)
            sheets.append(
                {
                    "quantile": quantile,
                    "phase": phase,
                    "output": str(output),
                    "output_sha256": file_sha256(output),
                    "sources": phase_sources[phase],
                }
            )
    payload = {
        "schema_version": 1,
        "schema": "tv-royale-public-arena-contact-sheets-v1",
        "run_manifest": str(run_manifest_path),
        "run_manifest_sha256": file_sha256(run_manifest_path),
        "completed_games_at_render": sum(len(records) for records in by_arena.values()),
        "arenas": arenas,
        "quantiles": quantiles,
        "sheets": sheets,
    }
    atomic_write_json(manifest_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--quantiles", type=int, default=4)
    parser.add_argument("--expected-arenas", type=int, default=20)
    args = parser.parse_args()
    payload = build_contact_sheets(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
        quantiles=args.quantiles,
        expected_arenas=args.expected_arenas,
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
