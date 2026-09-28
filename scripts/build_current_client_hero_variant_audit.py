from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SCHEMA = "clasher.current_client.hero_variant_hud_audit.v1"
HUD_ROIS: dict[int, tuple[tuple[float, float, float, float], ...]] = {
    0: tuple((x, 0.868, 0.145, 0.090) for x in (0.105, 0.252, 0.397, 0.532)),
    1: tuple((x, 0.098, 0.132, 0.085) for x in (0.130, 0.262, 0.394, 0.526)),
}
BASE_TEMPLATE_FILENAMES = {
    "Balloon": "balloon-5.png",
    "BarbLog": "barb_barrel-2.png",
    "Bowler": "bowler-5.png",
    "DarkPrince": "dark_prince-4.png",
    "EliteArcher": "magic_archer-4.png",
    "Giant": "giant-5.png",
    "Goblins": "goblins-2.png",
    "IceGolemite": "ice_golem-2.png",
    "Knight": "knight-3.png",
    "MegaMinion": "mega_minion-3.png",
    "MiniPekka": "mini_pekka-4.png",
    "Musketeer": "musketeer-4.png",
    "Tombstone": "tombstone-3.png",
    "Wizard": "wizard-5.png",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _exact_frames(video: Path, indices: list[int]) -> dict[int, np.ndarray]:
    ordered = sorted(set(indices))
    selection = "+".join(f"eq(n\\,{index})" for index in ordered)
    with tempfile.TemporaryDirectory(prefix="clasher-hero-hud-") as temporary:
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
                raise ValueError(f"could not decode exact frame {index}")
            result[index] = cv2.resize(
                image, (image.shape[1] // 2, image.shape[0] // 2)
            )
        return result


def _card_crop(
    frames: dict[int, np.ndarray], *, frame: int, player: int, slot: int
) -> np.ndarray:
    image = frames[frame]
    height, width = image.shape[:2]
    x, y, w, h = HUD_ROIS[player][slot]
    return image[
        round(y * height) : round((y + h) * height),
        round(x * width) : round((x + w) * width),
    ]


def _bottom_hud_crop(frames: dict[int, np.ndarray], *, frame: int) -> np.ndarray:
    image = frames[frame]
    height = image.shape[0]
    return image[round(0.82 * height) : height, :]


def _render_sheet(
    *,
    video: Path,
    base_template: Path,
    suspect_rows: list[dict[str, Any]],
    base_rows: list[dict[str, Any]],
    output: Path,
) -> dict[str, Any]:
    exact_indices = [row["frame"] for row in [*suspect_rows[:4], *base_rows[:4]]] + [
        258,
        308,
        314,
    ]
    frames = _exact_frames(video, exact_indices)
    panels: list[np.ndarray] = []
    base_image = cv2.imread(str(base_template))
    if base_image is None:
        raise ValueError(f"could not decode {base_template}")
    evidence = [
        ("LOCAL BASE BarbLog", base_image),
        *[
            (
                f"HERO? p{row['player_id']} f{row['frame']} s{row['slot']} cost2",
                _card_crop(
                    frames,
                    frame=row["frame"],
                    player=row["player_id"],
                    slot=row["slot"],
                ),
            )
            for row in suspect_rows[:4]
        ],
        *[
            (
                f"BASE p{row['player_id']} f{row['frame']} s{row['slot']} cost2",
                _card_crop(
                    frames,
                    frame=row["frame"],
                    player=row["player_id"],
                    slot=row["slot"],
                ),
            )
            for row in base_rows[:4]
        ],
        (
            "SEQ 25.8s before variant reaches Next",
            _bottom_hud_crop(frames, frame=258),
        ),
        (
            "SEQ 30.8s glowing card in Next",
            _bottom_hud_crop(frames, frame=308),
        ),
        (
            "SEQ 31.4s glowing card in hand",
            _bottom_hud_crop(frames, frame=314),
        ),
    ]
    for title, image in evidence:
        panel = cv2.resize(image, (300, 210))
        cv2.rectangle(panel, (0, 0), (299, 32), (0, 0, 0), -1)
        cv2.putText(
            panel,
            title,
            (6, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        panels.append(panel)
    while len(panels) % 3:
        panels.append(np.zeros((210, 300, 3), dtype=np.uint8))
    sheet = np.vstack(
        [np.hstack(panels[offset : offset + 3]) for offset in range(0, len(panels), 3)]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise ValueError(f"could not write {output}")
    return {"path": str(output.resolve()), "sha256": _sha256(output)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--vocabulary",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument("--gamedata", default="gamedata.json")
    parser.add_argument(
        "--card-root",
        default="datasets/external/CS541-Deep-Learning-Clash-Royale-Project/cr_detection/cards",
    )
    parser.add_argument(
        "--cost-manifest",
        default=(
            "datasets/derived/tv_royale_youtube_fullmatch_visible_cost_gate_"
            "hTG8dM4KtM4_20260817/manifest.json"
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
        "--source-crop", default="reports/barbarians_source_card_crop_f0314.png"
    )
    parser.add_argument(
        "--deployment-evidence",
        default="reports/barblog_hero_deployment_evidence_v1.json",
    )
    parser.add_argument(
        "--output", default="reports/current_client_hero_variant_hud_manifest_v1.json"
    )
    parser.add_argument(
        "--contact-sheet",
        default="reports/current_client_hero_variant_hud_contact_sheet_v1.jpg",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.repository_root).resolve()
    vocabulary_path = (root / args.vocabulary).resolve()
    gamedata_path = (root / args.gamedata).resolve()
    card_root = (root / args.card_root).resolve()
    cost_path = (root / args.cost_manifest).resolve()
    video_path = (root / args.video).resolve()
    source_crop = (root / args.source_crop).resolve()
    deployment_path = (root / args.deployment_evidence).resolve()
    output_path = (root / args.output).resolve()
    sheet_path = (root / args.contact_sheet).resolve()

    vocabulary = json.loads(vocabulary_path.read_text(encoding="utf-8"))
    gamedata = json.loads(gamedata_path.read_text(encoding="utf-8"))
    cost_manifest = json.loads(cost_path.read_text(encoding="utf-8"))
    deployment = json.loads(deployment_path.read_text(encoding="utf-8"))
    deployment_decision = deployment["identity_decision"]
    if (
        deployment_decision["stable_key"] != "card_action:BarbLog_hero"
        or deployment_decision["status"]
        != "accepted_exact_identity_for_reviewed_test_sequence"
    ):
        raise ValueError("BarbLog hero deployment authority is not accepted")
    spells = {row["name"]: row for row in gamedata["items"]["spells"]}
    entries = {row["stable_key"]: row for row in vocabulary["entries"]}

    suspect_rows = [
        row
        for row in cost_manifest["occurrences"]
        if row["family"] == "card_action:Barbarians" and row.get("visible_cost") == 2
    ]
    base_rows = [
        row
        for row in cost_manifest["occurrences"]
        if row["family"] == "card_action:BarbLog" and row.get("visible_cost") == 2
    ]
    suspect_rows.sort(key=lambda row: row["frame"])
    base_rows.sort(key=lambda row: row["frame"])

    hero_rows: list[dict[str, Any]] = []
    for variant in vocabulary["hero_variants"]:
        base_name = variant["base"]
        hero_name = variant["variant"]
        stable_key = f"card_action:{hero_name}"
        stable = entries[stable_key]
        base_data = spells[base_name]
        hero_data = base_data["heroData"]
        base_template = card_root / BASE_TEMPLATE_FILENAMES[base_name]
        if not base_template.is_file():
            raise FileNotFoundError(base_template)
        base_body = (base_data.get("summonCharacterData") or {}).get("name")
        base_projectile = (base_data.get("projectileData") or {}).get("name")
        same_payload = (
            hero_data.get("summonCharacter") == base_body
            and hero_data.get("projectile") == base_projectile
        )
        proposals: list[dict[str, Any]] = []
        accepted_video_reference = stable_key == "card_action:BarbLog_hero"
        if stable_key == "card_action:BarbLog_hero":
            proposals.append(
                {
                    "video_id": "hTG8dM4KtM4",
                    "source_group_id": "youtube:hTG8dM4KtM4",
                    "split": "test",
                    "frames": [row["frame"] for row in suspect_rows],
                    "occurrences": len(suspect_rows),
                    "visible_cost": 2,
                    "evidence": (
                        "distinct glowing single-Barbarian portrait repeatedly seen; "
                        "typed heroData and cost match BarbLog_hero; independent sequence "
                        "shows portrait cycling from bottom Next into an ordinary hand slot"
                    ),
                    "slot_kind": "normal_cycling_hand_card_variant",
                    "temporary_ability_control_slot": False,
                    "status": "accepted_exact_identity_for_reviewed_test_sequence",
                    "auto_label": False,
                }
            )
        hero_rows.append(
            {
                "actor_token_id": stable["actor_token_id"],
                "stable_key": stable_key,
                "stable_id": stable["stable_id"],
                "base_stable_key": f"card_action:{base_name}",
                "owner_root_card": base_name,
                "stable_manifest_runtime_observable": stable["runtime_observable"],
                "hud_runtime_visible": True,
                "hud_visibility_basis": "typed card action in current-client heroData",
                "mana_cost": hero_data.get("manaCost"),
                "icon_file": hero_data.get("iconFile"),
                "highres_image_filename": hero_data.get("highresImageFilename"),
                "base_template_hint": {
                    "path": _relative(base_template, root),
                    "sha256": _sha256(base_template),
                    "hero_identity_label": False,
                },
                "exact_local_hero_template": (
                    {
                        "path": _relative(source_crop, root),
                        "sha256": _sha256(source_crop),
                        "split": "test",
                        "training_eligible": False,
                        "scope": "reviewed hTG8dM4KtM4 sequence only",
                    }
                    if accepted_video_reference
                    else None
                ),
                "template_status": (
                    "accepted_video_reference_test_only"
                    if accepted_video_reference
                    else "missing_distinct_hero_template"
                ),
                "root_family_may_auto_label": False,
                "video_review_proposals": proposals,
                "arena_disposition": {
                    "base_summon_character": base_body,
                    "hero_summon_character": hero_data.get("summonCharacter"),
                    "base_projectile": base_projectile,
                    "hero_projectile": hero_data.get("projectile"),
                    "same_payload_identity": same_payload,
                    "distinct_arena_body_proven": False,
                    "detector_class_required": False,
                    "reason": (
                        "current data names the same summoned body/projectile; "
                        "promote only if current video proves a distinct arena sprite"
                    ),
                },
                "review": {
                    "status": (
                        "accepted_exact_identity_for_reviewed_test_sequence"
                        if accepted_video_reference
                        else "missing_no_distinct_video_proposal"
                    ),
                    "accepted_template": (
                        _relative(source_crop, root)
                        if accepted_video_reference
                        else None
                    ),
                    "generalize_to_other_video_crops": False,
                },
            }
        )

    contact = _render_sheet(
        video=video_path,
        base_template=card_root / BASE_TEMPLATE_FILENAMES["BarbLog"],
        suspect_rows=suspect_rows,
        base_rows=base_rows,
        output=sheet_path,
    )
    payload = {
        "schema": SCHEMA,
        "authorities": {
            "vocabulary": {
                "path": _relative(vocabulary_path, root),
                "sha256": _sha256(vocabulary_path),
            },
            "gamedata": {
                "path": _relative(gamedata_path, root),
                "sha256": _sha256(gamedata_path),
                "client_version": "15.546.41",
            },
            "cost_manifest": {
                "path": _relative(cost_path, root),
                "sha256": _sha256(cost_path),
            },
            "barblog_hero_source_crop": {
                "path": _relative(source_crop, root),
                "sha256": _sha256(source_crop),
            },
            "barblog_hero_deployment_evidence": {
                "path": _relative(deployment_path, root),
                "sha256": _sha256(deployment_path),
            },
        },
        "contract": {
            "all_hero_card_actions_are_runtime_visible_hud_variants": True,
            "stable_runtime_observable_false_is_entity_graph_not_hud_disposition": True,
            "base_or_root_template_is_hint_only": True,
            "root_family_auto_label_forbidden": True,
            "video_proposals_are_test_only": True,
            "distinct_arena_class_requires_separate_visual_proof": True,
        },
        "counts": {
            "hero_variants": len(hero_rows),
            "runtime_visible_hud_variants": sum(
                row["hud_runtime_visible"] for row in hero_rows
            ),
            "exact_local_hero_templates": sum(
                row["exact_local_hero_template"] is not None for row in hero_rows
            ),
            "missing_distinct_hero_templates": sum(
                row["template_status"] == "missing_distinct_hero_template"
                for row in hero_rows
            ),
            "video_art_hypotheses": sum(
                bool(row["video_review_proposals"]) for row in hero_rows
            ),
            "accepted_video_references_test_only": sum(
                row["template_status"] == "accepted_video_reference_test_only"
                for row in hero_rows
            ),
            "distinct_arena_bodies_proven": sum(
                row["arena_disposition"]["distinct_arena_body_proven"]
                for row in hero_rows
            ),
        },
        "hero_template_queue": hero_rows,
        "barblog_hero_visual_audit": {
            "suspected_occurrences": len(suspect_rows),
            "base_barblog_occurrences": len(base_rows),
            "source_crop_sha256": _sha256(source_crop),
            "conclusion": (
                "portrait is visually distinct from local/base BarbLog art and repeated "
                "base BarbLog video art; exact identity is accepted for the reviewed "
                "test sequence by the separate deployment/mechanics authority"
            ),
        },
        "barblog_hero_slot_sequence": {
            "source_video_id": "hTG8dM4KtM4",
            "source_group_id": "youtube:hTG8dM4KtM4",
            "split": "test",
            "observations": [
                {
                    "sample_index": 258,
                    "timestamp_ms": 25800,
                    "observation": "preceding ordinary hand state before cycle transition",
                },
                {
                    "sample_index": 308,
                    "timestamp_ms": 30800,
                    "observation": "glowing cost-2 single-Barbarian portrait visible in bottom Next slot",
                },
                {
                    "sample_index": 314,
                    "timestamp_ms": 31400,
                    "observation": "same portrait visible in an ordinary bottom four-card hand slot after preceding play",
                },
            ],
            "slot_kind_conclusion": "normal_cycling_hand_card_variant_proven",
            "temporary_ability_control_slot_rejected": True,
            "exact_stable_identity": "card_action:BarbLog_hero",
            "exact_identity_status": "accepted_exact_identity_for_reviewed_test_sequence",
            "auto_label": False,
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
                "counts": payload["counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
