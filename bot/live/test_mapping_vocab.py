"""Combined completed vocabulary, immutable canonical projections and host guards.

Only public resources, source fixtures and private temporary filesystem trees.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from bot.live.translate import LiveTranslator, load_vocab
from bot.live.test_mapping_projection import rt, clean_policy, unit, frame, OWN
from bot.players.royalesim_translate import complete_vocab

ROOT = Path(__file__).resolve().parents[3]
HELPER = '381138734b2fcdd45434685b3b764f30c70583c51f8cc9fc4052d9b55df29fa6'


def measured():
    return json.loads((ROOT / 'base/bot/players/royalesim_vocab.json').read_text())


def test_complete_vocab_preserves_every_measured_value_and_is_immutable_idempotent(rt):
    vocab = measured()
    before = copy.deepcopy(vocab)
    done = complete_vocab(rt, vocab)
    for table, original in before.items():
        if isinstance(original, dict):
            for key, value in original.items():
                assert done[table][key] == value
        else:
            assert done[table] == original
    assert vocab == before and complete_vocab(rt, done) == done
    for (token, kind) in rt.R.templates:
        k = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity').index(kind)
        assert f'{token}/{k}' in done['objects']
        if k < 2:
            assert rt.R.builder.token_names[token] in done['units']
    done['units']['Knight'][0] = -1
    assert vocab == before


def test_both_constructor_vocab_paths_complete_without_mutating_the_caller(rt):
    explicit = measured()
    token, kind = explicit['units'].pop('Knight')
    explicit.setdefault('objects', {}).pop(f'{token}/{kind}', None)
    explicit['units']['reviewed-measured-alias'] = [token, kind]
    before = copy.deepcopy(explicit)
    tr = LiveTranslator(rt, OWN, vocab=explicit)
    assert explicit == before
    assert tr.vocab['units']['Knight'] == [token, kind]
    assert tr.vocab['units']['reviewed-measured-alias'] == [token, kind]
    assert tr.vocab['objects'][f'{token}/{kind}'] == [token, kind]
    default = LiveTranslator(rt, OWN)
    assert default.vocab == load_vocab(rt) == complete_vocab(rt, measured())


def test_loader_keeps_token_hash_guard(rt, tmp_path):
    vocab = measured()
    vocab['meta']['token_sha256'] = '0' * 64
    path = tmp_path / 'different-token-vocab.json'
    path.write_text(json.dumps(vocab))
    with pytest.raises(ValueError, match='another token vocabulary'):
        load_vocab(rt, path)


def test_completed_vocab_does_not_enable_an_unsupported_detector_family(rt):
    tr = LiveTranslator(rt, OWN)
    assert len(tr.cards.main) == 56
    got, plays = tr.assign(frame([unit('Barbarian', 'Barbarians')]))
    assert got[0][0] is None and not plays
    assert tr.last_projections[0]['disposition'] == 'unplaced'
    assert tr.unknown_card == 'drop' and tr.legacy_mapping_compat is None


def test_exact_source_helper_dependency_is_packaged():
    import bot.players.royalesim_translate as module
    assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == HELPER
    assert hashlib.sha256((ROOT / 'release/bot/players/royalesim_translate.py').read_bytes()).hexdigest() == HELPER
    # The live changes are exactly the landed two-call delta on the reviewed R2 source.
    old = (ROOT / 'prior-review/R2-translate.py').read_text()
    expected = old.replace('    return vocab\n',
                           '    from bot.players.royalesim_translate import complete_vocab\n    return complete_vocab(rt, vocab)\n', 1)
    expected = expected.replace('        self.rt, self.vocab = rt, vocab or load_vocab(rt)\n',
                                '        from bot.players.royalesim_translate import complete_vocab\n'
                                '        self.rt, self.vocab = rt, complete_vocab(rt, vocab or load_vocab(rt))\n', 1)
    assert Path(__file__).with_name('translate.py').read_text() == expected


@pytest.fixture
def guarded_target(tmp_path):
    spec = importlib.util.spec_from_file_location('combined_host_guard', ROOT / 'verify_host_package.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    package, repo, yolo = tmp_path / 'package', tmp_path / 'repo', tmp_path / 'yolo'
    shutil.copytree(ROOT / 'release', package / 'release')
    shutil.copy2(ROOT / 'host-base-guards.json', package / 'host-base-guards.json')
    for p in (ROOT / 'rollback').rglob('*'):
        if p.is_file():
            name = str(p.relative_to(ROOT / 'rollback'))
            dst = guard.target_path(name, repo, yolo)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    vocab = repo / 'bot/players/royalesim_vocab.json'
    shutil.copy2(ROOT / 'base/bot/players/royalesim_vocab.json', vocab)
    return guard, package, repo, yolo


def test_read_only_host_base_and_complete_paired_rollback(guarded_target):
    guard, package, repo, yolo = guarded_target
    result = guard.verify(package, repo, yolo, 'base')
    assert result['validated_files'] == 5 and result['unchanged_assets'] == 1
    assert not result['deployment_authorized'] and not result['detector_enablement_authorized']
    for p in (package / 'release').rglob('*'):
        if p.is_file():
            dst = guard.target_path(str(p.relative_to(package / 'release')), repo, yolo)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    assert guard.verify(package, repo, yolo, 'released')['validated_files'] == 7
    # Restoring only the old four-file rollback is insufficient with this dependency.
    for p in (ROOT / 'rollback').rglob('*'):
        if p.is_file() and p.name != 'royalesim_translate.py':
            shutil.copy2(p, guard.target_path(str(p.relative_to(ROOT / 'rollback')), repo, yolo))
    with pytest.raises(ValueError, match='royalesim_translate'):
        guard.verify(package, repo, yolo, 'rollback')
    shutil.copy2(ROOT / 'rollback/bot/players/royalesim_translate.py', repo / 'bot/players/royalesim_translate.py')
    assert guard.verify(package, repo, yolo, 'rollback')['validated_files'] == 5


@pytest.mark.parametrize('failure', ['helper-target', 'helper-payload', 'dependency-omitted',
                                    'partial-vocab-live', 'unchanged-vocab', 'conflicting-added-data'])
def test_host_package_guards_fail_closed(guarded_target, failure):
    guard, package, repo, yolo = guarded_target
    if failure == 'helper-target':
        (repo / 'bot/players/royalesim_translate.py').unlink()
    elif failure == 'helper-payload':
        with (package / 'release/bot/players/royalesim_translate.py').open('a') as stream:
            stream.write('\n# incomplete dependency\n')
    elif failure == 'dependency-omitted':
        p = package / 'host-base-guards.json'
        data = json.loads(p.read_text())
        del data['release_sha256']['bot/players/royalesim_translate.py']
        p.write_text(json.dumps(data))
    elif failure == 'partial-vocab-live':
        shutil.copy2(ROOT / 'source-base/bot/live/translate.py', repo / 'bot/live/translate.py')
    elif failure == 'unchanged-vocab':
        (repo / 'bot/players/royalesim_vocab.json').write_text('{}')
    else:
        p = repo / 'bot/live/engine_body_aliases.json'
        p.write_text('{}')
    before = {str(p): p.read_bytes() for root in (repo, yolo) for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):
        guard.verify(package, repo, yolo)
    assert before == {str(p): p.read_bytes() for root in (repo, yolo) for p in root.rglob('*') if p.is_file()}
