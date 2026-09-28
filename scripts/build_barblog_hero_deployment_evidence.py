from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SCHEMA = "clasher.current_client.barblog_hero_deployment_evidence.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_neutral(path: Path) -> dict[int, dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return {row["sample_index"]: row for row in map(json.loads, source)}


def _exact_frames(video: Path, indices: list[int]) -> dict[int, np.ndarray]:
    ordered = sorted(set(indices))
    selection = "+".join(f"eq(n\\,{index})" for index in ordered)
    with tempfile.TemporaryDirectory(prefix="clasher-hero-deploy-") as temporary:
        pattern = Path(temporary) / "frame_%03d.png"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video),
                "-vf",
                f"fps=10,select='{selection}'",
                "-fps_mode",
                "vfr",
                str(pattern),
            ],
            check=True,
        )
        paths = sorted(Path(temporary).glob("frame_*.png"))
        if len(paths) != len(ordered):
            raise ValueError(f"expected {len(ordered)} exact frames, got {len(paths)}")
        result: dict[int, np.ndarray] = {}
        for index, path in zip(ordered, paths, strict=True):
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f"could not decode exact sample {index}")
            result[index] = cv2.resize(
                image, (image.shape[1] // 2, image.shape[0] // 2)
            )
        return result


def _panel(
    frames: dict[int, np.ndarray],
    *,
    sample_index: int,
    title: str,
    region: tuple[float, float, float, float],
) -> np.ndarray:
    image = frames[sample_index]
    height, width = image.shape[:2]
    x, y, w, h = region
    crop = image[
        round(y * height) : round((y + h) * height),
        round(x * width) : round((x + w) * width),
    ]
    panel = cv2.resize(crop, (450, 270))
    cv2.rectangle(panel, (0, 0), (449, 34), (0, 0, 0), -1)
    cv2.putText(
        panel,
        title,
        (7, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return panel


def _render_sheet(video: Path, output: Path) -> dict[str, Any]:
    frames = _exact_frames(video, [308, 314, 371, 372, 374, 382])
    bottom_hud = (0.0, 0.82, 1.0, 0.18)
    left_lane = (0.0, 0.32, 0.52, 0.52)
    panels = [
        _panel(
            frames,
            sample_index=308,
            title="30.8s: glowing cost-2 card in bottom Next",
            region=bottom_hud,
        ),
        _panel(
            frames,
            sample_index=314,
            title="31.4s: same card in ordinary hand",
            region=bottom_hud,
        ),
        _panel(
            frames,
            sample_index=371,
            title="37.1s: card present; public elixir displays 4",
            region=bottom_hud,
        ),
        _panel(
            frames,
            sample_index=372,
            title="37.2s: card gone; public elixir displays 2",
            region=bottom_hud,
        ),
        _panel(
            frames,
            sample_index=374,
            title="37.4s: friendly rolling barrel on left lane",
            region=left_lane,
        ),
        _panel(
            frames,
            sample_index=382,
            title="38.2s: barrel ends at enemy swarm",
            region=left_lane,
        ),
    ]
    sheet = np.vstack((np.hstack(panels[:3]), np.hstack(panels[3:])))
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise ValueError(f"could not write {output}")
    return {"path": str(output.resolve()), "sha256": _sha256(output)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--gamedata", default="gamedata.json")
    parser.add_argument(
        "--vocabulary",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument(
        "--neutral-sequence",
        default=(
            "datasets/derived/tv_royale_youtube_fullmatch_semantic_"
            "hTG8dM4KtM4_20260817/neutral_sequence.jsonl.gz"
        ),
    )
    parser.add_argument(
        "--video",
        default=(
            "datasets/external/tv_royale_youtube_fullmatch_20260817/"
            "hTG8dM4KtM4/source.webm"
        ),
    )
    parser.add_argument(
        "--output", default="reports/barblog_hero_deployment_evidence_v1.json"
    )
    parser.add_argument(
        "--contact-sheet",
        default="reports/barblog_hero_deployment_sequence_v1.jpg",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.repository_root).resolve()
    gamedata_path = (root / args.gamedata).resolve()
    vocabulary_path = (root / args.vocabulary).resolve()
    neutral_path = (root / args.neutral_sequence).resolve()
    video_path = (root / args.video).resolve()
    output_path = (root / args.output).resolve()
    sheet_path = (root / args.contact_sheet).resolve()
    gamedata = json.loads(gamedata_path.read_text(encoding="utf-8"))
    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
    records = _load_neutral(neutral_path)
    spells = {row["name"]: row for row in gamedata["items"]["spells"]}
    entries = {row["stable_key"]: row for row in vocabulary["entries"]}

    cost_two: list[dict[str, Any]] = []
    for variant in vocabulary["hero_variants"]:
        base = spells[variant["base"]]
        hero = base["heroData"]
        if hero.get("manaCost") != 2:
            continue
        cost_two.append(
            {
                "stable_key": f"card_action:{variant['variant']}",
                "actor_token_id": entries[f"card_action:{variant['variant']}"][
                    "actor_token_id"
                ],
                "summon_character": hero.get("summonCharacter"),
                "summon_number": hero.get("summonNumber"),
                "projectile": hero.get("projectile"),
                "spell_as_deploy": hero.get("spellAsDeploy", False),
            }
        )
    cost_two.sort(key=lambda row: row["stable_key"])

    before = records[371]["offline_privileged_hud"]["0"]
    after = records[372]["offline_privileged_hud"]["0"]
    barrel_detections: list[dict[str, Any]] = []
    for sample in (374, 375):
        for entity in records[sample]["public"]["entities"]:
            if entity["visual_class"] == "barbarian-barrel" and entity["team_id"] == 0:
                barrel_detections.append(
                    {
                        "sample_index": sample,
                        "timestamp_ms": records[sample]["timestamp_ms"],
                        "confidence": entity["confidence"],
                        "world_position": entity["world_position"],
                        "sprite_box_normalized": entity["sprite_box_normalized"],
                        "detector_box_is_proposal_not_identity_authority": True,
                    }
                )
    if len(barrel_detections) != 2:
        raise ValueError("expected two consecutive friendly barrel proposals")

    contact = _render_sheet(video_path, sheet_path)
    payload = {
        "schema": SCHEMA,
        "authorities": {
            "gamedata": {
                "path": _relative(gamedata_path, root),
                "sha256": _sha256(gamedata_path),
                "client_version": "15.546.41",
            },
            "vocabulary": {
                "path": _relative(vocabulary_path, root),
                "sha256": _sha256(vocabulary_path),
            },
            "source_video": {
                "video_id": "hTG8dM4KtM4",
                "path": _relative(video_path, root),
                "sha256": _sha256(video_path),
                "split": "test",
            },
            "neutral_sequence": {
                "path": _relative(neutral_path, root),
                "sha256": _sha256(neutral_path),
            },
        },
        "observed_sequence": {
            "normal_cycle": [
                {
                    "sample_index": 308,
                    "timestamp_ms": 30800,
                    "observation": "variant visible in bottom Next",
                },
                {
                    "sample_index": 314,
                    "timestamp_ms": 31400,
                    "observation": "same variant visible in ordinary bottom hand",
                },
            ],
            "play_transition": {
                "before": {
                    "sample_index": 371,
                    "timestamp_ms": 37100,
                    "hand_slot": 1,
                    "recognized_family_hint": before["hand"][1]["value"],
                    "recognition_score": before["hand"][1]["score"],
                    "public_elixir_fractional_head": before["elixir"]["value"],
                    "public_displayed_elixir": 4,
                },
                "after": {
                    "sample_index": 372,
                    "timestamp_ms": 37200,
                    "hand_slot": 1,
                    "recognized_family_hint": after["hand"][1]["value"],
                    "recognition_candidate": after["hand"][1]["candidate"],
                    "public_elixir_fractional_head": after["elixir"]["value"],
                    "public_displayed_elixir": 2,
                },
                "displayed_elixir_drop": 2,
                "fractional_head_drop": before["elixir"]["value"]
                - after["elixir"]["value"],
                "hand_disappearance_proven": True,
            },
            "arena_result": {
                "visual_observation": (
                    "a friendly barrel rolls from the bottom left lane toward the bridge "
                    "immediately after the card disappears"
                ),
                "barrel_detector_proposals": barrel_detections,
                "visual_reviewed": True,
            },
        },
        "official_cost_two_hero_candidates": cost_two,
        "candidate_comparison": {
            "card_action:BarbLog_hero": (
                "unique match: cost 2 and deploys BarbLogProjectile as spell-as-deploy"
            ),
            "card_action:Goblins_hero": (
                "rejected: directly summons four Goblin_Stab bodies; no rolling projectile"
            ),
            "card_action:IceGolemite_hero": (
                "rejected: directly summons IceGolemite; no rolling projectile"
            ),
            "base_BarbLog": (
                "mechanics match, but repeated base portrait is visually distinct; typed "
                "heroData supplies the exact distinct cost-2 card variant"
            ),
        },
        "identity_decision": {
            "stable_key": "card_action:BarbLog_hero",
            "actor_token_id": 100,
            "status": "accepted_exact_identity_for_reviewed_test_sequence",
            "basis": [
                "distinct portrait versus repeated base BarbLog portrait",
                "normal Next-to-hand cycling card behavior",
                "exact public displayed elixir drop from 4 to 2",
                "immediate visually confirmed rolling Barbarian Barrel deployment",
                "only official cost-2 hero candidate with BarbLogProjectile mechanics",
            ],
            "root_family_only_auto_label": False,
            "generalize_to_other_video_crops": False,
            "arena_detector_class_required": False,
            "arena_reason": "heroData uses the existing BarbLogProjectile; distinction is HUD identity",
        },
        "contact_sheet": contact,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "sha256": _sha256(output_path),
                "contact_sheet": contact,
                "decision": payload["identity_decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
