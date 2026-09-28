from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import urllib.request
from pathlib import Path
from typing import Any

import texture2ddecoder
import zstandard
from PIL import Image, ImageChops, ImageDraw, ImageFont

SCHEMA = "clasher.current_client.variant_art_authority.v1"
CLIENT_VERSION = "15.546.41"
CONTENT_HASH = "ef863332281e7c47d628d23a80881ed300d47ede"
FINGERPRINT_URL = (
    "https://game-assets.clashroyaleapp.com/"
    f"{CONTENT_HASH}/fingerprint.json"
)
FINGERPRINT_SHA256 = (
    "53eed16e1e65f81637bb212680b3faf32036214dc13b89bb3e8f440556b19794"
)
GAMEDATA_SHA256 = (
    "3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a"
)
DISCLAIMER = (
    "This material is unofficial and is not endorsed by Supercell. "
    "For more information see Supercell's Fan Content Policy: "
    "www.supercell.com/fan-content-policy."
)

HERO_UI_STEMS = {
    "Balloon_hero": "ui_card_balloon_hero",
    "BarbLog_hero": "ui_card_barbarian_barrel_hero",
    "Bowler_hero": "ui_card_bowler_hero",
    "DarkPrince_hero": "ui_card_darkprince_hero",
    "EliteArcher_hero": "ui_card_magic_archer_hero",
    "Giant_hero": "ui_card_giant_hero",
    "Goblins_hero": "ui_card_goblins_hero",
    "IceGolemite_hero": "ui_card_icegolem_hero",
    "Knight_hero": "ui_card_knight_hero",
    "MegaMinion_hero": "ui_card_megaminion_hero",
    "MiniPekka_hero": "ui_card_minipekka_hero",
    "Musketeer_hero": "ui_card_musketeer_hero",
    "Tombstone_hero": "ui_card_tombstone_hero",
    "Wizard_hero": "ui_card_wizard_hero",
}

EVOLUTION_IMAGE_PATHS = {
    "Archer_EV1": "image/chr_evolution/archer_evolution_dl.png",
    "BabyDragon_EV1": "image/chr_evolution/baby_dragon_evolution_dl.png",
    "Barbarians_EV1": "image/chr_evolution/barbarian_evolution_dl.png",
    "Bats_EV1": "image/chr_evolution/bats_evolution_dl.png",
    "BattleRam_EV1": "image/chr_evolution/battle_ram_evolution_dl.png",
    "BlowdartGoblin_EV1": "image/chr_evolution/dart_goblin_evolution_dl.png",
    "Bomber_EV1": "image/chr_evolution/bomber_evolution_dl.png",
    "Cannon_EV1": "image/chr_evolution/cannon_evolution_dl.png",
    "ElectroDragon_EV1": "image/chr_evolution/electro_dragon_evolution_dl.png",
    "AxeMan_EV1": "image/chr_evolution/executioner_evolution.png",
    "Firecracker_EV1": "image/chr_evolution/firecracker_evolution_dl.png",
    "FirespiritHut_EV1": "image/chr_evolution/furnace_evolution.png",
    "GoblinBarrel_EV1": "image/chr_evolution/goblin_barrel_evolution_dl.png",
    "GoblinCage_EV1": "image/chr_evolution/goblin_cage_evolution_dl.png",
    "GoblinDrill_EV1": "image/chr_evolution/goblin_drill_evolution_dl.png",
    "GoblinGiant_EV1": "image/chr_evolution/goblin_giant_evolution_dl.png",
    "Hunter_EV1": "image/chr_evolution/hunter_evolution.png",
    "IceSpirits_EV1": "image/chr_evolution/icespirit_evolution_dl.png",
    "InfernoDragon_EV1": "image/chr_evolution/inferno_dragon_evolution_dl.png",
    "Knight_EV1": "image/chr_evolution/knight_evolution_dl.png",
    "RageBarbarian_EV1": "image/chr_evolution/lumberjack_evolution_dl.png",
    "MegaKnight_EV1": "image/chr_evolution/megaknight_evolution_dl.png",
    "MinionHorde_EV1": "image/chr_evolution/minionhorde_evolution.png",
    "Mortar_EV1": "image/chr_evolution/mortar_evolution_dl.png",
    "Musketeer_EV1": "image/chr_evolution/musketeer_evolution_dl.png",
    "Pekka_EV1": "image/chr_evolution/pekka_evolution_dl.png",
    "Princess_EV1": "image/chr_evolution/princess_evolution.png",
    "Ghost_EV1": "image/chr_evolution/royal_ghost_evolution.png",
    "RoyalGiant_EV1": "image/chr_evolution/royal_giant_evolution_dl.png",
    "RoyalHogs_EV1": "image/chr_evolution/royal_hogs_evolution.png",
    "RoyalRecruits_EV1": "image/chr_evolution/royal_recruit_evolution_dl.png",
    "SkeletonArmy_EV1": "image/chr_evolution/skeleton_army_evolution.png",
    "SkeletonBalloon_EV1": "image/chr_evolution/skeleton_balloon_evolution.png",
    "Skeletons_EV1": "image/chr_evolution/skeleton_evolution_dl.png",
    "Snowball_EV1": "image/chr_evolution/snowball_evolution_dl.png",
    "Tesla_EV1": "image/chr_evolution/tesla_evolution_dl.png",
    "Valkyrie_EV1": "image/chr_evolution/valkyrie_evolution_dl.png",
    "Wallbreakers_EV1": "image/chr_evolution/wall_breaker_evolution_dl.png",
    "Witch_EV1": "image/chr_evolution/witch_evolution.png",
    "Wizard_EV1": "image/chr_evolution/wizard_evolution_dl.png",
    "Zap_EV1": "image/chr_evolution/zap_evolution_dl.png",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch(url: str, target: Path) -> bytes:
    if target.is_file():
        return target.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "clasher-art-audit/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    target.write_bytes(data)
    return data


def _verified_object(
    *, relative_path: str, expected_sha1: str, cache: Path
) -> tuple[bytes, dict[str, Any]]:
    url = (
        "https://game-assets.clashroyaleapp.com/"
        f"{CONTENT_HASH}/{relative_path}"
    )
    data = _fetch(url, cache / relative_path)
    actual_sha1 = hashlib.sha1(data).hexdigest()
    if actual_sha1 != expected_sha1:
        raise ValueError(
            f"fingerprint SHA-1 mismatch for {relative_path}: "
            f"{actual_sha1} != {expected_sha1}"
        )
    return data, {
        "relative_path": relative_path,
        "url": url,
        "fingerprint_sha1": expected_sha1,
        "download_sha256": _sha256_bytes(data),
        "bytes": len(data),
    }


def _decode_sctx(data: bytes) -> Image.Image:
    stream = io.BytesIO(data)
    stream.seek(8)
    if stream.read(4) != b"SCTX":
        raise ValueError("missing SCTX marker")
    stream.seek(48)
    _file_type = struct.unpack("<I", stream.read(4))[0]
    width, height = struct.unpack("<HH", stream.read(4))
    storage_type = struct.unpack("<I", stream.read(4))[0]
    stream.seek(20, io.SEEK_CUR)
    key_value_size = struct.unpack("<I", stream.read(4))[0]
    stream.seek(key_value_size + 52, io.SEEK_CUR)
    if storage_type != 5:
        raise ValueError(f"unsupported current-client SCTX storage type {storage_type}")
    pixels = zstandard.decompress(stream.read())
    decoded = texture2ddecoder.decode_astc(pixels, width, height, 8, 8)
    return Image.frombytes("RGBA", (width, height), decoded, "raw", "BGRA")


def _image_from_png(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as source:
        return source.convert("RGBA")


def _difference_score(left: Image.Image, right: Image.Image) -> float:
    size = (160, 202)
    a = left.resize(size, Image.Resampling.LANCZOS).convert("RGB")
    b = right.resize(size, Image.Resampling.LANCZOS).convert("RGB")
    histogram = ImageChops.difference(a, b).histogram()
    total = sum(value * (index % 256) for index, value in enumerate(histogram))
    return total / (255.0 * 3.0 * size[0] * size[1])


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, (26, 30, 40))
    rgba = image.copy()
    rgba.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - rgba.width) // 2
    y = (size[1] - rgba.height) // 2
    canvas.paste(rgba.convert("RGB"), (x, y), rgba.getchannel("A"))
    return canvas


def _render_contact_sheet(
    *,
    hero_images: list[tuple[str, Image.Image, Image.Image]],
    evolution_images: list[tuple[str, Image.Image]],
    output: Path,
) -> None:
    columns = 7
    cell_width = 180
    cell_height = 252
    width = columns * cell_width
    hero_rows = math.ceil(len(hero_images) / columns)
    evolution_rows = math.ceil(len(evolution_images) / columns)
    header_height = 104
    section_height = 54
    height = (
        header_height
        + section_height
        + hero_rows * cell_height
        + section_height
        + evolution_rows * cell_height
    )
    sheet = Image.new("RGB", (width, height), (15, 18, 25))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 14), f"Clash Royale current-client HUD art authority — {CLIENT_VERSION}", fill="white", font=font)
    draw.text((18, 34), f"Official CDN content hash: {CONTENT_HASH}", fill=(184, 205, 255), font=font)
    draw.multiline_text((18, 55), DISCLAIMER, fill=(255, 213, 128), font=font, spacing=2)
    y = header_height
    draw.rectangle((0, y, width, y + section_height), fill=(31, 45, 70))
    draw.text((18, y + 19), "14 HERO HUD PORTRAITS (hero; base art inset)", fill="white", font=font)
    y += section_height
    for index, (name, hero, base) in enumerate(hero_images):
        x = (index % columns) * cell_width
        row_y = y + (index // columns) * cell_height
        panel = _fit(hero, (cell_width - 10, 218))
        sheet.paste(panel, (x + 5, row_y + 4))
        inset = _fit(base, (50, 64))
        sheet.paste(inset, (x + cell_width - 58, row_y + 12))
        draw.rectangle((x + cell_width - 59, row_y + 11, x + cell_width - 7, row_y + 77), outline=(255, 255, 255), width=1)
        draw.text((x + 7, row_y + 226), name, fill="white", font=font)
    y += hero_rows * cell_height
    draw.rectangle((0, y, width, y + section_height), fill=(65, 39, 94))
    draw.text((18, y + 19), "41 EVOLUTION HUD PORTRAITS", fill="white", font=font)
    y += section_height
    for index, (name, image) in enumerate(evolution_images):
        x = (index % columns) * cell_width
        row_y = y + (index // columns) * cell_height
        panel = _fit(image, (cell_width - 10, 218))
        sheet.paste(panel, (x + 5, row_y + 4))
        draw.text((x + 7, row_y + 226), name, fill="white", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="JPEG", quality=93, optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--cache", default="/private/tmp/clasher-current-client-art")
    parser.add_argument(
        "--manifest",
        default="reports/current_client_variant_art_authority_15_546_41.json",
    )
    parser.add_argument(
        "--contact-sheet",
        default="reports/current_client_variant_art_contact_sheet_15_546_41.jpg",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.repository_root).resolve()
    cache = Path(args.cache).resolve()
    gamedata_path = root / "gamedata.json"
    if _sha256(gamedata_path) != GAMEDATA_SHA256:
        raise ValueError("gamedata.json is not the accepted 15.546.41 snapshot")
    gamedata = json.loads(gamedata_path.read_text(encoding="utf-8"))

    fingerprint_bytes = _fetch(FINGERPRINT_URL, cache / "fingerprint.json")
    if _sha256_bytes(fingerprint_bytes) != FINGERPRINT_SHA256:
        raise ValueError("official fingerprint digest changed")
    fingerprint = json.loads(fingerprint_bytes)
    if fingerprint["version"] != CLIENT_VERSION or fingerprint["sha"] != CONTENT_HASH:
        raise ValueError("official fingerprint version/content hash mismatch")
    fingerprint_rows = {row["file"]: row["sha"] for row in fingerprint["files"]}

    hero_data = {
        row["heroData"]["name"]: (row, row["heroData"])
        for row in gamedata["items"]["spells"]
        if row.get("heroData")
    }
    if set(hero_data) != set(HERO_UI_STEMS):
        raise ValueError("hero UI mapping does not cover the exact current-client set")
    evolved_data = {
        row["evolvedSpellsData"]["name"]: row
        for row in gamedata["items"]["spells"]
        if row.get("evolvedSpellsData")
    }
    if set(evolved_data) != set(EVOLUTION_IMAGE_PATHS):
        raise ValueError("evolution image mapping does not cover the current-client set")

    hero_rows: list[dict[str, Any]] = []
    hero_images: list[tuple[str, Image.Image, Image.Image]] = []
    for hero_name in sorted(HERO_UI_STEMS):
        base_row, variant = hero_data[hero_name]
        stem = HERO_UI_STEMS[hero_name]
        sc_path = f"sc/{stem}.sc"
        sctx_path = f"sc/{stem}_0.sctx"
        base_path = base_row["highresImageFilename"]
        sc_data, sc_source = _verified_object(
            relative_path=sc_path,
            expected_sha1=fingerprint_rows[sc_path],
            cache=cache,
        )
        sctx_data, sctx_source = _verified_object(
            relative_path=sctx_path,
            expected_sha1=fingerprint_rows[sctx_path],
            cache=cache,
        )
        base_data, base_source = _verified_object(
            relative_path=base_path,
            expected_sha1=fingerprint_rows[base_path],
            cache=cache,
        )
        hero_image = _decode_sctx(sctx_data)
        base_image = _image_from_png(base_data)
        difference = _difference_score(hero_image, base_image)
        if difference <= 0.02:
            raise ValueError(f"hero portrait is not visually distinct: {hero_name}")
        hero_png = io.BytesIO()
        hero_image.save(hero_png, format="PNG")
        hero_rows.append(
            {
                "stable_key": f"card_action:{hero_name}",
                "hero_name": hero_name,
                "root_card": base_row["name"],
                "root_card_id": base_row["id"],
                "mana_cost": variant["manaCost"],
                "ui_descriptor": sc_source,
                "ui_texture": sctx_source,
                "base_highres": base_source,
                "decoded_portrait": {
                    "sha256": _sha256_bytes(hero_png.getvalue()),
                    "width": hero_image.width,
                    "height": hero_image.height,
                    "rgba": True,
                    "base_normalized_mean_absolute_difference": round(
                        difference, 8
                    ),
                    "visually_distinct_from_base": True,
                    "persisted_individual_file": False,
                },
                "disposition": {
                    "exact_current_client_hud_art_authority": True,
                    "visual_review_only": True,
                    "training_eligible": False,
                    "auto_label_eligible": False,
                },
            }
        )
        hero_images.append((hero_name, hero_image, base_image))
        if not sc_data:
            raise ValueError(f"empty SC descriptor: {hero_name}")

    evolution_rows: list[dict[str, Any]] = []
    evolution_images: list[tuple[str, Image.Image]] = []
    for evolution_name in sorted(EVOLUTION_IMAGE_PATHS):
        base_row = evolved_data[evolution_name]
        image_path = EVOLUTION_IMAGE_PATHS[evolution_name]
        data, source = _verified_object(
            relative_path=image_path,
            expected_sha1=fingerprint_rows[image_path],
            cache=cache,
        )
        image = _image_from_png(data)
        evolution_rows.append(
            {
                "stable_key": f"card_action:{evolution_name}",
                "evolution_name": evolution_name,
                "root_card": base_row["name"],
                "root_card_id": base_row["id"],
                "portrait": {
                    **source,
                    "width": image.width,
                    "height": image.height,
                    "rgba": image.mode == "RGBA",
                },
                "disposition": {
                    "exact_current_client_hud_art_authority": True,
                    "visual_review_only": True,
                    "training_eligible": False,
                    "auto_label_eligible": False,
                },
            }
        )
        evolution_images.append((evolution_name, image))

    contact_path = (root / args.contact_sheet).resolve()
    _render_contact_sheet(
        hero_images=hero_images,
        evolution_images=evolution_images,
        output=contact_path,
    )
    manifest_path = (root / args.manifest).resolve()
    payload = {
        "schema": SCHEMA,
        "client_authority": {
            "version": CLIENT_VERSION,
            "content_hash": CONTENT_HASH,
            "fingerprint_url": FINGERPRINT_URL,
            "fingerprint_sha256": FINGERPRINT_SHA256,
            "gamedata_path": "gamedata.json",
            "gamedata_sha256": GAMEDATA_SHA256,
        },
        "license_and_use": {
            "copyright_owner": "Supercell Oy",
            "asset_license": "restricted Supercell fan-content use; not open source",
            "fan_content_policy_url": "https://supercell.com/en/fan-content-policy/",
            "fan_content_policy_last_updated": "2023-09-27",
            "required_notice": DISCLAIMER,
            "scope": "display, identification, and discussion audit only",
            "model_training_authorized": False,
            "automatic_video_labeling_authorized": False,
            "redistribution_of_individual_decoded_portraits": False,
        },
        "decoder": {
            "implementation": "bounded local SCTX container parser in this script",
            "texture_decoder": {
                "package": "texture2ddecoder",
                "version": "1.0.6",
                "license": "MIT",
                "project": "https://github.com/K0lb3/texture2ddecoder",
            },
            "zstandard_binding": {
                "package": "zstandard",
                "version": "0.25.0",
                "license": "BSD-3-Clause",
                "project": "https://github.com/indygreg/python-zstandard",
            },
            "reference_only_not_used_in_persisted_artifacts": {
                "project": "https://github.com/milanmaldini/cr-sc-dump2026",
                "commit": "46a4a2d6f0c01bf0549cde70dfcc35e0c9849b7c",
                "license_file_present": False,
            },
        },
        "contract": {
            "official_cdn_objects_match_fingerprint_sha1": True,
            "hero_portraits_are_distinct_ui_card_textures": True,
            "gamedata_hero_highres_paths_are_base_art_not_hero_art": True,
            "all_individual_decoded_hero_portraits_are_ephemeral": True,
            "base_family_auto_label_forbidden": True,
            "contact_sheet_is_review_only": True,
        },
        "counts": {
            "hero_variants": len(hero_rows),
            "hero_portraits_exact_current_client": len(hero_rows),
            "hero_portraits_persisted_individually": 0,
            "evolution_variants": len(evolution_rows),
            "evolution_portraits_exact_current_client": len(evolution_rows),
        },
        "heroes": hero_rows,
        "evolutions": evolution_rows,
        "contact_sheet": {
            "path": contact_path.relative_to(root).as_posix(),
            "sha256": _sha256(contact_path),
            "width": Image.open(contact_path).width,
            "height": Image.open(contact_path).height,
            "contains_required_notice": True,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(manifest_path)
    print(_sha256(manifest_path))
    print(contact_path)
    print(_sha256(contact_path))


if __name__ == "__main__":
    main()
