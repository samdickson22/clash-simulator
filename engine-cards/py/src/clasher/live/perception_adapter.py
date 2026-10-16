"""Load the existing exact decoder into an isolated copy of the sealed ABI."""
import uuid
from .loading import ROOT, V4, imports, module


class PublicTowerAdapter:
    """Attach fixed-slot public observations without changing decoder tracks."""
    def __init__(self, artifact=None, geometry=None, *, score_artifact=None):
        import json
        from pathlib import Path
        from .tower_channel import TowerChannel, MATRIX
        matrix = json.loads(Path(geometry).read_text())['tile_to_pixel'] if geometry else MATRIX
        self.channel = TowerChannel(artifact, matrix)
        from .crown_counter import CrownCounterReader
        from .result_screen import ResultScreenDetector
        self.crowns = CrownCounterReader(score_artifact)
        self.results = ResultScreenDetector(score_artifact)
        self.last_result = None

    def observe(self, public, pixels, *, result=None):
        from dataclasses import replace
        if result is not None:
            from .public_root import apply_match_result
            return apply_match_result(public,result)
        crowns = self.crowns.read(pixels,public.episode_id,public.timestamp_ms)
        self.last_result = self.results.step(pixels,public.episode_id,public.timestamp_ms,crowns)
        if self.last_result is not None:
            from .public_root import apply_match_result
            return apply_match_result(public,self.last_result.as_match_result())
        return replace(public, tower_observations=self.channel.step(
            pixels, public.episode_id, public.timestamp_ms,crowns=crowns))


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
