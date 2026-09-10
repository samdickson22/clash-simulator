"""Diagnostic episode lifetime manager for audited scalar appearance receipts.

Call synchronize_sources before every scalar frame. A source born and emitting
within that same frame is not guaranteed to be registered by this boundary-only
manager. Unknown visible effects must still fail in the projection layer; this
manager never hides them. Fixed extra IDs below are a diagnostic proposal, not
an accepted observation or training authority.
"""

from __future__ import annotations

from contextlib import ExitStack

from clasher.entities import Building, Troop
from scripts.hog26_scalar_chain_receipts import (
    ScalarChainReceiptRecorder,
    ScalarChainSourceDescriptor,
)
from scripts.hog26_scalar_death_effect_receipts import (
    DeathAppearanceRule,
    ScalarDeathEffectRecorder,
)
from scripts.hog26_scalar_line_projectile_receipts import (
    ScalarLineProjectileDescriptor,
    ScalarLineProjectileReceiptRecorder,
)
from scripts.hog26_scalar_projectile_receipts import (
    _COMMON_ROOTS,
    _EXTRA_SPAWN_ROUTES,
    ScalarOrdinaryProjectileDescriptor,
    ScalarProjectileReceiptRecorder,
)
from scripts.hog26_scalar_special_projectile_receipts import (
    ScalarSpecialProjectileDescriptor,
    ScalarSpecialProjectileReceiptRecorder,
)
from scripts.hog26_scalar_spell_receipts import ScalarSpellReceiptRecorder
from scripts.hog26_scalar_tower_receipts import ScalarTowerReceiptSetup


class ScalarReceiptSession:
    """Keep source, child-projectile and container hooks alive until episode end."""

    def __init__(self, battle, card_names, loader, vocabulary, *, visible_to):
        if not callable(visible_to):
            raise TypeError("receipt session requires explicit current visibility")
        names = tuple(dict.fromkeys(card_names))
        self.battle, self.loader, self.vocabulary = battle, loader, vocabulary
        self.card_names, self.visible_to = names, visible_to
        self.towers = ScalarTowerReceiptSetup.compile(
            battle,
            tuple(battle.entities.values()),
            loader,
            vocabulary,
            source_visible_to=visible_to,
        )
        self.token_names = (
            *self.towers.token_names,
            "public_effect:chain_bolt",
            "building_body:SkeletonContainerNew",
        )
        self.extra_public_effect_tokens = self.token_names[494:]
        self.extra_public_effect_ids = (494, 495, 496, 497)
        self.chain_category_token = 496
        self._candidates = {}
        self._death_cards = {}
        spells = []
        for name in names:
            stats = loader.get_card(name)
            if stats is None:
                raise ValueError(f"unknown supplied card: {name}")
            if stats.card_type == "Spell":
                spells.append(name)
            if name in _COMMON_ROOTS:
                self._add(
                    "ordinary",
                    ScalarOrdinaryProjectileDescriptor.compile(
                        name, loader, vocabulary
                    ),
                )
                if name not in {"Cannon", "BombTower", "Xbow"}:
                    self._add(
                        "ordinary",
                        ScalarOrdinaryProjectileDescriptor.compile_spawn_body(
                            name, ("summonCharacterData",), loader, vocabulary
                        ),
                    )
            if name in {"Bowler", "MagicArcher", "Wallbreakers"}:
                self._add(
                    "line",
                    ScalarLineProjectileDescriptor.compile(name, loader, vocabulary),
                )
            if name in {"ElectroDragon", "ElectroSpirit"}:
                self._add(
                    "chain",
                    ScalarChainSourceDescriptor.compile(name, loader, vocabulary),
                )
            if name in {"Princess", "Firecracker"}:
                self._add(
                    "special",
                    ScalarSpecialProjectileDescriptor.compile(name, loader, vocabulary),
                )
            if name in {
                "Balloon",
                "BombTower",
                "SkeletonBarrel",
                "IceGolem",
                "Lumberjack",
            }:
                self._death_cards.setdefault(stats.name, []).append(name)
        for parent, path in _EXTRA_SPAWN_ROUTES:
            if parent in names:
                self._add(
                    "ordinary",
                    ScalarOrdinaryProjectileDescriptor.compile_spawn_body(
                        parent, path, loader, vocabulary
                    ),
                )
        self.spells = ScalarSpellReceiptRecorder(battle, spells, loader, vocabulary)
        self.special = ScalarSpecialProjectileReceiptRecorder(battle)
        self._stack = ExitStack()
        self._active = False
        self._entered = False
        self._seen_sources = {}  # Strong references prevent Python-ID reuse.
        self._ordinary_recorders = []
        self._line_recorders = []
        self._chain_recorders = []
        self._death_recorders = []
        self.tower_recorder = None

    def _add(self, family, descriptor):
        self._candidates.setdefault(descriptor.source_card, []).append(
            (family, descriptor)
        )

    def __enter__(self):
        if self._entered:
            raise RuntimeError("receipt session cannot be entered twice")
        self._entered = True
        try:
            self.tower_recorder = self._stack.enter_context(self.towers.recorder())
            self._stack.enter_context(self.spells)
            self._stack.enter_context(self.special)
            self._active = True
            self.synchronize_sources()
        except BaseException:
            self._active = False
            self._stack.close()
            raise
        return self

    def synchronize_sources(self):
        """Bind newly observed source objects; a name only selects candidates."""
        if not self._active:
            raise RuntimeError("source synchronization requires an active session")
        for source in tuple(self.battle.entities.values()):
            if not isinstance(source, (Troop, Building)) or not source.is_alive:
                continue
            key = id(source)
            if key in self._seen_sources:
                continue
            name = getattr(source.card_stats, "name", "")
            candidates = self._candidates.get(name, ())
            matched = []
            for family, descriptor in candidates:
                try:
                    descriptor.validate_source(source)
                except ValueError:
                    continue
                matched.append((family, descriptor))
            if candidates and not matched:
                raise ValueError(f"source {name} matches no compiled receipt payload")
            if len({(family, descriptor.token) for family, descriptor in matched}) > 1:
                raise ValueError("source has ambiguous receipt appearance authority")
            if matched:
                family, descriptor = matched[0]
                if family == "special":
                    self.special.bind_source(source, descriptor)
                else:
                    recorder_type, destination = {
                        "ordinary": (
                            ScalarProjectileReceiptRecorder,
                            self._ordinary_recorders,
                        ),
                        "line": (
                            ScalarLineProjectileReceiptRecorder,
                            self._line_recorders,
                        ),
                        "chain": (ScalarChainReceiptRecorder, self._chain_recorders),
                    }[family]
                    recorder = self._stack.enter_context(
                        recorder_type(self.battle, [(source, descriptor)])
                    )
                    destination.append(recorder)
            for card in self._death_cards.get(name, ()):
                rule = DeathAppearanceRule.compile(
                    card,
                    source,
                    self.loader,
                    self.vocabulary,
                    extra_tokens={"building_body:SkeletonContainerNew": 497},
                )
                recorder = self._stack.enter_context(
                    ScalarDeathEffectRecorder(
                        self.battle,
                        [(source, rule)],
                        witnessed_visible_to=self.visible_to,
                    )
                )
                self._death_recorders.append(recorder)
            self._seen_sources[key] = source

    @property
    def ordinary_appearances(self):
        return tuple(a for r in self._ordinary_recorders for a in r.appearances)

    @property
    def line_appearances(self):
        return tuple(a for r in self._line_recorders for a in r.appearances)

    @property
    def special_appearances(self):
        return self.special.appearances

    @property
    def tower_appearances(self):
        return () if self.tower_recorder is None else self.tower_recorder.appearances

    @property
    def spell_appearances(self):
        return self.spells.appearances

    @property
    def chain_appearances(self):
        return tuple(
            a
            for r in self._chain_recorders
            for a in r.chain_appearances(
                category_name="public_effect:chain_bolt",
                category_token=self.chain_category_token,
                visible_to=self.visible_to,
            )
        )

    @property
    def appearances(self):
        parents = tuple(a for r in self._chain_recorders for a in r.parent_appearances)
        return (
            self.ordinary_appearances
            + self.line_appearances
            + self.special_appearances
            + self.tower_appearances
            + self.spell_appearances
            + parents
            + self.chain_appearances
        )

    @property
    def death_receipts(self):
        return tuple(receipt for r in self._death_recorders for receipt in r.receipts)

    @property
    def receipts(self):
        """Death-adapter protocol alias; unrelated receipts remain in their owners."""
        return self.death_receipts

    @property
    def registered_internal_containers(self):
        return tuple(
            entity
            for r in self._death_recorders
            for entity in r.registered_internal_containers
        )

    def __exit__(self, exc_type, exc_value, traceback):
        self._active = False
        return self._stack.__exit__(exc_type, exc_value, traceback)
