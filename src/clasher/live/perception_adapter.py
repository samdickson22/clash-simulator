"""Load the existing exact decoder into an isolated copy of the sealed ABI."""
import uuid
from .loading import ROOT, V4, imports, module


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
