from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/current_client_variant_art_authority_15_546_41.json"
CONTACT_SHEET = (
    ROOT / "reports/current_client_variant_art_contact_sheet_15_546_41.jpg"
)
CONTENT_HASH = "ef863332281e7c47d628d23a80881ed300d47ede"
CDN_PREFIX = f"https://game-assets.clashroyaleapp.com/{CONTENT_HASH}/"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_exact_current_client_variant_closure_is_complete() -> None:
    payload = _load()
    assert payload["schema"] == "clasher.current_client.variant_art_authority.v1"
    assert payload["client_authority"] == {
        "content_hash": CONTENT_HASH,
        "fingerprint_sha256": (
            "53eed16e1e65f81637bb212680b3faf32036214dc13b89bb3e8f440556b19794"
        ),
        "fingerprint_url": f"{CDN_PREFIX}fingerprint.json",
        "gamedata_path": "gamedata.json",
        "gamedata_sha256": (
            "3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a"
        ),
        "version": "15.546.41",
    }
    assert payload["counts"] == {
        "evolution_portraits_exact_current_client": 41,
        "evolution_variants": 41,
        "hero_portraits_exact_current_client": 14,
        "hero_portraits_persisted_individually": 0,
        "hero_variants": 14,
    }
    assert len(payload["heroes"]) == 14
    assert len(payload["evolutions"]) == 41


def test_hero_art_uses_distinct_fingerprinted_ui_textures() -> None:
    payload = _load()
    rows = payload["heroes"]
    assert len({row["stable_key"] for row in rows}) == 14
    assert len({row["decoded_portrait"]["sha256"] for row in rows}) == 14
    for row in rows:
        descriptor = row["ui_descriptor"]
        texture = row["ui_texture"]
        assert descriptor["url"].startswith(CDN_PREFIX)
        assert texture["url"].startswith(CDN_PREFIX)
        assert descriptor["relative_path"].startswith("sc/ui_card_")
        assert descriptor["relative_path"].endswith("_hero.sc")
        assert texture["relative_path"].endswith("_hero_0.sctx")
        assert len(descriptor["fingerprint_sha1"]) == 40
        assert len(texture["fingerprint_sha1"]) == 40
        decoded = row["decoded_portrait"]
        assert decoded["width"] == 394
        assert decoded["height"] == 500
        assert decoded["rgba"] is True
        assert decoded["visually_distinct_from_base"] is True
        assert decoded["base_normalized_mean_absolute_difference"] > 0.02
        assert decoded["persisted_individual_file"] is False
        disposition = row["disposition"]
        assert disposition["exact_current_client_hud_art_authority"] is True
        assert disposition["training_eligible"] is False
        assert disposition["auto_label_eligible"] is False


def test_evolution_art_uses_all_fingerprinted_portrait_pngs() -> None:
    payload = _load()
    rows = payload["evolutions"]
    assert len({row["stable_key"] for row in rows}) == 41
    assert len({row["portrait"]["relative_path"] for row in rows}) == 41
    assert len({row["portrait"]["download_sha256"] for row in rows}) == 41
    for row in rows:
        portrait = row["portrait"]
        assert portrait["url"].startswith(CDN_PREFIX)
        assert portrait["relative_path"].startswith("image/chr_evolution/")
        assert portrait["relative_path"].endswith(".png")
        assert len(portrait["fingerprint_sha1"]) == 40
        assert portrait["width"] > 0
        assert portrait["height"] > 0
        assert row["disposition"]["training_eligible"] is False
        assert row["disposition"]["auto_label_eligible"] is False


def test_contact_sheet_and_safe_use_contract_are_exact() -> None:
    payload = _load()
    sheet = payload["contact_sheet"]
    assert sheet["path"] == CONTACT_SHEET.relative_to(ROOT).as_posix()
    assert sheet["width"] == 1260
    assert sheet["height"] == 2228
    assert sheet["contains_required_notice"] is True
    assert _sha256(CONTACT_SHEET) == sheet["sha256"]
    license_use = payload["license_and_use"]
    assert license_use["copyright_owner"] == "Supercell Oy"
    assert license_use["model_training_authorized"] is False
    assert license_use["automatic_video_labeling_authorized"] is False
    assert license_use["redistribution_of_individual_decoded_portraits"] is False
    assert "unofficial" in license_use["required_notice"]
