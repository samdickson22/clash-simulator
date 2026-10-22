"""Relocated audit inputs retain the frozen reader choices and calculations."""
import gzip
import json
import shutil
from pathlib import Path

import pytest

from bot.pretrain_v1 import probe_roots as P


def corpus(parent):
    roots = {name: str(parent/name) for name in ('defense', 'spell', 'mirror')}
    for value in roots.values():
        Path(value).mkdir(parents=True)
    defense, spell, mirror = P.root_paths(roots)
    (defense/'events.json').write_text(json.dumps([{'game': 'g'}]))
    (spell/'opportunities.json').write_text('[]')
    frozen = defense/'inputs/g/records.jsonl.gz'
    frozen.parent.mkdir(parents=True)
    with gzip.open(frozen, 'wt') as output:
        output.write('{"tick":90}\n{"tick":95}\n')
    (mirror/'g').mkdir()
    (mirror/'g/decisions.jsonl').write_text('')
    # A fallback with different ticks must stay unused while frozen records exist.
    (mirror/'g/records.jsonl').write_text('{"tick":100}\n')
    return roots


def defaults(monkeypatch, roots):
    for name, path in zip(('DEF', 'SPELL', 'MIRROR'), P.root_paths(roots)):
        monkeypatch.setattr(P, name, path)


def test_input_inventory_preserves_frozen_fallback_and_optional_projectiles(tmp_path, monkeypatch):
    source = corpus(tmp_path/'source')
    shutil.copytree(tmp_path/'source', tmp_path/'copy')
    target = {key: str(tmp_path/'copy'/key) for key in source}
    defaults(monkeypatch, source)
    before = P.input_paths()
    after = P.input_paths(roots=target)
    assert [p.relative_to(tmp_path/'source') for p in before] == [
        p.relative_to(tmp_path/'copy') for p in after]
    assert all(a.read_bytes() == b.read_bytes() for a, b in zip(before, after))
    assert not any(p.name == 'records.jsonl' for p in after)
    projectile = Path(target['mirror'])/'g/projectiles.jsonl'
    projectile.write_text('')
    assert projectile in P.input_paths(roots=target)
    assert projectile not in P.input_paths()
    frozen = Path(target['defense'])/'inputs/g/records.jsonl.gz'
    frozen.unlink()
    assert Path(target['mirror'])/'g/records.jsonl' in P.input_paths(roots=target)
    assert P.DEF == Path(source['defense'])


def test_replay_uses_explicit_roots_without_mutating_default_reader(tmp_path, monkeypatch):
    source = corpus(tmp_path/'source')
    shutil.copytree(tmp_path/'source', tmp_path/'copy')
    target = {key: str(tmp_path/'copy'/key) for key in source}
    defaults(monkeypatch, source)
    monkeypatch.setattr(P.F, 'observe', lambda record, extras, history: {'tick': record['tick']})
    monkeypatch.setattr(P, 'dist', lambda model, feat, rec, gap: {'tick': rec['tick'], 'gap': gap})
    expected = P.replay('g', object(), None)
    assert sorted(expected) == [90, 95]
    assert P.replay('g', object(), None, roots=target) == expected
    (Path(target['defense'])/'inputs/g/records.jsonl.gz').unlink()
    assert sorted(P.replay('g', object(), None, roots=target)) == [100]
    assert P.replay('g', object(), None) == expected


def test_evaluate_reads_explicit_audit_roots_without_default_files(tmp_path, monkeypatch):
    roots = corpus(tmp_path/'source')
    (Path(roots['defense'])/'events.json').write_text('[]')
    expected = P.evaluate(object(), ckpt='same-policy', roots=roots)
    defaults(monkeypatch, roots)
    assert P.evaluate(object(), ckpt='same-policy') == expected
    monkeypatch.setattr(P, 'DEF', tmp_path/'absent-default')
    assert P.evaluate(object(), ckpt='same-policy', roots=roots) == expected
    with pytest.raises(FileNotFoundError):
        P.evaluate(object(), ckpt='same-policy')


@pytest.mark.parametrize('roots', [[], {}, {'defense': '/d', 'spell': '/s'},
    {'defense': 'relative', 'spell': '/s', 'mirror': '/m'},
    {'defense': '/same', 'spell': '/same', 'mirror': '/m'},
    {'defense': 1, 'spell': '/s', 'mirror': '/m'}])
def test_invalid_explicit_roots_fail_before_reading(roots):
    with pytest.raises(ValueError):
        P.input_paths(roots=roots)
