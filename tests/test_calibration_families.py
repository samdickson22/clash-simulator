"""A holdout cannot become fresh through another seat, name, or registry reopen."""

import sqlite3

import pytest

from clasher.rl.calibration_families import (
    FamilyExposure,
    record_exposure,
    register_family,
    require_unopened_acceptance,
)
from clasher.rl.native_match_registry import register_native_root

PROTOCOL = "a" * 64


def config(seed=3, swapped=False):
    return {
        "rndSeed": seed,
        "battle": {
            "deck0": [3, 4] if swapped else [1, 2],
            "deck1": [1, 2] if swapped else [3, 4],
        },
    }


def register(path, configs=None, name="family", role="acceptance"):
    return register_family(
        path,
        configs or [config(), config(swapped=True)],
        family_id=name,
        role=role,
        protocol_sha256=PROTOCOL,
    )


def test_seats_cannot_be_reassigned_or_membership_changed(tmp_path):
    path = tmp_path / "ledger.sqlite"
    family = register(path)
    assert register(path, list(reversed([config(), config(swapped=True)]))) == family
    with pytest.raises(ValueError, match="already belongs"):
        register(path, [config(swapped=True)], name="fresh")
    with pytest.raises(ValueError, match="immutable"):
        register(path, [config(), config(4)])
    with pytest.raises(ValueError, match="immutable"):
        register(path, role="training")
    assert require_unopened_acceptance(path, "family", PROTOCOL) == family


@pytest.mark.parametrize("purpose", ["evaluation", "repair", "selection"])
def test_opened_family_cannot_reacquire_freshness(tmp_path, purpose):
    path = tmp_path / "ledger.sqlite"
    register(path)
    record_exposure(
        path,
        FamilyExposure(family_id="family", purpose=purpose, evidence_sha256="b" * 64),
    )
    register(path)  # Idempotent registration cannot erase exposure.
    with pytest.raises(ValueError, match="permanently"):
        require_unopened_acceptance(path, "family", PROTOCOL)
    with pytest.raises(ValueError, match="cannot enter training"):
        record_exposure(
            path,
            FamilyExposure(
                family_id="family", purpose="training", evidence_sha256="c" * 64
            ),
        )


def test_legacy_acceptance_cannot_be_relabelled_prospective(tmp_path):
    path = tmp_path / "ledger.sqlite"
    register_native_root(path, config(), role="acceptance")
    with pytest.raises(ValueError, match="prospective"):
        register(path)


def test_old_development_can_be_grouped_but_never_admitted(tmp_path):
    path = tmp_path / "ledger.sqlite"
    register_native_root(path, config(), role="development")
    register(path, role="development")
    with pytest.raises(ValueError, match="role"):
        require_unopened_acceptance(path, "family", PROTOCOL)
    with pytest.raises(ValueError, match="already belongs"):
        register(path, [config()], name="new-acceptance")


def test_conflict_rolls_back_new_members_atomically(tmp_path):
    path = tmp_path / "ledger.sqlite"
    register(path)
    with pytest.raises(ValueError, match="already belongs"):
        register(path, [config(99), config()], name="bad")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM native_roots").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM calibration_members").fetchone()[0] == 2
    register(path, [config(99)], name="independent")


def test_protocol_digest_and_known_family_required(tmp_path):
    path = tmp_path / "ledger.sqlite"
    register(path)
    with pytest.raises(ValueError, match="protocol"):
        require_unopened_acceptance(path, "family", "d" * 64)
    with pytest.raises(ValueError, match="unregistered"):
        record_exposure(
            path,
            FamilyExposure(
                family_id="missing", purpose="repair", evidence_sha256="b" * 64
            ),
        )


def test_development_audit_checks_actual_membership(tmp_path):
    from clasher.rl.calibration_families import require_development_member

    path = tmp_path / "ledger.sqlite"
    dev = register(path, role="development")
    assert require_development_member(path, dev.family_id, dev.root_ids[0]) == dev
    other = register(path, [config(99)], name="held-out")
    with pytest.raises(ValueError, match="not a declared"):
        require_development_member(path, dev.family_id, other.root_ids[0])
    with pytest.raises(ValueError, match="not a declared"):
        require_development_member(path, other.family_id, other.root_ids[0])
