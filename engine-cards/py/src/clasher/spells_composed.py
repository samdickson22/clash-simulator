from dataclasses import dataclass
from typing import List

from .card_types import Effect
from .effects import EffectContext


@dataclass
class ComposedSpell:
    """Spell composed of multiple effects"""
    name: str
    mana_cost: int
    effects: List[Effect]

    def cast(self, battle_state, player_id: int, target_position) -> bool:
        """Cast the spell by applying all effects"""
        context = EffectContext(
            battle_state=battle_state,
            caster_id=player_id,
            target_position=target_position
        )

        for effect in self.effects:
            effect.apply(context)

        return len(context.affected_entities) > 0 or len(self.effects) > 0