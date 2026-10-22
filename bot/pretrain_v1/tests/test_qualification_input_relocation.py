"""A fresh relocated closure keeps payloads and rejects missing required pins."""
import importlib.util
import json
from pathlib import Path
import tempfile

import pytest

SPEC = importlib.util.spec_from_file_location('qualification_relocation', Path(__file__).resolve().parents[3]/
    'reports/bot/pretrain-v1/sweep/relocate_qualification_inputs.py')
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


@pytest.fixture
def inputs(tmp_path):
    rows = []

    def put(name, value):
        path = tmp_path/name
        raw = value if isinstance(value, bytes) else R.encoded(value)
        path.write_bytes(raw)
        ref = dict(path=str(path), sha256=R.digest(raw))
        rows.append(dict(ref, bytes=len(raw)))
        return ref

    payload = put('policy.pt', b'exact tensor bytes\x00\xff')
    nested = put('bank.json', {'anchor': payload, 'cases': [{'seed': 7, 'level': 9}]})
    optional = put('old-stage.json', {'path': '/historical/remote/only.pt', 'sha256': 'a'*64})
    config = dict(qualification_only=True, host='127x09', size='M', banks=nested,
                  precision_registration={'path': '/old/PENDING/precision.json', 'sha256': '0'*64},
                  live={'environment': {'BOT_RL_K4CW_FAST': 'student:'+payload['path']+'@.6'}},
                  workers=32, steps_per_update=262144)
    config_path = tmp_path/'config.json'
    config_path.write_bytes(R.encoded(config))
    with tempfile.TemporaryDirectory(prefix='relocation-test-', dir='/mpac/sdicks02/jobs/clasher') as parent:
        yield dict(put=put, rows=rows, config=config, config_path=config_path, payload=payload,
                   nested=nested, optional=optional, out=Path(parent)/'fresh',
                   readiness={'127x09': {'runtime_root': '/mpac/sdicks02/repos/clasher-ready/runtime',
                                        'actor_source_root': '/mpac/sdicks02/repos/clasher-ready/actors'}})


def run(i):
    i['config_path'].write_bytes(R.encoded(i['config']))
    return R.prepare([i['config_path']], {'files': i['rows']}, i['readiness'], i['out'])


def test_rewrites_required_refs_but_retains_cases_payload_and_optional_provenance(inputs):
    i = inputs
    result = run(i)
    config = json.loads(Path(result['configs'][0]['path']).read_bytes())
    bank_ref = config['banks']
    bank = json.loads(Path(bank_ref['path']).read_bytes())
    assert bank['cases'] == [{'seed': 7, 'level': 9}]
    assert R.digest(Path(bank_ref['path']).read_bytes()) == bank_ref['sha256']
    assert Path(bank['anchor']['path']).read_bytes() == Path(i['payload']['path']).read_bytes()
    assert bank['anchor']['sha256'] == i['payload']['sha256']
    assert bank_ref['sha256'] != i['nested']['sha256']
    original = i['optional']['path']
    assert Path(result['files'][original]['path']).read_bytes() == Path(original).read_bytes()
    assert result['files'][original]['rewritten'] is False
    assert config['precision_registration']['sha256'] == '0'*64
    assert Path(config['precision_registration']['path']).is_relative_to(i['out']/'PENDING')
    assert not Path(config['precision_registration']['path']).exists()
    assert config['workers'] == 32 and config['steps_per_update'] == 262144
    assert config['live']['environment']['BOT_RL_K4CW_FAST'] == 'student:'+bank['anchor']['path']+'@.6'
    assert all(Path(path).is_relative_to(i['out']) for path in config['audit_roots'].values())
    assert result['status'] == 'PREPARED-NOT-GO' and result['remote_writes'] is False
    with pytest.raises(ValueError, match='fresh output'):
        run(i)


def test_required_unknown_reference_is_not_hidden_as_optional_metadata(inputs):
    inputs['config']['banks'] = inputs['optional']
    with pytest.raises(ValueError, match='absent from pinned inventory'):
        run(inputs)


def test_source_hash_change_fails_before_output_creation(inputs):
    Path(inputs['payload']['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='source input changed'):
        run(inputs)
    assert not inputs['out'].exists()


@pytest.mark.parametrize('edit', [dict(size='L'), dict(host='127x12'), dict(qualification_only=False)])
def test_wrong_arm_host_or_registered_scope_is_rejected(inputs, edit):
    inputs['config'].update(edit)
    with pytest.raises(ValueError, match='matching qualification'):
        run(inputs)


@pytest.mark.parametrize('reference', [dict(path='/old/PENDING/../escape', sha256='0'*64),
    dict(path='/old/PENDING/proof.json', sha256='a'*64),
    dict(path='relative/PENDING/proof.json', sha256='0'*64)])
def test_pending_cannot_escape_or_invent_evidence(inputs, reference):
    inputs['config']['precision_registration'] = reference
    with pytest.raises(ValueError):
        run(inputs)


def test_symlink_output_cannot_redirect_outside_allowed_root(inputs, tmp_path):
    redirect = inputs['out'].parent/'redirect'
    redirect.symlink_to(tmp_path, target_is_directory=True)
    inputs['out'] = redirect/'new-output'
    with pytest.raises(ValueError, match='fresh output'):
        run(inputs)
    assert not (tmp_path/'new-output').exists()
