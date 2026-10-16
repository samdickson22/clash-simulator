"""Public HUD score and scoring-banner reader; never uses native labels."""
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class CrownObservation:
    episode_id: str
    timestamp_ms: int
    crowns: tuple[int | None, int | None]  # opponent, own
    confidence: float

    def __post_init__(self):
        if type(self.timestamp_ms) is not int or self.timestamp_ms < 0:
            raise ValueError('Invalid crown timestamp')
        if not isinstance(self.crowns, tuple) or len(self.crowns) != 2 or any(c is not None and (type(c) is not int or not 0 <= c <= 3) for c in self.crowns):
            raise ValueError('Invalid public crown counts')
        if self.crowns == (None, None) or self.crowns == (3, 3):
            raise ValueError('Crown observation requires a legible score')
        if not math.isfinite(self.confidence) or not 0 < self.confidence <= 1:
            raise ValueError('Invalid crown confidence')


def color_feature(image, box, size):
    import cv2
    import numpy as np
    x1,y1,x2,y2 = box
    return cv2.resize(image[y1:y2,x1:x2],size,interpolation=cv2.INTER_AREA).astype(np.float32).ravel()/255


def read_templates(feature, table, limit, margin):
    import numpy as np
    distances = {key:float(np.sqrt(np.mean((np.asarray(values,np.float32)-feature)**2,axis=1)).min()) for key,values in table.items() if values}
    if not distances: return None
    ordered = sorted(distances,key=distances.get)
    distance = distances[ordered[0]]
    if distance > limit or (len(ordered)>1 and distances[ordered[1]]-distance < margin):
        return None
    return ordered[0],1-distance


class CrownCounterReader:
    """Fixed public HUD regions plus the earlier three-icon score animation.

    A score is not a slot identity or a terminal signal. The side banner can
    precede the HUD update, so simultaneous accepted reads use the larger score.
    Missing templates/crops abstain, including unsupported three-crown glyphs.
    """
    def __init__(self, artifact=None):
        if artifact is None: artifact = Path(__file__).with_name('public_score_templates.json')
        self.data = json.loads(Path(artifact).read_text()) if isinstance(artifact,(str,Path)) else artifact
        if self.data['schema'] != 'clasher.public-score-templates.v1':
            raise ValueError('Unsupported public score artifact')

    def read(self, image, episode, timestamp_ms):
        import numpy as np
        if image.shape != (1140,540,3) or image.dtype != np.uint8:
            raise ValueError('Expected public 540x1140 uint8 BGR pixels')
        if not math.isfinite(timestamp_ms) or timestamp_ms < 0:
            raise ValueError('Invalid public crown time')
        counts, confidences = [], []
        for side in self.data['crowns']:
            reads = []
            for region in side:
                feature = color_feature(image,region['box'],tuple(region['size']))
                hit = read_templates(feature,region['templates'],region['distance'],region['margin'])
                if hit: reads.append((int(hit[0]),hit[1]))
            counts.append(max((n for n,c in reads),default=None))
            if reads: confidences.append(min(c for n,c in reads))
        return CrownObservation(episode,round(timestamp_ms),tuple(counts),min(confidences)) if confidences else None
