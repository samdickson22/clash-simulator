"""Deterministic scalar episode control, without rewards or automatic resets."""

import hashlib
import random
from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass

import numpy as np

from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace


@dataclass
class ScalarReferenceEpisode:
    battle: BattleState
    action_space: DiscreteTileActionSpace
    action_order_rng: random.Random
    learner_seat: int
    decision_interval_ticks: int

    @classmethod
    def create(
        cls,
        ordered_decks,
        *,
        seed,
        learner_seat,
        decision_interval_ticks=8,
        action_order_seed=None,
    ):
        """Opening order is supplied, never shuffled by episode construction.

        Battle randomness and learner-relative action-order randomness have
        separate declared streams. This is a new reference scenario contract,
        not an assertion of historical native seed equivalence. An explicit
        action_order_seed is used directly; None preserves the previous
        seed-derived default exactly.
        """
        if action_order_seed is not None:
            if type(action_order_seed) is not int:
                raise TypeError("action_order_seed must be an integer or None")
            if action_order_seed < 0:
                raise ValueError("action_order_seed must be nonnegative")
        if learner_seat not in (0, 1) or decision_interval_ticks < 1:
            raise ValueError("invalid learner seat or decision interval")
        if len(ordered_decks) != 2 or any(
            len(d) != 8 or len(set(d)) != 8 for d in ordered_decks
        ):
            raise ValueError("two explicit eight-card ordered decks are required")
        loader = CardDataLoader()
        definitions = loader.load_card_definitions()
        ordered_decks = [
            tuple(resolve_card_name(name, definitions) for name in deck)
            for deck in ordered_decks
        ]
        if any(
            len(set(deck)) != 8 or any(loader.get_card(name) is None for name in deck)
            for deck in ordered_decks
        ):
            raise ValueError("reference decks require eight distinct canonical cards")
        players = [
            PlayerState(
                player_id=seat,
                deck=list(deck),
                hand=list(deck[:4]),
                cycle_queue=deque(deck[4:]),
            )
            for seat, deck in enumerate(ordered_decks)
        ]
        battle = BattleState(
            players=players,
            rng=random.Random(seed),
            fast_path=False,
            card_loader=loader,
        )
        if action_order_seed is None:
            material = f"scalar-reference-action-order-v1:{seed}".encode()
            order_seed = int.from_bytes(hashlib.sha256(material).digest(), "big")
        else:
            order_seed = action_order_seed
        return cls(
            battle,
            DiscreteTileActionSpace(canonical_perspective=True),
            random.Random(order_seed),
            learner_seat,
            decision_interval_ticks,
        )

    def step(
        self,
        actions,
        public_masks,
        *,
        before_tick=None,
        after_tick=None,
        tick_context=None,
    ):
        """Apply public-mask-authorized requests, then real scalar frames.

        Success is diagnostic output only. No simulator legality mask is read,
        no reward is computed, and terminal episodes are never auto-reset.
        Optional receipt hooks must be separately verified as observational.
        """
        if self.battle.game_over:
            raise RuntimeError("reference episode is already terminal")
        actions = np.asarray(actions)
        masks = np.asarray(public_masks)
        if (
            actions.shape != (2,)
            or actions.dtype.kind not in "iu"
            or masks.shape != (2, self.action_space.num_actions)
            or masks.dtype != np.bool_
        ):
            raise ValueError("invalid public action boundary")
        if np.any(actions < 0) or np.any(actions >= masks.shape[1]):
            raise ValueError("action outside public action space")
        if not masks[np.arange(2), actions].all():
            raise ValueError("selected action is not allowed by supplied public mask")
        order = [self.learner_seat, 1 - self.learner_seat]
        self.action_order_rng.shuffle(order)
        success = [False, False]
        for seat in order:
            success[seat] = self.action_space.apply_action(
                self.battle, seat, int(actions[seat])
            )
        ticks = 0
        for _ in range(self.decision_interval_ticks):
            if self.battle.game_over:
                break
            with nullcontext() if tick_context is None else tick_context(self.battle):
                if before_tick is not None:
                    before_tick(self.battle)
                self.battle.step()
                ticks += 1
                if after_tick is not None:
                    after_tick(self.battle)
        return {
            "action_order": tuple(order),
            "action_success": tuple(success),
            "ticks": ticks,
            "done": self.battle.game_over,
        }
