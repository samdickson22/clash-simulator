"""Exact decoder source closure and platform-specific admission handoff."""
from dataclasses import asdict, dataclass
import hashlib
import json
import platform
import sys
from .loading import ROOT


IMPLEMENTATION = 'clasher.live.isolated-vectorized-decoder.v1'
SOURCES = ('src/clasher/vision/l1_v4.py',
    'reports/strategy_council_20260928/live-loop/v4/l1/decoder_records_v4.py',
    'reports/strategy_council_20260928/live-loop/v4/l1/vectorized_decoder_v4.py',
    'reports/strategy_council_20260928/live-loop/v4/l1/vectorized_runtime_adapter_v4.py',
    'src/clasher/live/loading.py', 'src/clasher/live/perception_adapter.py',
    'src/clasher/live/perception.py', 'src/clasher/live/decoder_binding.py')


@dataclass(frozen=True)
class ProofReference:
    path: str
    sha256: str


@dataclass(frozen=True)
class DecoderScope:
    device: str
    platform: str
    torch_version: str
    backend: str = 'torch-eager-fp32'


@dataclass(frozen=True)
class DecoderBinding:
    implementation: str
    source_hashes: tuple
    source_closure_sha256: str
    equality_proof: ProofReference
    timing_proof: ProofReference
    scopes: tuple


def source_hashes():
    return tuple((name, hashlib.sha256((ROOT/name).read_bytes()).hexdigest()) for name in SOURCES)


def closure_hash(hashes):
    return hashlib.sha256(json.dumps(dict(hashes), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def current_scope(device):
    import torch
    return DecoderScope(device, sys.platform+'/'+platform.machine(), str(torch.__version__))


def validate_binding(binding):
    if type(binding) is not DecoderBinding or binding.implementation != IMPLEMENTATION:
        raise ValueError('Exact decoder implementation binding required')
    actual = source_hashes()
    if (type(binding.source_hashes) is not tuple or binding.source_hashes != actual
            or binding.source_closure_sha256 != closure_hash(actual)):
        raise ValueError('Decoder source closure differs from admitted implementation')
    if (type(binding.scopes) is not tuple or not binding.scopes
            or any(type(s) is not DecoderScope or any(type(v) is not str or not v
                for v in (s.device, s.platform, s.torch_version, s.backend)) for s in binding.scopes)
            or len(set(binding.scopes)) != len(binding.scopes)
            or any(type(p) is not ProofReference for p in (binding.equality_proof, binding.timing_proof))):
        raise ValueError('Decoder equality/timing proof and device scopes required')


def qualify(selection, config):
    """Diagnostic measurement is explicitly separate from decoder admission."""
    if not config.get('vectorized_decoder'):
        return dict(scope='authenticated-final-joint-scalar', decoder_admitted=False)
    actual = source_hashes()
    scope = current_scope(config.get('device', 'cpu'))
    if config.get('decoder_diagnostic'):
        return dict(scope='unadmitted-decoder-diagnostic-qualification', decoder_admitted=False,
                    implementation=IMPLEMENTATION, source_hashes=dict(actual),
                    source_closure_sha256=closure_hash(actual), device_scope=asdict(scope))
    binding = selection.decoder_binding
    if binding is None:
        raise ValueError('DecoderAdapter is unadmitted; explicit mock-only diagnostic required')
    validate_binding(binding)
    if scope not in binding.scopes:
        raise ValueError('Decoder admission does not cover this device/platform/backend scope')
    return dict(scope='authenticated-final-joint-admitted-decoder', decoder_admitted=True,
                binding=asdict(binding), device_scope=asdict(scope))
