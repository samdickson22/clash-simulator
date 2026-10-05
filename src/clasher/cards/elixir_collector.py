"""Elixir Collector production (decoded-logic characters/elixircollector.toml).

BUILDING.ElixirCollector: ManaCollectAmount 1 every ManaGenerateTimeMs 13000 over
LifeTime 93000 after its 1000 ms deploy, plus ManaOnDeath 1 when it is destroyed
or expires. Production uses the spawn-speed axis (Freeze/Vines pause it); the
owner's balance is capped at the usual 10 elixir.
"""

from dataclasses import dataclass, field

from ..mechanics.mechanic_base import BaseMechanic


@dataclass
class ElixirProduction(BaseMechanic):
    amount: float = 1.0
    interval_ms: float = 13000.0
    on_death_amount: float = 1.0
    _elapsed_ms: float = field(default=0.0, init=False, repr=False)
    _produced: int = field(default=0, init=False, repr=False)

    def on_attach(self, entity) -> None:
        raw = getattr(getattr(entity, "card_stats", None), "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData", {}) or {}
        self.amount = float(character.get("manaCollectAmount", self.amount) or 0)
        self.interval_ms = float(character.get("manaGenerateTimeMs", self.interval_ms) or self.interval_ms)
        self.on_death_amount = float(character.get("manaOnDeath", self.on_death_amount) or 0)

    def on_object_tick(self, entity, dt_ms: int) -> None:
        if not entity.is_alive or getattr(entity, "deploy_delay_remaining", 0.0) > 1e-9:
            return
        self._elapsed_ms += float(dt_ms) * float(entity.get_spawn_rate_multiplier())
        while self._elapsed_ms + 1e-6 >= self.interval_ms:
            self._elapsed_ms -= self.interval_ms
            self._produced += 1
            self._give(entity, self.amount)

    def on_death(self, entity) -> None:
        self._give(entity, self.on_death_amount)

    @staticmethod
    def _give(entity, amount: float) -> None:
        battle_state = getattr(entity, "battle_state", None)
        if battle_state is None or amount <= 0 or battle_state.game_over:
            return
        player = battle_state.players[entity.player_id]
        player.elixir = min(player.max_elixir, player.elixir + amount)
