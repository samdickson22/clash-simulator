//! Repaired opponent-scope effects, separate from C56 controller admission.
use super::*;

fn unit_axes() -> (f64, f64, f64) { (1.0, 1.0, 1.0) }

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Cursed {
    pub id: i32,
    pub expiry: f64,
    pub corpse: Option<(f64, f64, bool)>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind")]
pub(super) enum Effect {
    Container { delay: f64, complete: bool, child: Box<Entity> },
    StartAction { child: Box<Entity> },
    Haste {
        delay: f64, axes: (f64,f64,f64), refresh: f64, cap: bool,
        interval: f64, once: bool, applied: bool, impact_applied: bool,
        impact: Option<Box<Entity>>, damage: f64, crown_damage: f64, next_scan: Option<f64>,
    },
    Graveyard {
        interval: f64, initial: f64, deadlines: Vec<f64>, maximum: usize,
        offsets: Vec<(f64, f64)>, mirror_x: bool, orient_y: bool,
        spawned: usize, next_spawn: f64, radius: f64,
    },
    SpawnDamage {
        damage: f64,
        crown_damage: f64,
        hits_air: bool,
        hits_ground: bool,
        #[serde(default)]
        damage_done: bool,
        #[serde(default)]
        buff_done: bool,
        #[serde(default)]
        buff_duration: f64,
        #[serde(default = "unit_axes")]
        axes: (f64, f64, f64),
    },
    Heal {
        heal_per_tick: f64,
        heal_interval: f64,
        recipients: Vec<i32>,
        snapshot_taken: bool,
        ticks_done: usize,
    },
    Curse {
        scan_interval: f64,
        buff_time: f64,
        damage: f64,
        crown_damage: f64,
        interval: f64,
        next_scan: f64,
        cursed: Vec<Cursed>,
    },
    Void {
        pulse_times: Vec<f64>,
        hit_delay: f64,
        tier_max_units: Vec<usize>,
        tier_damage: Vec<f64>,
        tier_crown_damage: Vec<f64>,
        pulses_done: usize,
        pending: Vec<(f64, i32, f64)>,
    },
    Vines {
        select_delay: f64,
        action_delays: Vec<f64>,
        snare_duration: f64,
        damage: f64,
        crown_damage: f64,
        interval: f64,
        selected: bool,
        pending: Vec<(f64, i32)>,
        grounded: Vec<(f64, i32)>,
    },
}

impl Entity {
    pub(super) fn haste_percent(&self, axis: usize) -> i64 {
        let factor = self.hastes.iter().map(|h| match axis { 1 => h.1, 2 => h.2, _ => h.3 })
            .fold(1.0_f64, f64::max);
        (factor * 100.0).round_ties_even().max(0.0) as i64
    }
    pub(super) fn can_hit_plane(&self, other: &Entity) -> bool {
        if other.airborne() {
            self.stats.can_air
        } else {
            self.stats.can_ground.unwrap_or(true)
        }
    }

    pub(super) fn spawn_work(&self) -> f64 {
        let mut multiplier: f64 = if self.slow_ms > 0 { 0.7 } else { 1.0 };
        for slow in &self.area_slows {
            multiplier = multiplier.min(slow.3);
        }
        let debuff = (multiplier * 100.0).round_ties_even().max(0.0) as i64;
        (debuff * self.haste_percent(3) / 100 / 2) as f64
    }

    pub(super) fn airborne(&self) -> bool {
        (self.stats.air || self.jump.is_some()) && !self.grounded
    }
    pub(super) fn above_surface(&self) -> bool {
        self.airborne() || (self.leap_airborne() && !self.grounded)
    }
    pub(super) fn collision_air(&self, tick: i64) -> bool {
        self.above_surface() || self.stats.hover || self.landed_tick == tick
    }
}

impl BattleState {
    fn scope_child(&mut self, source: &Entity, template: &Entity) {
        let mut child = template.clone();
        child.id = self.next_id as i32; self.next_id += 1;
        child.x = source.x; child.y = source.y; child.owner = source.owner;
        child.birth = self.tick; self.entities.push(child);
    }
    fn haste_scan(&mut self, area: &Entity, duration: f64, axes: (f64,f64,f64)) {
        if duration <= 1e-9 { return; }
        for e in &mut self.entities {
            if !e.alive || e.owner != area.owner || e.id == area.id
                || !(e.class == "Troop" || e.class == "Building")
                || !Self::in_area(e,area.x,area.y,area.effect_radius) { continue; }
            if let Some(h) = e.hastes.iter_mut().find(|h| (h.1,h.2,h.3)==axes) {
                h.0 = h.0.max(duration);
            } else { e.hastes.push((duration,axes.0,axes.1,axes.2)); }
        }
    }
    pub(super) fn slow_target(&mut self, j: usize, duration: f64, axes: (f64, f64, f64)) {
        let e = &mut self.entities[j];
        if !e.alive || e.hidden || e.underground || e.spirit || e.stagger > 1e-9 || e.dash_travel() || duration <= 1e-9 || axes.0.min(axes.1).min(axes.2) >= 1.0 { return; }
        if axes == (0.7, 0.7, 0.7) {
            e.slow_ms = e.slow_ms.max((duration*1000.0).round_ties_even() as i64);
        } else if let Some(slow) = e.area_slows.iter_mut().find(|s| (s.1,s.2,s.3)==axes) {
            slow.0 = slow.0.max(duration);
        } else { e.area_slows.push((duration,axes.0,axes.1,axes.2)); }
    }
    pub(super) fn collector_tick(&mut self, i: usize) {
        let e = &mut self.entities[i];
        e.collect_elapsed += e.spawn_work();
        while e.collect_elapsed + 1e-6 >= e.stats.collect_interval {
            e.collect_elapsed -= e.stats.collect_interval;
            if !self.game_over && e.stats.collect_amount > 0.0 {
                let p = &mut self.players[e.owner as usize];
                p.elixir = (p.elixir + e.stats.collect_amount).min(10.0);
            }
        }
    }

    pub(super) fn remember_cursed_dead(&mut self) {
        if !self
            .entities
            .iter()
            .any(|e| matches!(&e.scope, Some(Effect::Curse { .. })))
        {
            return;
        }
        let dead: BTreeMap<i32, (f64, f64, bool)> = self
            .entities
            .iter()
            .filter(|e| !e.alive)
            .map(|e| (e.id, (e.x, e.y, e.spirit)))
            .collect();
        for e in &mut self.entities {
            if let Some(Effect::Curse { cursed, .. }) = &mut e.scope {
                for target in cursed {
                    if let Some(&body) = dead.get(&target.id) {
                        target.corpse = Some(body);
                    }
                }
            }
        }
    }
    fn internal_spawn_valid(&self, x: f64, y: f64, radius: f64) -> bool {
        if !(0.25 - 1e-9..=17.75 + 1e-9).contains(&x) || !(0.25 - 1e-9..=31.75 + 1e-9).contains(&y)
        {
            return false;
        }
        let touching = |value: f64, limit: i32| {
            if (value - value.round_ties_even()).abs() <= 1e-9 {
                vec![
                    value.round_ties_even() as i32 - 1,
                    value.round_ties_even() as i32,
                ]
                .into_iter()
                .filter(|&v| v >= 0 && v < limit)
                .collect::<Vec<_>>()
            } else {
                vec![value.floor() as i32]
            }
        };
        if touching(x, 18).iter().any(|&tx| {
            touching(y, 32)
                .iter()
                .any(|&ty| self.config.blocked_tiles[(ty * 18 + tx) as usize])
        }) {
            return false;
        }
        if (15.0..=17.0).contains(&y) && !(2.0..=5.0).contains(&x) && !(13.0..=16.0).contains(&x) {
            return false;
        }
        !self.entities.iter().any(|e| {
            if !e.alive || e.class != "Building" {
                return false;
            }
            let crown = e.king || e.stats.name == "Tower";
            let half = if e.king { 2.0 } else { 1.5 };
            (crown && (x - e.x).abs() <= half + 1e-9 && (y - e.y).abs() <= half + 1e-9)
                || units(x - e.x).pow(2) + units(y - e.y).pow(2)
                    < units(radius + e.stats.radius).pow(2)
        })
    }
    fn snap_internal_spawn(&self, x: f64, y: f64, owner: i32, radius: f64) -> (f64, f64) {
        if self.internal_spawn_valid(x, y, radius) {
            return (x, y);
        }
        if (15.0..=17.0).contains(&y) && !(2.0..=5.0).contains(&x) && !(13.0..=16.0).contains(&x) {
            let bank = if owner == 0 { 14.5 } else { 17.5 };
            if self.internal_spawn_valid(x, bank, radius) {
                return (x, bank);
            }
        }
        let mut best = (x, y);
        let mut distance = f64::INFINITY;
        let rotation = if owner == 0 { 1.0 } else { -1.0 };
        for dx in -3..=3 {
            for dy in -3..=3 {
                let p = (
                    x + dx as f64 * 0.5 * rotation,
                    y + dy as f64 * 0.5 * rotation,
                );
                if self.internal_spawn_valid(p.0, p.1, radius) {
                    let d = ((x - p.0).powi(2) + (y - p.1).powi(2)).sqrt();
                    if d < distance - 1e-9 {
                        distance = d;
                        best = p;
                    }
                }
            }
        }
        if distance.is_finite() {
            return best;
        }
        let clamped = (x.clamp(0.5, 17.5), y.clamp(0.5, 31.5));
        if self.internal_spawn_valid(clamped.0, clamped.1, radius) {
            return clamped;
        }
        for step in [0.5, 1.0, 1.5, 2.0] {
            let p = (
                clamped.0 + (9.0 - clamped.0) * step * 0.1,
                clamped.1 + (16.0 - clamped.1) * step * 0.1,
            );
            if self.internal_spawn_valid(p.0, p.1, radius) {
                return p;
            }
        }
        best
    }
    fn curse_spawn(&mut self, area: &Entity, x: f64, y: f64) {
        let mut child = self.config.cards[&area.spell_name].spawns[area.owner as usize][0].clone();
        let p = self.snap_internal_spawn(
            x.clamp(0.25, 17.75),
            y.clamp(0.25, 31.75),
            area.owner,
            child.stats.radius,
        );
        child.x = units(p.0) as f64 / 1000.0;
        child.y = units(p.1) as f64 / 1000.0;
        child.lane = if child.x < 9.0 { 1 } else { 2 };
        child.id = self.next_id as i32;
        self.next_id += 1;
        child.birth = self.tick;
        self.entities.push(child);
    }
    fn scope_targets(&self, area: &Entity) -> Vec<usize> {
        self.entities
            .iter()
            .enumerate()
            .filter_map(|(i, e)| {
                (e.alive
                    && e.owner != area.owner
                    && !e.spirit
                    && !e.underground
                    && !e.hidden
                    && e.stagger <= 1e-9
                    && (e.class == "Troop" || e.class == "Building")
                    && Self::in_area(e, area.x, area.y, area.effect_radius))
                .then_some(i)
            })
            .collect()
    }
    pub(super) fn freeze_until(&mut self, j: usize, expiry: f64) {
        let duration = (expiry - self.tick as f64 * 0.05).max(0.0);
        if duration <= 1e-9 {
            return;
        }
        self.freeze_for(j, duration, expiry);
    }
    pub(super) fn freeze_for(&mut self, j: usize, duration: f64, expiry: f64) {
        if self.entities[j].dash_travel() { return; }
        self.stun_target(j, duration);
        let e = &mut self.entities[j];
        e.freeze_expiry = e.freeze_expiry.max(expiry);
        if e.hidden || e.underground || e.spirit || e.stagger > 1e-9 {
            return;
        }
        if let Some(slow) = e
            .area_slows
            .iter_mut()
            .find(|s| s.1 == 0.0 && s.2 == 0.0 && s.3 == 0.0)
        {
            slow.0 = slow.0.max(duration);
        } else {
            e.area_slows.push((duration, 0.0, 0.0, 0.0));
        }
    }
    fn scope_periodic(
        &mut self,
        j: usize,
        source_id: i32,
        duration: f64,
        interval: f64,
        damage: f64,
    ) {
        let e = &mut self.entities[j];
        if e.hidden || e.underground || e.spirit || e.stagger > 1e-9 || damage <= 0.0 {
            return;
        }
        if let Some(buff) = e.periodic.iter_mut().find(|b| b.source_id == source_id) {
            buff.remaining = buff.remaining.max(duration);
            buff.damage = damage;
            buff.affects_hidden = false;
        } else {
            e.periodic.push(c56::Periodic {
                source_id,
                remaining: duration,
                interval,
                next_hit: interval,
                damage,
                hard: None,
                affects_hidden: false,
            });
        }
    }
    pub(super) fn scope_tick(&mut self, i: usize) {
        if self.entities[i].scope_skip_birth && self.entities[i].birth >= self.tick { return; }
        self.entities[i].effect_age += 0.05;
        let area = self.entities[i].clone();
        let mut effect = self.entities[i].scope.take().unwrap();
        match &mut effect {
            Effect::Container { delay, complete, child } => {
                if *complete { self.entities[i].alive = false; }
                else if area.effect_age + 1e-9 >= *delay {
                    self.scope_child(&area,child); *complete = true;
                }
            }
            Effect::StartAction { child } => {
                self.scope_child(&area,child); self.entities[i].alive = false;
            }
            Effect::Haste { delay, axes, refresh, cap, interval, once, applied,
                impact_applied, impact, damage, crown_damage, next_scan } => {
                if area.effect_age + 1e-9 >= *delay {
                    let active = area.effect_age - *delay;
                    if !*impact_applied {
                        if let Some(template) = impact { self.scope_child(&area,template); }
                        else if *damage > 0.0 {
                            for j in self.scope_targets(&area) {
                                let amount = if self.entities[j].king || self.entities[j].stats.name == "Tower" { *crown_damage } else { *damage };
                                self.damage(j,amount);
                            }
                        }
                        *impact_applied = true;
                    }
                    if *once {
                        if !*applied {
                            self.haste_scan(&area, if *cap { refresh.min((area.effect_duration-active).max(0.0)) } else { *refresh }, *axes);
                            *applied = true;
                        }
                    } else {
                        let step = interval.max(0.05);
                        let next = next_scan.get_or_insert(step);
                        while *next <= active.min(area.effect_duration)+1e-9 && *next < area.effect_duration-1e-9 {
                            self.haste_scan(&area,if *cap { refresh.min((area.effect_duration-*next).max(0.0)) } else { *refresh },*axes);
                            *next += step;
                        }
                    }
                    if active >= area.effect_duration-1e-9 { self.entities[i].alive = false; }
                }
            }
            Effect::Graveyard { interval, initial, deadlines, maximum, offsets,
                mirror_x, orient_y, spawned, next_spawn, radius } => {
                while *next_spawn <= area.effect_age.min(area.effect_duration) + 1e-9
                    && *spawned < *maximum {
                    let (mut dx, mut dy) = if offsets.is_empty() {
                        let angle = 2.0 * std::f64::consts::PI * *spawned as f64 / (*maximum).max(1) as f64;
                        (*radius * angle.cos(), *radius * angle.sin())
                    } else { offsets[*spawned % offsets.len()] };
                    if !offsets.is_empty() {
                        if *mirror_x && area.x > 9.0 { dx = -dx; }
                        if *orient_y && area.owner == 1 { dy = -dy; }
                        else if !*mirror_x && !*orient_y && area.owner == 1 { dx = -dx; dy = -dy; }
                    }
                    if let Some(template) = self.config.cards[&area.spell_name].spawns[area.owner as usize].first() {
                        let mut child = template.clone();
                        child.x = units((area.x + dx).clamp(0.25, 17.75)) as f64 / 1000.0;
                        child.y = units((area.y + dy).clamp(0.25, 31.75)) as f64 / 1000.0;
                        let (cx,cy) = cell(child.x,child.y);
                        child.lane = self.config.lane_ids[(cy*36+cx) as usize];
                        child.id = self.next_id as i32; self.next_id += 1;
                        child.birth = self.tick; self.entities.push(child);
                    }
                    *spawned += 1;
                    *next_spawn = deadlines.get(*spawned).copied().unwrap_or(*initial + *spawned as f64 * *interval);
                }
                if area.effect_age >= area.effect_duration - 1e-9 { self.entities[i].alive = false; }
            }
            Effect::SpawnDamage {
                damage,
                crown_damage,
                hits_air,
                hits_ground,
                damage_done,
                buff_done,
                buff_duration,
                axes,
            } => {
                if !*damage_done { for j in self.scope_targets(&area) {
                    let e = &self.entities[j];
                    if (e.airborne() && !*hits_air) || (!e.airborne() && !*hits_ground) {
                        continue;
                    }
                    let amount = if e.king || e.stats.name == "Tower" {
                        *crown_damage
                    } else {
                        *damage
                    };
                    self.damage(j, amount);
                } *damage_done = true; }
                if !*buff_done {
                    for j in self.scope_targets(&area) {
                        let e = &self.entities[j];
                        if (e.airborne() && !*hits_air) || (!e.airborne() && !*hits_ground) { continue; }
                        let duration = buff_duration.max(area.effect_duration.min(0.05));
                        if *axes == (0.0,0.0,0.0) { self.stun_target(j,duration); }
                        else { self.slow_target(j,duration,*axes); }
                    }
                    *buff_done = true;
                }
                if area.effect_age >= area.effect_duration - 1e-9 { self.entities[i].alive = false; }
            }
            Effect::Heal {
                heal_per_tick,
                heal_interval,
                recipients,
                snapshot_taken,
                ticks_done,
            } => {
                if !*snapshot_taken {
                    *snapshot_taken = true;
                    *recipients = self
                        .entities
                        .iter()
                        .filter(|e| {
                            e.class == "Troop"
                                && e.owner == area.owner
                                && e.alive
                                && !e.spirit
                                && Self::in_area(e, area.x, area.y, area.effect_radius)
                        })
                        .map(|e| e.id)
                        .collect();
                }
                let total = (area.effect_duration / *heal_interval)
                    .round_ties_even()
                    .max(1.0) as usize;
                while *ticks_done < total
                    && (*ticks_done + 1) as f64 * *heal_interval <= area.effect_age + 1e-9
                {
                    *ticks_done += 1;
                    for &id in recipients.iter() {
                        if let Some(j) = self.index(id).filter(|&j| self.entities[j].alive) {
                            let e = &mut self.entities[j];
                            e.hp = (e.hp + *heal_per_tick).min(e.stats.max_hp);
                        }
                    }
                }
                if *ticks_done >= total {
                    self.entities[i].alive = false;
                }
            }
            Effect::Curse {
                scan_interval,
                buff_time,
                damage,
                crown_damage,
                interval,
                next_scan,
                cursed,
            } => {
                let now = self.tick as f64 * 0.05;
                cursed.retain(|target| {
                    let body = self.index(target.id).map(|j| &self.entities[j]);
                    let corpse = body
                        .filter(|e| !e.alive)
                        .map(|e| (e.x, e.y, e.spirit))
                        .or(target.corpse);
                    if let Some((x, y, spirit)) = corpse {
                        if target.expiry + 0.05 + 1e-9 >= now && !spirit {
                            self.curse_spawn(&area, x, y);
                        }
                        false
                    } else {
                        target.expiry >= now - 1e-9
                    }
                });
                while *next_scan <= area.effect_age.min(area.effect_duration) + 1e-9 {
                    *next_scan += *scan_interval;
                    let expiry = now + *buff_time;
                    for j in self.scope_targets(&area) {
                        let e = &self.entities[j];
                        let (id, troop) = (e.id, e.class == "Troop");
                        let amount = if e.king || e.stats.name == "Tower" {
                            *crown_damage
                        } else {
                            *damage
                        };
                        self.scope_periodic(j, area.id, *buff_time, *interval, amount);
                        if troop {
                            if let Some(entry) = cursed.iter_mut().find(|v| v.id == id) {
                                entry.expiry = entry.expiry.max(expiry);
                            } else {
                                cursed.push(Cursed {
                                    id,
                                    expiry,
                                    corpse: None,
                                });
                            }
                        }
                    }
                }
                if area.effect_age >= area.effect_duration - 1e-9
                    && cursed.iter().all(|v| v.expiry < now - 1e-9)
                {
                    self.entities[i].alive = false;
                }
            }
            Effect::Void {
                pulse_times,
                hit_delay,
                tier_max_units,
                tier_damage,
                tier_crown_damage,
                pulses_done,
                pending,
            } => {
                while *pulses_done < pulse_times.len()
                    && pulse_times[*pulses_done] <= area.effect_age.min(area.effect_duration) + 1e-9
                {
                    let time = pulse_times[*pulses_done];
                    *pulses_done += 1;
                    let mut targets = self.scope_targets(&area);
                    if targets.is_empty() {
                        continue;
                    }
                    let tier = tier_max_units
                        .iter()
                        .position(|&limit| targets.len() <= limit)
                        .unwrap_or(tier_max_units.len());
                    targets.sort_by_key(|&j| self.entities[j].id);
                    for j in targets {
                        let e = &self.entities[j];
                        let amount = if e.king || e.stats.name == "Tower" {
                            tier_crown_damage[tier]
                        } else {
                            tier_damage[tier]
                        };
                        pending.push((time + *hit_delay, e.id, amount));
                    }
                }
                pending.retain(|&(time, id, amount)| {
                    if time <= area.effect_age + 1e-9 {
                        if let Some(j) = self
                            .index(id)
                            .filter(|&j| self.entities[j].alive && !self.entities[j].hidden)
                        {
                            self.damage(j, amount);
                        }
                        false
                    } else {
                        true
                    }
                });
                if area.effect_age >= area.effect_duration - 1e-9 && pending.is_empty() {
                    self.entities[i].alive = false;
                }
            }
            Effect::Vines {
                select_delay,
                action_delays,
                snare_duration,
                damage,
                crown_damage,
                interval,
                selected,
                pending,
                grounded,
            } => {
                if !*selected && area.effect_age >= *select_delay - 1e-9 {
                    *selected = true;
                    let mut targets = self.scope_targets(&area);
                    targets.sort_by(|&a, &b| {
                        let a = &self.entities[a];
                        let b = &self.entities[b];
                        (b.hp + b.shield)
                            .total_cmp(&(a.hp + a.shield))
                            .then(a.id.cmp(&b.id))
                    });
                    for (&delay, j) in action_delays.iter().zip(targets) {
                        pending.push((*select_delay + delay, self.entities[j].id));
                    }
                }
                while pending
                    .first()
                    .is_some_and(|v| v.0 <= area.effect_age + 1e-9)
                {
                    let (_, id) = pending.remove(0);
                    if let Some(j) = self.index(id).filter(|&j| self.entities[j].alive) {
                        let target = &mut self.entities[j];
                        if target.airborne() && target.stats.air {
                            target.grounded = true;
                            grounded.push((area.effect_age + *snare_duration, id));
                        }
                        let amount = if target.king || target.stats.name == "Tower" {
                            *crown_damage
                        } else {
                            *damage
                        };
                        self.freeze_for(
                            j,
                            *snare_duration,
                            self.tick as f64 * 0.05 + *snare_duration,
                        );
                        self.scope_periodic(j, area.id, *snare_duration, *interval, amount);
                    }
                }
                grounded.retain(|&(time, id)| {
                    if time <= area.effect_age + 1e-9 {
                        if let Some(j) = self.index(id) {
                            self.entities[j].grounded = false;
                        }
                        false
                    } else {
                        true
                    }
                });
                if *selected
                    && pending.is_empty()
                    && grounded.is_empty()
                    && area.effect_age >= area.effect_duration - 1e-9
                {
                    self.entities[i].alive = false;
                }
            }
        }
        self.entities[i].scope = Some(effect);
    }
}
