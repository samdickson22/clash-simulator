"""Positive public end-screen text; overlays/absence alone never end a match."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
from .crown_counter import read_templates


@dataclass(frozen=True)
class ResultScreenObservation:
    episode_id: str
    timestamp_ms: int
    outcome: str | None  # own win/loss/draw; None when outcome is unreadable
    crowns: tuple[int | None, int | None]
    confidence: float

    def __post_init__(self):
        from .public_root import PublicMatchResult
        PublicMatchResult(self.episode_id,self.timestamp_ms,self.crowns,self.confidence,self.outcome)

    def as_match_result(self):
        from .public_root import PublicMatchResult
        return PublicMatchResult(self.episode_id,self.timestamp_ms,self.crowns,self.confidence,self.outcome)


def text_feature(image, box, size):
    import cv2
    import numpy as np
    x1,y1,x2,y2 = box
    crop = image[y1:y2,x1:x2].astype(np.int16)
    # White glyph interiors are insensitive to arena/background colors.
    mask = ((crop.min(2)>200)&(crop.max(2)-crop.min(2)<45)).astype(np.float32)
    return cv2.resize(mask,size,interpolation=cv2.INTER_AREA).ravel()


class ResultScreenDetector:
    def __init__(self, artifact=None):
        if artifact is None: artifact = Path(__file__).with_name('public_score_templates.json')
        self.data = json.loads(Path(artifact).read_text()) if isinstance(artifact,(str,Path)) else artifact
        if self.data['schema'] != 'clasher.public-score-templates.v1':
            raise ValueError('Unsupported public result artifact')
        self.episode, self.last_time = None, None
        self.last_counts = [None,None]
        self.last_count_times = [None,None]
        self.streak = 0
        self.last_label = None
        self.ended = None

    def step(self, image, episode, timestamp_ms, crowns=None):
        import numpy as np
        if image.shape != (1140,540,3) or image.dtype != np.uint8:
            raise ValueError('Expected public 540x1140 uint8 BGR pixels')
        if not math.isfinite(timestamp_ms) or timestamp_ms < 0:
            raise ValueError('Invalid public result time')
        now = round(timestamp_ms)
        if episode != self.episode:
            self.episode, self.last_time = episode, None
            self.last_counts,self.last_count_times = [None,None],[None,None]
            self.streak,self.last_label,self.ended = 0,None,None
        if self.last_time is not None and now <= self.last_time:
            raise ValueError('Result detector requires increasing timestamps')
        if crowns is not None and (crowns.episode_id != episode or crowns.timestamp_ms != now):
            raise ValueError('Noncausal crown observation')
        if crowns is not None:
            for side,count in enumerate(crowns.crowns):
                if count is not None and (self.last_counts[side] is None or count >= self.last_counts[side]):
                    self.last_counts[side],self.last_count_times[side] = count,now
        if self.ended is not None:
            self.last_time = now
            return self.ended
        p = self.data['result']
        hit = read_templates(text_feature(image,p['box'],tuple(p['size'])),p['templates'],p['distance'],p['margin'])
        gap = self.last_time is not None and now-self.last_time > p['gap_ms']
        self.streak = self.streak+1 if hit and hit[0] == self.last_label and not gap else (1 if hit else 0)
        self.last_label,self.last_time = hit[0] if hit else None,now
        if self.streak < p['confirmation_frames']: return None
        label,confidence = hit
        counts = tuple(c if t is not None and now-t <= p['score_max_age_ms'] else None for c,t in zip(self.last_counts,self.last_count_times))
        outcome = label if label in ('win','loss','draw') else None
        # Scores can still be animating when Match Over appears. Require an
        # explicit outcome template; equal counts also permit HP tiebreaks.
        self.ended = ResultScreenObservation(episode,now,outcome,counts,confidence)
        return self.ended
