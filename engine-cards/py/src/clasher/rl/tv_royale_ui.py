from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class CardTemplate:
    name: str
    # UI sentinels such as ``empty`` have no game-data card cost. Real card
    # costs are resolved from the packaged authoritative card snapshot and
    # must never be inferred from an asset filename.
    cost: int | None
    color: np.ndarray
    gray: np.ndarray


@dataclass(frozen=True)
class ElixirTemplate:
    value: int
    image: np.ndarray


@dataclass(frozen=True)
class UIFrameState:
    frame: int
    hand: tuple[str | None, ...]
    elixir: float | None
    hand_confidence: tuple[float, ...] = ()
    elixir_confidence: float = 0.0
    next_card: str | None = None
    next_card_confidence: float = 0.0


@dataclass(frozen=True)
class UIPlayEvent:
    frame: int
    card: str
    confidence: float = 1.0
    evidence_frame: int | None = None


@dataclass(frozen=True)
class UINextCardLabel:
    """Offline-only label for the Next icon visible before one own play.

    ``evidence_frame`` is later than ``source_frame``. This label may supervise
    or validate a current-frame Next-icon detector, but it must never be placed
    directly in an inference observation.
    """

    source_frame: int
    card: str
    evidence_frame: int
    confidence: float


@dataclass(frozen=True)
class UINextCardObservation:
    """A current-frame template observation of the local public Next icon."""

    card: str
    confidence: float
    match_score: float
    runner_up_score: float


@dataclass
class _DeckCluster:
    compact: np.ndarray
    original: np.ndarray
    count: int
    first_frame: int
    grayscale: bool
    elixir: float | None


CARD_ORIGIN = (72, 834)
CARD_SIZE = (66, 81)
CARD_SPACE = 5
ELIXIR_ORIGIN = (19, 920)
ELIXIR_SIZE = (30, 25)
ELIXIR_BAR_ORIGIN = (48, 936)
ELIXIR_BAR_SIZE = (472, 3)
# Native 540x960 TV Royale replay geometry. This is the card-art portion of the
# local player's visibly public Next icon, excluding the level badge and label.
NEXT_CARD_ORIGIN = (17, 846)
NEXT_CARD_SIZE = (32, 40)


def _crop(image: np.ndarray, origin: tuple[int, int], size: tuple[int, int]) -> np.ndarray:
    x, y = origin
    width, height = size
    return image[y : y + height, x : x + width]


def _hand_crops(image: np.ndarray) -> list[np.ndarray]:
    return [
        _crop(
            image,
            (CARD_ORIGIN[0] + index * (CARD_SIZE[0] + CARD_SPACE), CARD_ORIGIN[1]),
            CARD_SIZE,
        )
        for index in range(4)
    ]


def _prep(image: np.ndarray, downsize_factor: int = 2) -> np.ndarray:
    shrunk = cv2.resize(
        image,
        (image.shape[1] // downsize_factor, image.shape[0] // downsize_factor),
        interpolation=cv2.INTER_AREA,
    )
    return cv2.GaussianBlur(shrunk, (3, 3), 0)


def _best_match(
    template: np.ndarray,
    candidates: dict[str, np.ndarray],
    *,
    shearing: tuple[int, int],
) -> tuple[float, str | None]:
    shear_y, shear_x = shearing
    y_slice = slice(shear_y, -shear_y if shear_y else None)
    x_slice = slice(shear_x, -shear_x if shear_x else None)
    query = template[y_slice, x_slice]
    best_score = 0.0
    best_name: str | None = None
    for name, image in candidates.items():
        result = cv2.matchTemplate(image, query, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(result)
        if score > best_score:
            best_score = float(score)
            best_name = name
    return best_score, best_name


def _is_grayscale(image: np.ndarray) -> bool:
    gray = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    return bool(np.median(np.abs(image.astype(np.int16) - gray.astype(np.int16))) < 5)


def _matching_pixel_fraction(
    image: np.ndarray,
    target: np.ndarray,
    tolerance: int,
    *,
    denominator: int | None = None,
) -> float:
    difference = np.abs(image.astype(np.int16) - target.astype(np.int16))
    count = int(np.count_nonzero(np.all(difference <= tolerance, axis=-1)))
    return count / float(denominator or image.shape[0] * image.shape[1])


def _is_selected(card: np.ndarray) -> bool:
    blurred = cv2.GaussianBlur(card, (5, 5), 0)
    return _matching_pixel_fraction(
        blurred[75:], np.asarray([133, 73, 47]), 11
    ) > 0.4


def _is_sliding(card: np.ndarray) -> bool:
    blurred = cv2.GaussianBlur(card, (5, 5), 0)
    target = np.asarray([133, 73, 47])
    return max(
        _matching_pixel_fraction(blurred[:, 5:7], target, 20),
        _matching_pixel_fraction(blurred[:, -7:-5], target, 20),
    ) > 0.35


def _not_ready_overlay(
    image: np.ndarray, current_elixir: float, cost: int, intensity: int = 127
) -> np.ndarray:
    height, width = image.shape[:2]
    center_x, center_y = width // 2, height // 2
    radius = int(np.hypot(center_x, center_y))
    readiness = 1.0 - current_elixir / cost
    steps = max(10, int(100 * readiness))
    angles = np.linspace(
        -math.pi / 2,
        -math.pi / 2 - 2 * math.pi * readiness,
        steps,
    )
    points = [(center_x, center_y)] + [
        (
            int(center_x + radius * math.cos(angle)),
            int(center_y + radius * math.sin(angle)),
        )
        for angle in angles
    ]
    overlay = np.zeros_like(image, dtype=np.uint8)
    cv2.fillPoly(
        overlay,
        [np.asarray(points, dtype=np.int32).reshape((-1, 1, 2))],
        intensity,
    )
    result = cv2.add(image, overlay)
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)


class TVRoyaleUIExtractor:
    """Fast, fixed-region TV Royale hand/elixir/event extraction.

    The geometry and matching rules are a cleaned, testable port of the
    MIT-licensed CS541 Clash Royale project's raw-replay extractor. The
    templates remain external inputs so every production manifest can pin the
    exact source revision and template hashes.
    """

    def __init__(
        self,
        template_root: Path,
        *,
        card_cost_resolver: Callable[[str], int | None],
    ) -> None:
        card_root = template_root / "cr_detection" / "cards"
        elixir_root = template_root / "cr_detection" / "elixir"
        if not card_root.is_dir() or not elixir_root.is_dir():
            raise FileNotFoundError(
                f"missing card/elixir templates beneath {template_root}"
            )
        self.cards: dict[str, CardTemplate] = {}
        for path in sorted(card_root.glob("*.png")):
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"could not decode card template {path}")
            stem_parts = path.stem.rsplit("-", 1)
            if len(stem_parts) != 2:
                continue
            name, _asset_metadata = stem_parts
            cost = None if name == "empty" else card_cost_resolver(name)
            if name != "empty" and cost is None:
                continue
            if cost is not None and (isinstance(cost, bool) or not 0 < cost <= 10):
                raise ValueError(
                    f"authoritative card cost for {name!r} must be in [1, 10]"
                )
            self.cards[name] = CardTemplate(
                name=name,
                cost=cost,
                color=image,
                gray=cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
            )
        self.elixirs: list[ElixirTemplate] = []
        for path in sorted(elixir_root.glob("*.png")):
            if not path.stem.isdigit():
                continue
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"could not decode elixir template {path}")
            self.elixirs.append(ElixirTemplate(int(path.stem), image))
        if not self.cards or not self.elixirs:
            raise ValueError("template library is empty")
        self._prepared_cards = {
            name: _prep(card.color) for name, card in self.cards.items()
        }

    def current_elixir(self, image: np.ndarray) -> float | None:
        value, _confidence = self.current_elixir_with_confidence(image)
        return value

    def current_elixir_with_confidence(
        self, image: np.ndarray
    ) -> tuple[float | None, float]:
        query = _crop(image, ELIXIR_ORIGIN, ELIXIR_SIZE)
        candidates = {str(item.value): item.image for item in self.elixirs}
        score, name = _best_match(query, candidates, shearing=(2, 2))
        if name is None or score <= 0.7:
            return None, 0.0
        bar = cv2.GaussianBlur(_crop(image, ELIXIR_BAR_ORIGIN, ELIXIR_BAR_SIZE), (3, 3), 0)
        fractional = _matching_pixel_fraction(
            bar,
            np.asarray([132, 71, 78]),
            11,
            denominator=135,
        )
        # Retain the raw visual match quality rather than promoting every
        # thresholded template match to exact confidence one.
        return float(int(name) + fractional), float(np.clip(score, 0.0, 1.0))

    def next_card_observation(
        self,
        image: np.ndarray,
        deck: dict[str, CardTemplate],
        *,
        minimum_score: float = 0.12,
        minimum_margin: float = 0.025,
    ) -> UINextCardObservation | None:
        """Decode only the current local Next icon, retaining ambiguity evidence."""

        if not deck:
            return None
        if not -1.0 <= minimum_score <= 1.0 or minimum_margin < 0.0:
            raise ValueError("next-card score and margin thresholds are invalid")
        query = _crop(image, NEXT_CARD_ORIGIN, NEXT_CARD_SIZE)
        if query.shape[:2] != (NEXT_CARD_SIZE[1], NEXT_CARD_SIZE[0]):
            return None
        scores: list[tuple[float, str]] = []
        for name, card in deck.items():
            candidate = cv2.resize(
                card.color,
                NEXT_CARD_SIZE,
                interpolation=cv2.INTER_AREA,
            )
            score = float(
                cv2.matchTemplate(candidate, query, cv2.TM_CCOEFF_NORMED)[0, 0]
            )
            scores.append((score, name))
        scores.sort(reverse=True)
        best_score, best_name = scores[0]
        runner_up = scores[1][0] if len(scores) > 1 else -1.0
        margin = best_score - runner_up
        if best_score < minimum_score or margin < minimum_margin:
            return None
        absolute_quality = float(
            np.clip((best_score - minimum_score) / max(1e-6, 1.0 - minimum_score), 0, 1)
        )
        margin_quality = float(
            np.clip((margin - minimum_margin) / 0.20, 0.0, 1.0)
        )
        return UINextCardObservation(
            card=best_name,
            confidence=float(math.sqrt(absolute_quality * margin_quality)),
            match_score=best_score,
            runner_up_score=runner_up,
        )

    def cards_in_hand(
        self,
        image: np.ndarray,
        deck: dict[str, CardTemplate],
        current_elixir: float | None,
    ) -> tuple[str | None, ...]:
        cards, _confidence = self.cards_in_hand_with_confidence(
            image,
            deck,
            current_elixir,
        )
        return cards

    def cards_in_hand_with_confidence(
        self,
        image: np.ndarray,
        deck: dict[str, CardTemplate],
        current_elixir: float | None,
    ) -> tuple[tuple[str | None, ...], tuple[float, ...]]:
        detected: list[str | None] = []
        confidence: list[float] = []
        for card_image in _hand_crops(image):
            gray = _is_grayscale(card_image)
            if _is_sliding(card_image):
                detected.append(None)
                confidence.append(0.0)
                continue
            if gray and current_elixir is not None:
                candidates = {
                    name: _prep(
                        _not_ready_overlay(card.gray, current_elixir, card.cost)
                        if card.cost is not None
                        else card.color
                    )
                    for name, card in deck.items()
                }
            else:
                candidates = {name: _prep(card.color) for name, card in deck.items()}
            score, name = _best_match(
                _prep(card_image), candidates, shearing=(9, 3)
            )
            if name is None:
                detected.append(None)
                confidence.append(0.0)
            elif gray and score > 0.55:
                detected.append(f"gray_{name}")
                confidence.append(float(np.clip(score, 0.0, 1.0)))
            elif not gray and score > 0.6:
                detected.append(name)
                confidence.append(float(np.clip(score, 0.0, 1.0)))
            else:
                detected.append(None)
                confidence.append(0.0)
        return tuple(detected), tuple(confidence)

    def discover_deck(self, images: Iterable[np.ndarray]) -> dict[str, CardTemplate]:
        clusters: dict[str, _DeckCluster] = {}
        for frame_index, image in enumerate(images):
            elixir: float | None = None
            for hand_crop in _hand_crops(image):
                if _is_selected(hand_crop) or _is_sliding(hand_crop):
                    continue
                grayscale = _is_grayscale(hand_crop)
                if grayscale and elixir is None:
                    elixir = self.current_elixir(image)
                compact = _prep(hand_crop, 4)
                if not clusters:
                    clusters[str(uuid.uuid4())] = _DeckCluster(
                        compact,
                        hand_crop.copy(),
                        1,
                        frame_index,
                        grayscale,
                        elixir,
                    )
                    continue
                score, key = _best_match(
                    compact,
                    {
                        name: value.compact
                        for name, value in clusters.items()
                        if value.grayscale == grayscale
                    },
                    shearing=(3, 3),
                )
                if key is not None and score > 0.96:
                    clusters[key].count += 1
                else:
                    clusters[str(uuid.uuid4())] = _DeckCluster(
                        compact,
                        hand_crop.copy(),
                        1,
                        frame_index,
                        grayscale,
                        elixir,
                    )
            if frame_index % 30 == 0 and frame_index > 15:
                clusters = {
                    key: value
                    for key, value in clusters.items()
                    if value.count > 5
                    or not (15 < frame_index - value.first_frame < 45)
                }
        persistent = {
            key: value for key, value in clusters.items() if value.count > 5
        }
        deck: dict[str, CardTemplate] = {}
        for value in persistent.values():
            candidates = self._prepared_cards
            if value.grayscale and value.elixir is not None:
                candidates = {
                    name: _prep(
                        _not_ready_overlay(card.gray, value.elixir, card.cost)
                        if card.cost is not None
                        else card.color
                    )
                    for name, card in self.cards.items()
                }
            score, name = _best_match(
                _prep(value.original),
                candidates,
                shearing=(9, 3),
            )
            if name is not None and score >= 0.80:
                deck[name] = self.cards[name]
        # Partial decks remain useful: the frame scanner emits a complete
        # state only when all four visible cards match this strict library.
        # Fewer than four templates can never produce such a state.
        if len(deck) < 4:
            raise ValueError(f"identified only {len(deck)} distinct deck cards")
        return deck

    def scan_states(
        self,
        images: Iterable[tuple[int, np.ndarray]],
        deck: dict[str, CardTemplate],
    ) -> tuple[list[UIFrameState], list[UIPlayEvent]]:
        old_hand: list[str | None] = [None, None, None, None]
        old_hand_confidence = [0.0, 0.0, 0.0, 0.0]
        previous_elixir = 0.0
        queued_elixir_losses = 0
        last_true_update_frame = 0
        states: list[UIFrameState] = []
        events: list[UIPlayEvent] = []
        for frame, image in images:
            elixir, elixir_confidence = self.current_elixir_with_confidence(image)
            if elixir is not None:
                if elixir - previous_elixir < -0.8:
                    queued_elixir_losses += 1
                previous_elixir = elixir
            hand, hand_confidence = self.cards_in_hand_with_confidence(
                image, deck, elixir
            )
            next_card = self.next_card_observation(image, deck)
            states.append(
                UIFrameState(
                    frame=frame,
                    hand=hand,
                    elixir=elixir,
                    hand_confidence=hand_confidence,
                    elixir_confidence=elixir_confidence,
                    next_card=(next_card.card if next_card is not None else None),
                    next_card_confidence=(
                        next_card.confidence if next_card is not None else 0.0
                    ),
                )
            )
            empties = [index for index, card in enumerate(hand) if card == "empty"]
            missing = [index for index, card in enumerate(hand) if card is None]
            new_plays = 0
            for empty_index in empties:
                if old_hand[empty_index] != "empty":
                    previous = old_hand[empty_index]
                    if previous is not None:
                        events.append(
                            UIPlayEvent(
                                last_true_update_frame,
                                previous,
                                confidence=float(old_hand_confidence[empty_index]),
                                evidence_frame=frame,
                            )
                        )
                        new_plays += 1
                    old_hand[empty_index] = "empty"
                    old_hand_confidence[empty_index] = 0.0
            for index, card in enumerate(hand):
                if missing or empties:
                    continue
                if old_hand[index] == card:
                    old_hand_confidence[index] = float(hand_confidence[index])
                    continue
                previous = old_hand[index]
                if (
                    queued_elixir_losses > 0
                    and previous is not None
                    and card is not None
                    and f"gray_{card}" != previous
                    and f"gray_{previous}" != card
                ):
                    events.append(
                        UIPlayEvent(
                            last_true_update_frame,
                            previous,
                            confidence=min(
                                float(old_hand_confidence[index]),
                                float(elixir_confidence),
                            ),
                            evidence_frame=frame,
                        )
                    )
                    new_plays += 1
                old_hand[index] = card
                old_hand_confidence[index] = float(hand_confidence[index])
            queued_elixir_losses = max(0, queued_elixir_losses - new_plays)
            if not missing and not empties:
                last_true_update_frame = frame
        return states, events


def infer_offline_next_card_labels(
    states: Sequence[UIFrameState],
    events: Sequence[UIPlayEvent],
    *,
    maximum_followup_frames: int = 45,
) -> list[UINextCardLabel]:
    """Use a later hand refill to label the earlier, visibly public Next icon.

    This deliberately consumes future frames and is therefore training/audit
    tooling only. Runtime inference must decode the current Next icon directly.
    """

    if maximum_followup_frames <= 0:
        raise ValueError("next-card label followup must be positive")
    ordered = sorted(states, key=lambda state: state.frame)
    labels: list[UINextCardLabel] = []
    for event in sorted(events, key=lambda item: item.frame):
        before = [state for state in ordered if state.frame <= event.frame]
        if not before:
            continue
        source = before[-1]
        normalized_event = event.card.removeprefix("gray_")
        played_slots = [
            index
            for index, card in enumerate(source.hand)
            if card is not None
            and card != "empty"
            and card.removeprefix("gray_") == normalized_event
        ]
        if len(played_slots) != 1:
            continue
        slot = played_slots[0]
        for later in ordered:
            if later.frame <= event.frame:
                continue
            if later.frame - event.frame > maximum_followup_frames:
                break
            if slot >= len(later.hand):
                continue
            replacement = later.hand[slot]
            if replacement is None or replacement == "empty":
                continue
            replacement = replacement.removeprefix("gray_")
            if replacement == normalized_event:
                continue
            later_confidence = (
                float(later.hand_confidence[slot])
                if slot < len(later.hand_confidence)
                else 0.0
            )
            confidence = min(float(event.confidence), later_confidence)
            labels.append(
                UINextCardLabel(
                    source_frame=event.frame,
                    card=replacement,
                    evidence_frame=later.frame,
                    confidence=float(np.clip(confidence, 0.0, 1.0)),
                )
            )
            break
    return labels


def choose_sparse_noop_frames(
    states: Sequence[UIFrameState],
    events: Sequence[UIPlayEvent],
    *,
    stride_frames: int = 20,
    exclusion_frames: int = 5,
    terminal_exclusion_frames: int = 50,
) -> list[int]:
    if (
        stride_frames <= 0
        or exclusion_frames < 0
        or terminal_exclusion_frames < 0
    ):
        raise ValueError("noop stride must be positive and exclusions non-negative")
    event_frames = [event.frame for event in events]
    final_eligible_frame = (
        states[-1].frame - terminal_exclusion_frames if states else -1
    )
    return [
        state.frame
        for state in states
        if state.frame % stride_frames == 0
        and state.frame <= final_eligible_frame
        and state.elixir is not None
        and all(card is not None for card in state.hand)
        and all(abs(state.frame - event_frame) > exclusion_frames for event_frame in event_frames)
    ]
