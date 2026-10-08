"""One backend timing selection shared by planning and verification."""
import json
import math
from pathlib import Path
from .loading import V4


def backend_timing(config):
    backend = config.get('backend', 'offline-renderer-grpc')
    path = Path(config.get('timing_path') or V4/'actuation/backend-timing.json')
    row = json.loads(path.read_text())['backends'][backend]
    ticks = float(row['p50_ticks'])
    if not math.isfinite(ticks) or ticks < 0:
        raise ValueError('Backend p50_ticks must be finite and nonnegative')
    # Measured wall-latency equivalents, rounded to the nearest engine tick.
    return backend, path, row, math.floor(ticks+.5)
