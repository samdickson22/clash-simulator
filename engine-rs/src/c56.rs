//! C56 mechanics, gated separately from the admitted P16 scope.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Periodic {
    pub source_id: i32,
    pub remaining: f64,
    pub interval: f64,
    pub next_hit: f64,
    pub damage: f64,
    pub hard: Option<f64>,
    pub affects_hidden: bool,
}

pub(super) fn tunnel_duration(mut remaining: i64, speed: i64, from_speed: bool) -> f64 {
    let mut ticks = 0;
    let reached = if from_speed { speed } else { 1000 };
    while remaining > 0 {
        ticks += 1;
        let mut budget = speed;
        while budget > 0 {
            let substep = budget.min(250);
            remaining = (remaining - substep).max(0);
            if remaining <= reached {
                remaining = 0;
                break;
            }
            budget -= substep;
        }
    }
    ticks as f64 * 0.05
}

impl Entity {
    pub(super) fn ramp_damage(&self) -> f64 {
        self.stats
            .ramp_stages
            .iter()
            .rev()
            .find(|s| self.ramp_time >= s.0 as f64)
            .or(self.stats.ramp_stages.first())
            .map(|s| s.1)
            .unwrap_or(self.stats.damage)
    }
    pub(super) fn reset_ramp(&mut self) {
        if !self.stats.ramp_stages.is_empty() {
            self.ramp_target = None;
            self.ramp_time = 0.0;
            self.stats.damage = self.stats.ramp_stages[0].1;
        }
    }

    pub(super) fn tick_death_immunity(&mut self) {
        self.death_immunity = self
            .death_immunity
            .and_then(|v| (v + 50 <= 250).then_some(v + 50));
    }

    pub(super) fn slow_percent(&self, attack: bool) -> i64 {
        let mut factor: f64 = if self.slow_ms > 0 { 0.7 } else { 1.0 };
        for slow in &self.area_slows {
            factor = factor.min(if attack { slow.2 } else { slow.1 });
        }
        if !attack {
            factor = factor.min(self.move_mode.max(0.0));
        }
        (factor * 100.0).round_ties_even().max(0.0) as i64
    }
}

impl BattleState {
    pub(super) fn tunnel_move(&mut self, i: usize) {
        let e = &mut self.entities[i];
        e.moving = false;
        let elapsed = (e.tunnel_total - e.deploy).max(0.0);
        if e.tunnel_duration <= 0.0 || elapsed + 0.05 >= e.tunnel_duration - 1e-12 {
            e.x = units(e.tunnel_destination.0) as f64 / 1000.0;
            e.y = units(e.tunnel_destination.1) as f64 / 1000.0;
            return;
        }
        let (dx, dy) = (
            units(e.tunnel_destination.0 - e.x),
            units(e.tunnel_destination.1 - e.y),
        );
        let (mx, my) = if e.stats.tunnel_speed >= isqrt(dx * dx + dy * dy) {
            (dx, dy)
        } else {
            norm(dx, dy, e.stats.tunnel_speed)
        };
        e.x = (units(e.x) + mx) as f64 / 1000.0;
        e.y = (units(e.y) + my) as f64 / 1000.0;
    }

    pub(super) fn observe_ramp(&mut self, i: usize, j: Option<usize>, engaged: bool) {
        if self.entities[i].stats.ramp_stages.is_empty() {
            return;
        }
        let valid = engaged
            && self.entities[i].stun <= 0.0
            && j.is_some_and(|j| {
                let e = &self.entities[j];
                e.alive
                    && !e.hidden
                    && !e.spirit
                    && !e.underground
                    && e.death_immunity.is_none()
                    && e.stagger <= 1e-9
            });
        let e = &mut self.entities[i];
        if !valid {
            e.reset_ramp();
            return;
        }
        if e.ramp_target != e.target {
            e.ramp_target = e.target;
            e.ramp_time = 0.0;
            e.stats.damage = e.stats.ramp_stages[0].1;
        }
        e.ramp_time += e.attack_work() as f64;
    }

    pub(super) fn death_travel_move(&mut self, i: usize, external: (i64, i64)) {
        let e = &mut self.entities[i];
        let target = e.death_travel.unwrap();
        let (dx, dy) = (units(target.0 - e.x), units(target.1 - e.y));
        let d = isqrt(dx * dx + dy * dy).max(1);
        let work = d.min(250);
        let (mut mx, mut my) = ((dx * 256 / d) * work / 256, (dy * 256 / d) * work / 256);
        if e.avoidance != 0 {
            let retained = 256 - e.avoidance.abs();
            (mx, my) = norm(
                (retained * mx >> 8) + (e.avoidance * my >> 8),
                (retained * my >> 8) + (-mx * e.avoidance >> 8),
                work,
            );
        }
        e.x = (units(e.x) + mx + external.0).clamp(0, 17999) as f64 / 1000.0;
        e.y = (units(e.y) + my + external.1).clamp(0, 31999) as f64 / 1000.0;
        e.death_ticks -= 1;
        if e.death_ticks == 0 {
            e.death_travel = None;
        }
    }

    pub(super) fn ghost_tick(&mut self, i: usize) {
        let a = &self.entities[i];
        let engaged = a.stats.ghost_range
            && a.target.and_then(|id| self.index(id)).is_some_and(|j| {
                let b = &self.entities[j];
                b.alive
                    && !b.hidden
                    && !b.spirit
                    && !b.underground
                    && b.stagger <= 1e-9
                    && b.death_immunity.is_none()
                    && b.stealth_until <= self.tick * 50
                    && reach(a, b, 0.0)
            });
        if engaged {
            self.entities[i].ghost_time = 0.0;
        } else {
            self.entities[i].ghost_time += 50.0;
            if self.entities[i].ghost_time >= self.entities[i].stats.ghost_fade as f64 {
                self.entities[i].stealth_until = 2_147_483_647;
            }
        }
    }

    pub(super) fn bomb_tick(&mut self, i: usize) {
        self.entities[i].effect_age += 0.05;
        if self.entities[i].effect_age < self.entities[i].bomb_timer - 1e-9 {
            return;
        }
        let bomb = self.entities[i].clone();
        let targets: Vec<usize> = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(j, e)| {
                (e.alive
                    && e.owner != bomb.owner
                    && !e.hidden
                    && !e.spirit
                    && !e.underground
                    && e.stagger <= 1e-9
                    && !matches!(e.entity_kind, 2 | 3)
                    && Self::in_area(e, bomb.x, bomb.y, bomb.bomb_radius))
                .then_some(j)
            })
            .collect();
        for j in targets {
            self.damage(j, bomb.bomb_damage);
            self.radial_knockback(
                j,
                (bomb.x, bomb.y),
                bomb.bomb_knockback,
                bomb.bomb_ignores_mass,
                false,
                None,
            );
        }
        if let Some(templates) = self.config.bomb_children.get(&bomb.stats.name).cloned() {
            self.spawn_death_templates(&bomb,templates);
        }
        self.entities[i].alive = false;
    }

    pub(super) fn stun_target(&mut self, i: usize, duration: f64) {
        self.stun_target_mode(i, duration, true);
    }
    pub(super) fn stun_target_mode(&mut self, i: usize, duration: f64, interrupt: bool) {
        if duration>0.0 && !self.entities[i].spirit && !self.entities[i].underground
            && !self.entities[i].hidden && self.entities[i].stagger<=1e-9 && !self.entities[i].dash_travel() {
            self.hook_cancel(i);
        }
        let e = &mut self.entities[i];
        // A committed on-hit status still interrupts a depleted character's
        // start-of-phase combat component. Python can_receive_effect does
        // not test HP (entities.py:610-624,2987-3005).
        if duration <= 0.0 || e.spirit || e.underground || e.hidden || e.stagger > 1e-9 || e.dash_travel()
        {
            return;
        }
        e.consume_clock_reseed();
        e.dash_cancel();
        if e.stun <= 1e-9 {
            e.frozen_moving = e.moving || e.move_target.is_some();
        }
        if interrupt {
            e.reset_ramp();
        }
        if !interrupt || e.stats.ordinary || e.king || e.stats.name == "Tower" {
            e.freeze_pause = e.freeze_pause.max(duration);
        }
        e.stun = e.stun.max(duration);
        e.force_due = false;
        if e.started && !e.moving {
            e.windup = true;
        }
        e.target = None;
        e.move_target = None;
        e.pending_lethal = false;
        e.last_target = None;
        if interrupt && !e.stats.ordinary && !e.king && e.stats.name != "Tower" {
            e.cooldown = e.stats.interval as f64 / 1000.0;
            e.clock.finish = 0;
            e.clock.stop();
            e.windup = false;
            e.started = false;
            e.resume_pending = false;
        }
    }

    pub(super) fn electro_land(&mut self, i: usize, source: &Entity) {
        if let Some(j) = source
            .shot_target
            .and_then(|id| self.index(id))
            .filter(|&j| self.entities[j].alive)
        {
            self.damage(j, source.stats.damage);
            self.stun_target(j, source.stats.spirit_stun);
            let target = &self.entities[j];
            let mut chain = self.config.cards["ElectroSpirit"].chain.clone().unwrap();
            chain.owner = source.owner;
            chain.id = self.next_id as i32;
            self.next_id += 1;
            chain.x = target.x;
            chain.y = target.y;
            chain.chain_origin = (target.x, target.y);
            chain.chain_remaining = source.stats.chain_count.saturating_sub(1);
            chain.hit_ids = vec![target.id];
            chain.birth = self.tick;
            self.entities.push(chain);
        }
        self.entities[i].alive = false;
        self.entities[i].hp = 0.0;
    }

    pub(super) fn dragon_chain_hit(&mut self, i: usize, j: usize) {
        if !self.entities[i].stats.dragon_chain { return; }
        let source = &self.entities[i];
        let Some(template) = self.config.cards.get(&source.stats.name).and_then(|c| c.chain.as_ref()) else { return; };
        let mut chain = template.clone();
        chain.id = self.next_id as i32; self.next_id += 1;
        chain.owner = source.owner;
        chain.x = self.entities[j].x; chain.y = self.entities[j].y;
        chain.chain_origin = (chain.x,chain.y);
        chain.hit_ids = vec![self.entities[j].id];
        chain.birth = self.tick; self.entities.push(chain);
    }
    pub(super) fn chain_tick(&mut self, i: usize) {
        let mut remaining = 0.05;
        while self.entities[i].chain_remaining > 0 {
            let chain = &self.entities[i];
            let eligible = |e: &Entity| {
                e.alive
                    && e.owner != chain.owner
                    && !e.hidden
                    && !e.spirit
                    && !e.underground
                    && (e.class == "Troop" || e.class == "Building")
                    && e.death_immunity.is_none()
                    && chain.can_hit_plane(e)
                    && e.stagger <= 1e-9
                    && !chain.hit_ids.contains(&e.id)
            };
            let target = chain.shot_target.and_then(|id| self.index(id));
            let j = if let Some(j) = target {
                j
            } else {
                let candidates: Vec<(usize, f64)> = self
                    .entities
                    .iter()
                    .enumerate()
                    .filter(|(_, e)| eligible(e))
                    .map(|(j, e)| {
                        (
                            j,
                            ((e.x - chain.chain_origin.0).powi(2)
                                + (e.y - chain.chain_origin.1).powi(2)
                                - e.stats.distance_discount / 1_000_000.0)
                                .max(0.0)
                                .sqrt(),
                        )
                    })
                    .filter(|&(_, d)| d <= chain.stats.chain_range + 1e-9)
                    .collect();
                let minimum = candidates
                    .iter()
                    .map(|&(_, d)| d)
                    .fold(f64::INFINITY, f64::min);
                let sign = if chain.owner == 0 { 1.0 } else { -1.0 };
                let selected = candidates
                    .iter()
                    .filter(|&&(_, d)| d <= minimum + 1e-6)
                    .map(|&(j, _)| j)
                    .min_by(|&a, &b| {
                        let (a, b) = (&self.entities[a], &self.entities[b]);
                        (sign * (a.x - 9.0))
                            .total_cmp(&(sign * (b.x - 9.0)))
                            .then((sign * (a.y - 16.0)).total_cmp(&(sign * (b.y - 16.0))))
                            .then(a.id.cmp(&b.id))
                    });
                let Some(j) = selected else {
                    self.entities[i].alive = false;
                    return;
                };
                self.entities[i].shot_target = Some(self.entities[j].id);
                self.entities[i].chain_time = self.entities[i].stats.chain_interval;
                j
            };
            let chain = &self.entities[i];
            let target = &self.entities[j];
            if !target.alive
                || target.owner == chain.owner
                || target.hidden
                || target.spirit
                || target.underground
                || target.death_immunity.is_some()
                || target.stagger > 1e-9 || !chain.can_hit_plane(target)
                || chain.hit_ids.contains(&target.id)
            {
                self.entities[i].alive = false;
                return;
            }
            let (x, y, id) = (target.x, target.y, target.id);
            let (dx, dy) = (units(x - chain.x), units(y - chain.y));
            let fixed = chain.stats.chain_interval > 0.0;
            let until = if fixed { chain.chain_time }
                else { isqrt(dx*dx+dy*dy) as f64 * 0.05 / chain.stats.speed.max(1) as f64 };
            if remaining + 1e-12 < until {
                let (mx,my) = if fixed {
                    let duration = (until * 1_000_000_000.0).round_ties_even().max(1.0) as i64;
                    let consumed = (remaining * 1_000_000_000.0).round_ties_even().clamp(0.0,duration as f64) as i64;
                    (dx*consumed/duration,dy*consumed/duration)
                } else {
                    let work = (chain.stats.speed as f64 * remaining / 0.05).round_ties_even().max(0.0) as i64;
                    let length = isqrt(dx*dx+dy*dy);
                    if work >= length {(dx,dy)} else {norm(dx,dy,work)}
                };
                let e = &mut self.entities[i];
                e.x = (units(e.x)+mx) as f64/1000.0;
                e.y = (units(e.y)+my) as f64/1000.0;
                if fixed { e.chain_time = (e.chain_time - remaining).max(0.0); }
                return;
            }
            remaining = (remaining - until).max(0.0);
            let e = &mut self.entities[i];
            e.x = x;
            e.y = y;
            e.chain_time = 0.0;
            e.hit_ids.push(id);
            let (damage, stun) = (e.stats.damage, e.stats.spirit_stun);
            self.damage(j, damage);
            self.stun_target(j, stun);
            let e = &mut self.entities[i];
            e.chain_origin = (x, y);
            e.chain_remaining -= 1;
            e.shot_target = None;
            if remaining <= 0.0 {
                break;
            }
        }
        if self.entities[i].chain_remaining == 0 {
            self.entities[i].alive = false;
        }
    }

    pub(super) fn periodic_tick(&mut self, i: usize) {
        let mut buffs = std::mem::take(&mut self.entities[i].periodic);
        for buff in &mut buffs {
            buff.remaining = (buff.remaining - 0.05).max(0.0);
            buff.hard = buff.hard.map(|v| (v - 0.05).max(0.0));
            buff.next_hit -= 0.05;
            while buff.next_hit <= 1e-9 && self.entities[i].alive {
                if !self.entities[i].hidden || buff.affects_hidden {
                    self.damage(i, buff.damage);
                }
                buff.next_hit += buff.interval;
            }
        }
        buffs.retain(|b| {
            b.remaining > 1e-9 && b.hard.is_none_or(|v| v > 1e-9) && self.entities[i].alive
        });
        self.entities[i].periodic = buffs;
    }

    fn area_targets(&self, area: &Entity, spell: &Spell) -> Vec<usize> {
        self.entities
            .iter()
            .enumerate()
            .filter(|(_, e)| {
                e.alive
                    && e.owner != area.owner
                    && !e.spirit
                    && !e.underground
                    && e.stagger <= 1e-9
                    && (!e.hidden || spell.affects_hidden)
                    && (e.class == "Troop" || e.class == "Building")
                    && (spell.hits_air.unwrap_or(true) || !e.airborne())
                    && Self::in_area(e, area.x, area.y, area.effect_radius)
            })
            .map(|(j, _)| j)
            .collect()
    }

    fn area_damage(&self, j: usize, spell: &Spell) -> f64 {
        let target = &self.entities[j];
        if target.king || target.stats.name == "Tower" {
            spell.crown_tower_damage.unwrap_or(spell.damage)
        } else if target.class == "Building" {
            spell.building_damage.unwrap_or(spell.damage)
        } else {
            spell.damage
        }
    }

    pub(super) fn c56_area_tick(&mut self, i: usize) {
        if self.entities[i].birth >= self.tick {
            return;
        }
        let before = self.entities[i].effect_age;
        self.entities[i].effect_age += 0.05;
        let area = self.entities[i].clone();
        let spell = self.config.cards[&area.spell_name].spell.clone().unwrap();
        let duration = area.effect_duration;
        let deadline = area.effect_age.min(duration);
        if spell.max_damage_ticks > 0 {
            let mut next = area.next_damage.unwrap_or(
                spell
                    .initial_damage_delay
                    .unwrap_or(spell.damage_tick_interval),
            );
            while self.entities[i].damage_ticks < spell.max_damage_ticks && next <= deadline + 1e-9
            {
                for j in self.area_targets(&area, &spell) {
                    self.damage(j, self.area_damage(j, &spell));
                }
                self.entities[i].damage_ticks += 1;
                next += spell.damage_tick_interval;
            }
            self.entities[i].next_damage = Some(next);
        }
        if spell.freeze_effect && !area.effect_applied {
            let targets: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j,e)| {
                (e.alive && e.owner != area.owner && !e.hidden && !e.spirit && !e.underground
                    && e.stagger <= 1e-9 && (e.freeze_carrier || e.class == "Troop" || e.class == "Building")
                    && (spell.hits_air.unwrap_or(true) || !e.airborne())
                    && Self::in_area(e,area.x,area.y,area.effect_radius)).then_some(j)
            }).collect();
            let expiry = self.tick as f64 * 0.05 + duration;
            for j in targets {
                if self.entities[j].freeze_carrier { self.entities[j].freeze_expiry = self.entities[j].freeze_expiry.max(expiry); }
                else { self.freeze_for(j,duration,expiry); }
            }
            self.entities[i].effect_applied = true;
        }
        if before < duration && !spell.freeze_effect {
            let interval = if spell.effect_tick_interval > 0.0 {
                spell.effect_tick_interval
            } else {
                0.05
            };
            let mut next = area.next_effect.unwrap_or(interval.max(0.05));
            while next <= deadline + 1e-9 && next < duration - 1e-9 {
                for j in self.area_targets(&area, &spell) {
                    let damage = self.area_damage(j, &spell);
                    let e = &mut self.entities[j];
                    if spell.attract_percentage > 0.0 && e.class != "Building" {
                        let (dx, dy) = (units(area.x - e.x), units(area.y - e.y));
                        let per_tick = ((e.stats.speed as f64 * spell.push_speed_factor / 100.0)
                            as i64 as f64
                            * spell.attract_percentage
                            / 100.0) as i64;
                        let amount = (per_tick as f64 * interval / 0.05).round_ties_even() as i64;
                        if amount > 0 && (dx != 0 || dy != 0) {
                            let (vx, vy) = norm(dx, dy, amount);
                            e.controlled_vector.0 += vx;
                            e.controlled_vector.1 += vy;
                            e.controlled_vector.2 += 1;
                            e.controlled_bypass = true;
                        }
                    }
                    let hard = spell
                        .periodic_damage_controlled_by_parent
                        .then_some((duration - next).max(0.0));
                    if spell.target_local_damage && damage > 0.0 && spell.damage_tick_interval > 0.0
                    {
                        if let Some(buff) = e.periodic.iter_mut().find(|b| b.source_id == area.id) {
                            buff.remaining =
                                buff.remaining.max(spell.periodic_damage_buff_duration);
                            buff.damage = damage;
                            if let Some(hard) = hard {
                                buff.hard = Some(buff.hard.unwrap_or(hard).min(hard));
                            }
                        } else {
                            e.periodic.push(Periodic {
                                source_id: area.id,
                                remaining: spell.periodic_damage_buff_duration,
                                interval: spell.damage_tick_interval,
                                next_hit: spell.damage_tick_interval,
                                damage,
                                hard,
                                affects_hidden: spell.affects_hidden,
                            });
                        }
                    }
                    let movement = spell.speed_multiplier.unwrap_or(1.0);
                    let attack = if spell.slows_attack_speed.unwrap_or(true) {
                        movement
                    } else {
                        1.0
                    };
                    let mut remaining = interval.max(spell.slow_refresh_duration);
                    if spell.cap_buff_time_to_effect {
                        remaining = remaining.min((duration - next).max(0.0));
                    }
                    if movement.min(attack) < 1.0 && remaining > 1e-9 {
                        if let Some(slow) = e
                            .area_slows
                            .iter_mut()
                            .find(|s| s.1 == movement && s.2 == attack)
                        {
                            slow.0 = slow.0.max(remaining);
                        } else {
                            e.area_slows.push((remaining, movement, attack, 1.0));
                        }
                    }
                }
                next += interval;
            }
            self.entities[i].next_effect = Some(next);
        }
        if area.effect_age >= duration - 1e-9 {
            self.entities[i].alive = false;
        }
    }

    pub(super) fn delivery_tick(&mut self, i: usize) {
        self.entities[i].effect_age += 0.05;
        let source = self.entities[i].clone();
        let card = self.config.cards[&source.spell_name].clone();
        let spell = card.spell.as_ref().unwrap();
        if source.effect_age + 1e-9 < spell.impact_delay {
            return;
        }
        let (dx, dy) = (
            units(source.aim.0 - source.x),
            units(source.aim.1 - source.y),
        );
        let distance = isqrt(dx * dx + dy * dy);
        if distance > source.stats.speed {
            let (mx, my) = norm(dx, dy, source.stats.speed);
            self.entities[i].x = (units(source.x) + mx) as f64 / 1000.0;
            self.entities[i].y = (units(source.y) + my) as f64 / 1000.0;
            return;
        }
        let cast = Cast {
            player: source.owner as usize,
            name: source.spell_name.clone(),
            x: source.aim.0,
            y: source.aim.1,
        };
        self.direct_spell(&cast, spell, None);
        for template in &card.spawns[cast.player] {
            let mut child = template.clone();
            child.id = self.next_id as i32;
            self.next_id += 1;
            child.x =
                (cast.x + template.x * if cast.x < 9.0 { 1.0 } else { -1.0 }).clamp(0.25, 17.75);
            child.y = (cast.y + template.y).clamp(0.25, 31.75);
            child.x = units(child.x) as f64 / 1000.0;
            child.y = units(child.y) as f64 / 1000.0;
            child.lane = if child.x < 9.0 { 1 } else { 2 };
            child.birth = self.tick;
            self.entities.push(child);
        }
        self.entities[i].alive = false;
    }

    pub(super) fn ranked_strike_tick(&mut self, i: usize) {
        self.entities[i].effect_age += 0.05;
        let area = self.entities[i].clone();
        let spell = self.config.cards[&area.spell_name].spell.clone().unwrap();
        let deadline = area.effect_age.min(area.effect_duration);
        while self.entities[i].strikes_elapsed < spell.max_targets
            && (self.entities[i].strikes_elapsed + 1) as f64 * spell.strike_interval
                <= deadline + 1e-9
        {
            self.entities[i].strikes_elapsed += 1;
            let target = self
                .entities
                .iter()
                .enumerate()
                .filter(|(_, e)| {
                    e.alive
                        && e.owner != area.owner
                        && !e.spirit
                        && !e.underground
                        && !e.hidden
                        && e.stagger <= 1e-9
                        && (e.class == "Troop" || e.class == "Building")
                        && !self.entities[i].hit_ids.contains(&e.id)
                        && Self::in_area(e, area.x, area.y, area.effect_radius)
                })
                .min_by(|(_, a), (_, b)| b.hp.total_cmp(&a.hp).then(a.id.cmp(&b.id)))
                .map(|(j, _)| j);
            if let Some(j) = target {
                let id = self.entities[j].id;
                self.entities[i].hit_ids.push(id);
                let cast = Cast {
                    player: area.owner as usize,
                    name: area.spell_name.clone(),
                    x: area.x,
                    y: area.y,
                };
                self.spell_hit(j, &cast, &spell, None);
                self.stun_target(j, spell.stun_duration);
            }
        }
        if area.effect_age >= area.effect_duration - 1e-9 {
            self.entities[i].alive = false;
        }
    }

    pub(super) fn rotate(&self, x: i64, y: i64, angle: usize) -> (i64, i64) {
        let (cos, sin) = self.config.rotations[angle % 360];
        ((cos * x - sin * y) >> 10, (sin * x + cos * y) >> 10)
    }

    pub(super) fn projectile_volley(&mut self, card: &Card, player: usize, x: f64, y: f64) {
        let spell = card.spell.as_ref().unwrap();
        let count = spell.multiple_projectiles.unwrap_or(1).max(1);
        let waves = spell.damage_waves.unwrap_or(1).max(1);
        let radius = units(spell.spread_radius).max(0);
        for wave in 0..waves {
            let group = self.next_id as i32;
            for index in 0..count {
                // spells.py:395-451. Each member of every volley consumes
                // one CPython randrange(359), including its center member.
                let (dx, dy) = if spell.projectile_pattern == "grouped_ring" {
                    let jitter = units(spell.radius).max(0) * 60 / 100;
                    let ring = (radius - jitter).max(0);
                    let (bx, by) = if index == 0 {
                        (0, 0)
                    } else {
                        self.rotate(ring, 0, (360 / (count - 1)) * (index - 1))
                    };
                    let angle = self.rng.below(359) as usize;
                    let (jx, jy) = self.rotate(0, jitter, angle);
                    let (dx, dy) = (bx + jx, by + jy);
                    let limit = radius * 90 / 100;
                    if limit > 0 && dx * dx + dy * dy > limit * limit {
                        norm(dx, dy, limit)
                    } else {
                        (dx, dy)
                    }
                } else if index == 0 {
                    (0, 0)
                } else {
                    let inner = radius >> 2;
                    let span = (radius - inner).max(0);
                    let r = if span > 0 {
                        self.rng.below(span as u32) as i64 + inner
                    } else {
                        0
                    };
                    self.rotate(r, 0, (360 / count) * index)
                };
                // Preserve the Python upper-seat subtraction round trip.
                let mut aim = (x + dx as f64 / 1000.0, y + dy as f64 / 1000.0);
                if player == 1 {
                    aim = (x - (aim.0 - x), y - (aim.1 - y));
                }
                let mut shot = card.units[player][0].clone();
                shot.id = self.next_id as i32;
                self.next_id += 1;
                shot.aim = aim;
                shot.damage_group = Some(group);
                shot.launch_delay = wave as f64 * spell.damage_wave_interval;
                shot.birth = self.tick;
                self.entities.push(shot);
            }
        }
    }
}
