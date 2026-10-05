//! Champion ownership and ability timers. Python remains the behavior oracle.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Ability {
    cost: f64,
    cooldown: i64,
    duration: i64,
    last_use: i64,
    active: bool,
    start: i64,
    frozen_allowed: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind")]
pub(super) enum Effect {
    Skeleton {
        threshold: i64,
        offsets: Vec<(f64, f64)>,
    },
    Goblin {
        monster: Option<i32>,
        anchor: Option<(f64, f64)>,
        next_hit: Option<i64>,
        cast_until: i64,
        damage: f64,
        crown_damage: f64,
    },
    Mighty {
        pending: Option<i64>,
        cast_until: i64,
    },
    Queen {
        attack: f64,
        movement: f64,
        cast: i64,
        delay: i64,
        original_move: Option<f64>,
        pending: Option<i64>,
        cast_until: Option<i64>,
    },
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Champion {
    pub key: String,
    ability: Ability,
    effect: Effect,
}

impl Entity {
    pub(super) fn attack_work(&self) -> i64 {
        let buff = (self.attack_mode.max(self.haste_percent(2) as f64 / 100.0) * 100.0).round_ties_even() as i64;
        (50 * buff / 100) * self.slow_percent(true) / 100
    }
}

impl BattleState {
    pub(super) fn bind_champion(&self, e: &mut Entity) {
        let Some(c) = &mut e.champion else {
            return;
        };
        if let Effect::Goblin {
            monster, anchor, ..
        } = &mut c.effect
        {
            let bound = self
                .entities
                .iter()
                .filter(|b| {
                    b.alive
                        && b.owner == e.owner
                        && b.is_clone == e.is_clone
                        && b.stats.name == "Goblinstein"
                })
                .max_by_key(|b| b.id);
            *monster = bound.map(|b| b.id);
            *anchor = bound.map(|b| (b.x, b.y));
        }
    }

    fn refresh_champion_owner(&mut self, owner: i32, key: &str) -> Option<usize> {
        let selected = self
            .entities
            .iter()
            .enumerate()
            .filter(|(_, e)| {
                e.alive
                    && e.class == "Troop"
                    && !e.is_clone
                    && e.owner == owner
                    && e.champion.as_ref().is_some_and(|c| c.key == key)
            })
            .max_by_key(|(_, e)| e.id)
            .map(|(i, _)| i);
        let prior = self
            .champion_owners
            .iter()
            .position(|v| v.0 == owner && v.1 == key);
        if let Some(i) = selected {
            let id = self.entities[i].id;
            if prior.is_none_or(|k| self.champion_owners[k].2 != id) {
                self.entities[i].champion.as_mut().unwrap().ability.last_use = -1_000_000_000_000;
                if let Some(k) = prior {
                    self.champion_owners[k].2 = id;
                } else {
                    self.champion_owners.push((owner, key.to_owned(), id));
                }
            }
        } else if let Some(k) = prior {
            self.champion_owners.remove(k);
        }
        selected
    }
    pub(super) fn refresh_dead_champions(&mut self) {
        let groups: Vec<_> = self
            .entities
            .iter()
            .filter(|e| !e.alive && e.class == "Troop" && !e.is_clone)
            .filter_map(|e| e.champion.as_ref().map(|c| (e.owner, c.key.clone())))
            .collect();
        for (owner, key) in groups {
            self.refresh_champion_owner(owner, &key);
        }
    }
    fn ability_owner(&mut self, owner: usize) -> Option<usize> {
        let mut keys: Vec<_> = self
            .entities
            .iter()
            .filter(|e| e.alive && e.class == "Troop" && !e.is_clone && e.owner == owner as i32)
            .filter_map(|e| e.champion.as_ref().map(|c| (e.id, c.key.clone())))
            .collect();
        keys.sort_by(|a, b| b.0.cmp(&a.0));
        let mut seen = Vec::new();
        let mut best = None;
        for (_, key) in keys {
            if seen.contains(&key) {
                continue;
            }
            seen.push(key.clone());
            if let Some(i) = self.refresh_champion_owner(owner as i32, &key) {
                if best.is_none_or(|j: usize| self.entities[i].id > self.entities[j].id) {
                    best = Some(i);
                }
            }
        }
        best
    }
    pub(super) fn champion_can_activate(&mut self, owner: usize) -> bool {
        if self.game_over {
            return false;
        }
        let Some(i) = self.ability_owner(owner) else {
            return false;
        };
        let e = &self.entities[i];
        let c = e.champion.as_ref().unwrap();
        if matches!(&c.effect, Effect::Goblin { anchor: None, .. }) {
            return false;
        }
        let a = &c.ability;
        let ready =
            a.last_use <= -100_000_000_000 || self.tick * 50 >= a.start + a.duration + a.cooldown;
        self.players[owner].elixir >= a.cost
            && e.deploy <= 1e-9
            && (a.frozen_allowed || e.stun <= 1e-9)
            && ready
            && !a.active
    }
    pub(super) fn champion_activate(&mut self, owner: usize) -> bool {
        if !self.champion_can_activate(owner) {
            return false;
        }
        let i = self.ability_owner(owner).unwrap();
        if let Effect::Skeleton { threshold, .. } = &self.entities[i].champion.as_ref().unwrap().effect {
            if self.entities[i].souls_collected < *threshold { return false; }
        }
        let now = self.tick * 50;
        let c = self.entities[i].champion.as_mut().unwrap();
        self.players[owner].elixir -= c.ability.cost;
        c.ability.last_use = now;
        c.ability.active = true;
        c.ability.start = now;
        let mut summon = None;
        match &mut c.effect {
            Effect::Skeleton { threshold, offsets } => {
                summon = Some((*threshold, offsets.clone()));
            }
            Effect::Goblin {
                next_hit,
                cast_until,
                ..
            } => {
                c.ability.start = now + 50;
                *next_hit = Some(now + 50);
                *cast_until = now + 933;
            }
            Effect::Mighty {
                pending,
                cast_until,
            } => {
                *pending = Some(now + 500);
                *cast_until = now + 933;
                c.ability.start = now + 500;
            }
            Effect::Queen {
                cast,
                delay,
                pending,
                cast_until,
                ..
            } => {
                *pending = Some(now + *delay);
                *cast_until = Some(now + *cast);
                c.ability.start = now + *delay;
            }
        }
        if let Some((threshold, offsets)) = summon {
            let source = self.entities[i].clone();
            self.spawn_soul_groups(&source, offsets);
            self.entities[i].souls_collected = (self.entities[i].souls_collected - threshold).max(0);
        }
        true
    }
    /// Returns the combat lock after normal character-owned mechanic ticks.
    pub(super) fn champion_combat_tick(&mut self, i: usize) -> bool {
        let Some(mut c) = self.entities[i].champion.take() else {
            return false;
        };
        let now = self.tick * 50;
        if c.ability.active && now - c.ability.start >= c.ability.duration {
            c.ability.active = false;
        }
        let e = &mut self.entities[i];
        let blocked = match &mut c.effect {
            Effect::Skeleton { threshold, .. } => {
                c.ability.cost = if e.souls_collected >= *threshold {
                    (3 - e.souls_collected / 10).max(1) as f64
                } else { 3.0 };
                false
            }
            Effect::Mighty { cast_until, .. } | Effect::Goblin { cast_until, .. } => {
                now < *cast_until
            }
            Effect::Queen {
                attack,
                movement,
                original_move,
                pending,
                cast_until,
                ..
            } => {
                if pending.is_some_and(|time| now >= time) {
                    *pending = None;
                    *original_move = Some(e.move_mode);
                    e.attack_mode = *attack;
                    e.move_mode *= *movement;
                    e.stealth_until = now + c.ability.duration;
                }
                if cast_until.is_some_and(|time| now >= time) {
                    *cast_until = None;
                }
                if !c.ability.active {
                    if let Some(mode) = original_move.take() {
                        e.move_mode = mode;
                        e.attack_mode = 1.0;
                        e.stealth_until = 0;
                    }
                }
                cast_until.is_some()
            }
        };
        e.champion = Some(c);
        blocked
    }
    pub(super) fn champion_object_tick(&mut self, i: usize) {
        if self.entities[i]
            .champion
            .as_ref()
            .is_some_and(|c| matches!(c.effect, Effect::Goblin { .. }))
        {
            self.tether_object_tick(i);
            return;
        }
        let now = self.tick * 50;
        let Some(c) = &mut self.entities[i].champion else {
            return;
        };
        let Effect::Mighty { pending, .. } = &mut c.effect else {
            return;
        };
        if c.ability.active && now - c.ability.start >= c.ability.duration {
            c.ability.active = false;
        }
        if !pending.is_some_and(|time| now >= time) {
            return;
        }
        *pending = None;
        let e = &mut self.entities[i];
        let mut bomb = self.config.ability_bombs[e.stats.key()].clone();
        bomb.id = self.next_id as i32;
        self.next_id += 1;
        bomb.owner = e.owner;
        bomb.x = e.x;
        bomb.y = e.y;
        bomb.facing = (0, if e.owner == 0 { 1000 } else { -1000 });
        bomb.birth = self.tick;
        e.tunnel_destination = (18.0 - e.x, e.y);
        e.tunnel_duration =
            c56::tunnel_duration(units(e.tunnel_destination.0 - e.x).abs(), 650, true);
        e.deploy = e.tunnel_duration + 1.0;
        e.tunnel_total = e.deploy;
        e.underground = true;
        e.target = None;
        e.move_target = None;
        e.route.clear();
        e.goal = None;
        e.clock.finish = 0;
        e.windup = false;
        e.resume_pending = false;
        e.cooldown = e.cooldown.max(e.stats.first);
        e.started = false;
        e.reset_ramp();
        self.entities.push(bomb);
    }
    fn tether_object_tick(&mut self, i: usize) {
        let now = self.tick * 50;
        let monster = match &self.entities[i].champion.as_ref().unwrap().effect {
            Effect::Goblin { monster, .. } => *monster,
            _ => unreachable!(),
        };
        let position = monster
            .and_then(|id| self.index(id))
            .map(|j| (self.entities[j].x, self.entities[j].y));
        let c = self.entities[i].champion.as_mut().unwrap();
        let Effect::Goblin {
            anchor, next_hit, ..
        } = &mut c.effect
        else {
            unreachable!()
        };
        if let Some(position) = position {
            *anchor = Some(position);
        }
        if c.ability.active && now - c.ability.start >= c.ability.duration {
            c.ability.active = false;
        }
        if !c.ability.active {
            *next_hit = None;
            return;
        }
        loop {
            let c = self.entities[i].champion.as_mut().unwrap();
            let Effect::Goblin {
                anchor,
                next_hit,
                damage,
                crown_damage,
                ..
            } = &mut c.effect
            else {
                unreachable!()
            };
            let Some(time) = *next_hit else {
                break;
            };
            if now < time {
                break;
            }
            // A committed pulse may kill its own doctor via death damage.
            // Publish the next timer BEFORE callbacks; on_death can cancel it.
            *next_hit = Some(time + 500);
            let (anchor, damage, crown_damage) = (anchor.unwrap(), *damage, *crown_damage);
            self.tether_pulse(i, anchor, damage, crown_damage);
        }
    }
    fn tether_pulse(&mut self, i: usize, anchor: (f64, f64), damage: f64, crown_damage: f64) {
        let source = &self.entities[i];
        let (x, y, owner) = (source.x, source.y, source.owner);
        let (dx, dy) = (anchor.0 - x, anchor.1 - y);
        let length = dx * dx + dy * dy;
        let count = self.entities.len();
        for j in 0..count {
            let e = &self.entities[j];
            if !e.alive
                || e.owner == owner
                || matches!(e.entity_kind, 2 | 3)
                || e.hidden
                || e.spirit
                || e.underground
                || e.stagger > 1e-9
                || (e.stealth_until > self.tick * 50 && !e.stats.area_while_invisible)
            {
                continue;
            }
            let t = if length > 0.0 {
                (((e.x - x) * dx + (e.y - y) * dy) / length).clamp(0.0, 1.0)
            } else {
                0.0
            };
            let distance = ((e.x - (x + t * dx)).powi(2) + (e.y - (y + t * dy)).powi(2)).sqrt();
            if distance <= 1.0 + e.stats.radius {
                let amount = if e.king || e.stats.name == "Tower" {
                    crown_damage
                } else {
                    damage
                };
                self.damage(j, amount);
            }
        }
    }
    pub(super) fn champion_death(&mut self, i: usize) {
        let e = &mut self.entities[i];
        let Some(c) = &mut e.champion else {
            return;
        };
        if matches!(c.effect, Effect::Skeleton { .. }) { return; }
        c.ability.active = false;
        match &mut c.effect {
            Effect::Skeleton { .. } => unreachable!(),
            Effect::Goblin { next_hit, .. } => *next_hit = None,
            Effect::Mighty { pending, .. } => *pending = None,
            Effect::Queen {
                pending,
                cast_until,
                original_move,
                ..
            } => {
                *pending = None;
                *cast_until = None;
                if let Some(mode) = original_move.take() {
                    e.move_mode = mode;
                    e.attack_mode = 1.0;
                    e.stealth_until = 0;
                }
            }
        }
    }
}
