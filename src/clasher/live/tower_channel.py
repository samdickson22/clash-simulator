"""Six public screen-anchor measurements, independent of detector identities.

The fitted artifact contains small numerical templates, never native state.
Unknown is a current-frame observation, not a death transition. Persistence
belongs to PublicTowerModel. Scores are template similarity, not probabilities.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path

SLOT_NAMES = ('opp_king', 'opp_left', 'opp_right', 'own_king', 'own_left', 'own_right')
ANCHORS = ((0, 9., 3.), (0, 3.5, 6.5), (0, 14.5, 6.5),
           (1, 9., 29.), (1, 3.5, 25.5), (1, 14.5, 25.5))
MATRIX = ((28.54545454545454, 0., 12.09090909090933),
          (0., 22.89473684210524, 237.18421052631592))
EVIDENCE = frozenset({'rubble_template', 'public_match_result'})


@dataclass(frozen=True)
class TowerObservation:
    slot: str
    state: str = 'unknown'
    hp_known: bool = False
    hp: int | None = None
    confidence: float = 0.
    last_observed_ms: int | None = None
    destruction_evidence: str | None = None
    hp_fraction: float | None = None
    king_active: bool | None = None
    match_ended: bool = False

    def __post_init__(self):
        if self.slot not in SLOT_NAMES or self.state not in ('alive', 'unknown', 'destroyed'):
            raise ValueError('Invalid public tower slot/state')
        if type(self.hp_known) is not bool or self.hp_known != (self.hp is not None):
            raise ValueError('HP-known must agree with integer HP')
        if self.hp is not None and (type(self.hp) is not int or self.hp < 0):
            raise ValueError('Tower HP must be a nonnegative integer or unknown')
        if not isinstance(self.confidence, (int, float)) or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError('Invalid tower confidence')
        if self.last_observed_ms is not None and (type(self.last_observed_ms) is not int or self.last_observed_ms < 0):
            raise ValueError('Invalid tower observation time')
        if self.hp_fraction is not None and (not math.isfinite(self.hp_fraction) or not 0 <= self.hp_fraction <= 1):
            raise ValueError('Invalid public HP-bar fraction')
        if type(self.match_ended) is not bool or (self.match_ended and (not self.slot.endswith('king') or self.state == 'alive' or self.confidence <= 0 or self.last_observed_ms is None)):
            raise ValueError('Match end requires a positive public King/result observation')
        if self.king_active is not None and (type(self.king_active) is not bool or not self.slot.endswith('king') or self.state != 'alive'):
            raise ValueError('Activation is a living King observation only')
        if self.state == 'destroyed':
            if (self.slot.endswith('king')) != (self.destruction_evidence == 'public_match_result'):
                raise ValueError('King destruction requires a public three-crown result; princess destruction requires rubble')
            if self.destruction_evidence not in EVIDENCE or self.confidence <= 0 or self.last_observed_ms is None:
                raise ValueError('Destroyed requires positive visual evidence')
            if self.hp not in (None, 0) or self.hp_fraction not in (None, 0.):
                raise ValueError('Destroyed contradicts positive HP')
        elif self.destruction_evidence is not None:
            raise ValueError('Only destroyed carries destruction evidence')
        if self.state == 'unknown' and (self.hp_known or self.hp_fraction is not None):
            raise ValueError('Unknown cannot carry a current HP reading')
        if self.state == 'alive' and (self.hp == 0 or self.hp_fraction == 0 or self.last_observed_ms is None or self.confidence <= 0):
            raise ValueError('Alive requires a positive current observation')


def parse_observations(rows, timestamp_ms):
    if not isinstance(rows, (list, tuple)):
        raise ValueError('Tower channel must be a sequence')
    result = tuple(TowerObservation(**r) for r in rows)
    if result and (len(result) != 6 or {r.slot for r in result} != set(SLOT_NAMES)):
        raise ValueError('Tower channel must contain each of the six slots once')
    if any(r.last_observed_ms is not None and r.last_observed_ms > timestamp_ms for r in result):
        raise ValueError('Future tower observation')
    return result


def sprite_feature(crop):
    import cv2
    import numpy as np
    # Exclude HP and nearby troops; preserve collapsed stones at ground level.
    return cv2.resize(crop[30:140, 12:84], (12, 18), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()/255


def glyphs(panel, slot):
    """Connected foreground glyphs in the fixed public HP-number line."""
    import cv2
    import numpy as np
    # Opponent King numbers lie outside the sanitized public arena.
    if slot == 0:
        return []
    line = panel[38:57, 25:104] if slot == 3 else (panel[18:38, 25:104] if slot < 3 else panel[16:38, 25:104])
    v = line.astype(np.int16)
    threshold, spread = (190, 60) if slot < 3 else (150, 100)
    mask = ((v.min(2) > threshold) & (v.max(2)-v.min(2) < spread)).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = sorted((x,y,w,h) for x,y,w,h,area in stats[1:]
                   if 7 <= h <= 17 and 3 <= w <= 15 and area >= 12)
    if not 1 <= len(boxes) <= 4:
        return []
    # HP uses a single baseline and a tightly spaced left-aligned number.
    # Reject floating troop levels and truncated fragments of a longer number.
    first_range = {4:(2,12),3:(8,22),2:(15,32),1:(22,42)}[len(boxes)] if slot < 3 else (8,18)
    if not first_range[0] <= boxes[0][0] <= first_range[1] or any(b[0]-(a[0]+a[2]) > 3 for a,b in zip(boxes,boxes[1:])):
        return []
    if max(y+h for x,y,w,h in boxes)-min(y+h for x,y,w,h in boxes) > 2:
        return []
    for x,y,w,h,area in stats[1:]:
        if area >= 4 and 8 <= x <= 66 and h >= 4 and (x,y,w,h) not in boxes:
            return []
    return [cv2.resize(mask[y:y+h,x:x+w], (10,14), interpolation=cv2.INTER_NEAREST).ravel().astype(np.float32)
            for x,y,w,h in boxes]


def bar_fraction(panel, slot):
    """Read the visible fixed-width bar, never turn an empty bar into death."""
    import numpy as np
    if slot%3 == 0:
        return None
    row = panel[36 if slot < 3 else 17, 33:98].astype(np.int16)
    b,g,r = row.T
    fill = ((r > 170) & (b > 70) & (g < 140)) if slot < 3 else ((b > 160) & (g > 90) & (r < 100))
    if not fill[:2].all() or fill.sum() < 3:
        return None
    end = int(np.flatnonzero(fill)[-1])+1
    if fill[:end].mean() < .95:
        return None
    # A dark unfilled segment or a fully colored row is a positive bar cue.
    if end < len(row) and not (row[end:].mean(1) < 110).all():
        return None
    return end/len(row)


def activation_feature(sprite):
    import cv2
    import numpy as np
    return cv2.resize(sprite[25:105, 24:72], (12,16), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()/255


def number_family(slot):
    return 'opp_princess' if slot in (1,2) else ('own_king' if slot == 3 else 'own_princess')


class TowerChannel:
    def __init__(self, artifact=None, matrix=MATRIX):
        import numpy as np
        if artifact is None:
            artifact = Path(__file__).with_name('tower_channel_templates.json')
        data = json.loads(Path(artifact).read_text()) if isinstance(artifact, (str, Path)) else artifact
        if data['schema'] != 'clasher.public-tower-templates.v1':
            raise ValueError('Unsupported tower template artifact')
        self.parameters = data['parameters']
        self.templates = [{state: np.asarray(values, np.float32).reshape(-1,648)
                           for state,values in slot.items()} for slot in data['sprites']]
        self.digits = [(int(d), np.asarray(t, np.float32)) for d,templates in data['digits'].items() for t in templates]
        self.digit_labels = np.array([d for d,_ in self.digits],np.intp)
        self.digit_templates = np.array([t for _,t in self.digits],np.float32)
        self.number_readers = {}
        for family, table in data.get('digits_by_family', {}).items():
            pairs = [(int(d),t) for d,templates in table.items() for t in templates]
            self.number_readers[family] = (np.array([d for d,t in pairs],np.intp), np.array([t for d,t in pairs],np.float32))
        self.number_enabled = data.get('number_enabled', {})
        self.activation_templates = {int(slot):{state:np.asarray(t,np.float32).reshape(-1,576) for state,t in table.items()} for slot,table in data.get('activation', {}).items()}
        self.matrix = np.asarray(matrix, np.float64)
        if self.matrix.shape != (2,3) or not np.isfinite(self.matrix).all():
            raise ValueError('Invalid capture geometry')
        self.centers = [tuple(np.rint(self.matrix @ [x,y,1]).astype(int)) for _,x,y in ANCHORS]
        if any(not (55 <= x <= 485 and 295 <= y <= 925) for x,y in self.centers):
            raise ValueError('Tower crops outside calibrated public canvas')
        self.episode = None
        self.last_time = None

    def read_crop(self, sprite, panel, slot):
        import numpy as np
        f = sprite_feature(sprite)
        distances = {s: float(np.sqrt(np.mean((t-f)**2, axis=1)).min()) if len(t) else 1.
                     for s,t in self.templates[slot].items()}
        alive, rubble = distances.get('alive',1.), distances.get('destroyed',1.)
        p = self.parameters
        if slot%3 != 0 and rubble <= p['rubble_distance'] and alive-rubble >= p['rubble_margin']:
            return 'destroyed', 1-rubble, None, None
        if alive > p['alive_distance'] or rubble < alive:
            return 'unknown', 0., None, None
        hp = None
        family = number_family(slot)
        labels, templates = self.number_readers.get(family,(self.digit_labels,self.digit_templates))
        gs = glyphs(panel, slot) if self.number_enabled.get(family,True) else []
        if gs and len(templates):
            number = ''
            for g in gs:
                distances = np.mean((templates-g)**2,axis=1)
                errors = np.full(10,np.inf)
                np.minimum.at(errors,labels,distances)
                ordered = np.argsort(errors)
                limit = p.get(family+'_digit_distance', p['digit_distance'])
                margin = p.get(family+'_digit_margin', p['digit_margin'])
                if errors[ordered[0]] > limit or errors[ordered[1]]-errors[ordered[0]] < margin:
                    number = ''
                    break
                number += str(ordered[0])
            if number and number[0] != '0' and int(number) <= (4824 if slot%3 == 0 else 3052):
                hp = int(number)
        return 'alive', 1-alive, hp, bar_fraction(panel,slot)

    def read_activation(self, sprite, slot):
        import numpy as np
        table = self.activation_templates.get(slot)
        if not table:
            return None
        f = activation_feature(sprite)
        distances = {state:float(np.sqrt(np.mean((t-f)**2,axis=1)).min()) for state,t in table.items() if len(t)}
        if len(distances) != 2:
            return None
        ordered = sorted(distances,key=distances.get)
        if distances[ordered[0]] > self.parameters.get('activation_distance',.08) or distances[ordered[1]]-distances[ordered[0]] < self.parameters.get('activation_margin',.02):
            return None
        return ordered[0] == 'active'

    def step(self, image, episode, timestamp_ms):
        import numpy as np
        if image.shape != (1140,540,3) or image.dtype != np.uint8:
            raise ValueError('Expected sanitized 540x1140 uint8 BGR pixels')
        if not math.isfinite(timestamp_ms) or timestamp_ms < 0:
            raise ValueError('Invalid public timestamp')
        now = round(timestamp_ms)
        if episode != self.episode:
            self.episode, self.last_time = episode, None
            self.observed = [None]*6
            self.rubble_streak = [0]*6
        if self.last_time is not None and now <= self.last_time:
            raise ValueError('Tower channel requires increasing timestamps')
        if self.last_time is not None and now-self.last_time > self.parameters['confirmation_gap_ms']:
            self.rubble_streak = [0]*6
        self.last_time = now
        result = []
        for s,(x,y) in enumerate(self.centers):
            sprite = image[y-95:y+55,x-48:x+48]
            offset = (-130 if s%3 == 0 else -110) if s < 3 else (20 if s%3 == 0 else -25)
            panel = image[y+offset:y+offset+80,x-55:x+55]
            state, confidence, hp, fraction = self.read_crop(sprite,panel,s)
            self.rubble_streak[s] = self.rubble_streak[s]+1 if state == 'destroyed' else 0
            if state == 'destroyed' and self.rubble_streak[s] < self.parameters['confirmation_frames']:
                state, confidence = 'unknown', 0.
            if state != 'unknown':
                self.observed[s] = now
            result.append(TowerObservation(SLOT_NAMES[s], state, hp is not None, hp,
                         confidence, self.observed[s], 'rubble_template' if state == 'destroyed' else None, fraction,
                         self.read_activation(sprite,s) if state == 'alive' and s%3 == 0 else None))
        return tuple(result)
