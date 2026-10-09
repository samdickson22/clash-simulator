"""Load the existing exact decoder into an isolated copy of the sealed ABI."""
import math
import uuid
from .loading import ROOT, V4, imports, module


def selected_body_threshold(config, calibration):
    # The selection owner supplies the sealed selected value in calibration or
    # config. There is deliberately no default and no runtime threshold fitting.
    values = [source['body_threshold'] for source in (config, calibration)
              if 'body_threshold' in source]
    if not values:
        raise ValueError('V4 requires the sealed selected body_threshold')
    value = values[0]
    if (type(value) not in (int, float) or not math.isfinite(value) or
            value not in [i/10 for i in range(1, 10)] or any(v != value for v in values)):
        raise ValueError('Selected body_threshold must agree and use the registered 0.1..0.9 grid')
    return value


def vectorized_runtime():
    # DecoderAdapter.install replaces module globals. Give each live sensor its
    # own module so reference sensors and other runtimes remain independent.
    runtime = module('clasher_live_pixel_v4_'+uuid.uuid4().hex,
                     ROOT/'src/clasher/vision/l1_v4.py')
    records = module('clasher_live_decoder_records_v4', V4/'l1/decoder_records_v4.py')
    decoder = module('clasher_live_vectorized_decoder_v4', V4/'l1/vectorized_decoder_v4.py')
    with imports(aliases={'decoder_records_v4': records, 'vectorized_decoder_v4': decoder}):
        adapter = module('clasher_live_decoder_adapter_v4', V4/'l1/vectorized_runtime_adapter_v4.py')
    return runtime, adapter.DecoderAdapter(runtime).install()
