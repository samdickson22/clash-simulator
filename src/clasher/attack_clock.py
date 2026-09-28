"""Integer load and hit clocks for ordinary native weapons.

BattleState uses this model through the ordinary combat adapter. Special
load-first-hit/overloaded weapons and custom attack handlers retain their
existing adapters until their transitions have independent coverage.
"""

from dataclasses import dataclass


@dataclass
class OrdinaryAttackClock:
    hit_interval_ms: int
    load_time_ms: int
    finish_time_ms: int = 250
    hit_timeline_ms: int = 0
    load_remaining_ms: int = 0
    finish_elapsed_ms: int = 0

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in vars(self).values()):
            raise TypeError("native clock state requires integer milliseconds")
        if not 0 <= self.load_time_ms <= self.hit_interval_ms or self.hit_interval_ms <= 0:
            raise ValueError("ordinary weapons require 0 <= load <= positive hit interval")
        if min(self.finish_time_ms, self.hit_timeline_ms, self.load_remaining_ms, self.finish_elapsed_ms) < 0:
            raise ValueError("clock work cannot be negative")
        if self.load_remaining_ms > self.load_time_ms:
            raise ValueError("pending load exceeds the serialized load time")

    def advance(
        self,
        elapsed_ms: int,
        hit_work_ms: int,
        *,
        engaged: bool,
        frozen: bool = False,
        load_work_ms: int | None = None,
    ) -> int:
        """Consume one component frame and return the number of due hits.

        Call target_removed after this frame's work when object cleanup removes
        the current target. Both time inputs are integer work from the native
        component boundary; only hit_work_ms includes attack-speed modifiers.
        """
        if type(elapsed_ms) is not int or type(hit_work_ms) is not int:
            raise TypeError("native clock work requires integer milliseconds")
        if min(elapsed_ms, hit_work_ms) < 0:
            raise ValueError("time cannot run backwards")
        if frozen:
            return 0
        if load_work_ms is None:
            load_work_ms = elapsed_ms
        if type(load_work_ms) is not int or load_work_ms < 0:
            raise ValueError("load work requires nonnegative integer milliseconds")
        self.load_remaining_ms = max(0, self.load_remaining_ms - load_work_ms)
        if self.finish_elapsed_ms:
            self.finish_elapsed_ms += elapsed_ms
            if self.finish_elapsed_ms >= self.finish_time_ms:
                self.finish_elapsed_ms = 0
                self.hit_timeline_ms = 0
            return 0
        if not engaged:
            return 0
        previous_hits = self.hit_timeline_ms // self.hit_interval_ms
        if self.hit_timeline_ms == 0:
            self.hit_timeline_ms = max(0, self.load_time_ms - self.load_remaining_ms)
            self.load_remaining_ms = self.load_time_ms
        self.hit_timeline_ms += hit_work_ms
        hits = self.hit_timeline_ms // self.hit_interval_ms - previous_hits
        if hits:
            self.load_remaining_ms = self.load_time_ms
        return hits

    def target_removed(self) -> None:
        """Install ordinary finish work after an established hit loses its target."""
        if self.hit_timeline_ms and self.finish_time_ms:
            self.finish_elapsed_ms = 1
        else:
            self.hit_timeline_ms = 0

    def interrupt(self) -> None:
        """Apply the ordinary weapon's forced Zap interruption."""
        self.hit_timeline_ms = 0
        self.load_remaining_ms = self.load_time_ms
        self.finish_elapsed_ms = 0

    def stop_hit(self) -> None:
        """Movement clears hit progress without reloading the weapon."""
        self.hit_timeline_ms = 0
        self.finish_elapsed_ms = 0
