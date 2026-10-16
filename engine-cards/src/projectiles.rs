//! Fixed-endpoint child projectiles and recoil, following the Python oracle.
use super::*;

const PI_Q40: i128 = 3_454_217_652_358;
const TRIG_ONE: i64 = 1 << 20;
/// Ported from RoyaleSim (MIT), fixed.rs `sin_pi_frac` (entities.py `sin_pi_frac`).
fn sin_pi_frac(num: i64, den: i64) -> i64 {
    let mut r = num.rem_euclid(2 * den);
    let negative = r >= den;
    if negative { r -= den; }
    if 2 * r > den { r = den - r; }
    let q: i128 = 1 << 40;
    let x = PI_Q40 * (r as i128) / (den as i128);
    let (mut sum, mut term) = (x, x);
    for k in 1..=6i128 {
        term = -((term * x / q) * x / q) / ((2 * k) * (2 * k + 1));
        sum += term;
    }
    let v = ((sum + (1 << 19)) >> 20) as i64;
    if negative { -v } else { v }
}

impl BattleState {
    pub(super) fn pingpong_waiting(&mut self, i: usize) -> bool {
        let Some(axe) = self.entities[i].pp_axe else { return false; };
        if self.index(axe).is_some_and(|k| self.entities[k].alive) { return true; }
        self.entities[i].pp_axe = None;
        false
    }
    /// Batch C1 (entities.py PingpongProjectile.update; RoyaleSim (MIT) combat.rs `step_straight`, `pingpong_pos`).
    pub(super) fn pingpong_tick(&mut self, i: usize) {
        let period = self.entities[i].stats.pingpong_period;
        self.entities[i].pp_t += 1;
        let t = self.entities[i].pp_t;
        if t > period { self.entities[i].alive = false; return; }
        if 2 * t > period && 2 * (t - 1) <= period { self.entities[i].hit_ids.clear(); }
        let shot = &self.entities[i];
        let (cx, cy, reach) = (units(shot.x), units(shot.y), shot.stats.pingpong_reach);
        let victims: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j, e)| {
            let r = reach + units(e.stats.radius);
            let (dx, dy) = (units(e.x) - cx, units(e.y) - cy);
            (e.alive && e.owner != shot.owner && !e.hidden && !e.spirit && !e.underground
                && (!shot.source_character || e.death_immunity.is_none())
                && !e.dash_travel() && !(e.stealth_until > self.tick * 50 && !e.stats.area_while_invisible)
                && e.stagger <= 1e-9 && (e.class == "Troop" || e.class == "Building")
                && (!e.airborne() || shot.stats.can_air) && !shot.hit_ids.contains(&e.id)
                && dx * dx + dy * dy <= r * r).then_some(j)
        }).collect();
        let damage = shot.stats.damage;
        for j in victims {
            let id = self.entities[j].id;
            self.entities[i].hit_ids.push(id);
            self.damage(j, damage);
        }
        let e = &mut self.entities[i];
        let tt = if 2 * t == period { t - 1 } else { t };
        let ((ox, oy), (ax, ay)) = (e.pp_origin.unwrap_or_default(), e.pp_apex.unwrap_or_default());
        let (ux, uy) = (ax - ox, ay - oy);
        let range = isqrt(ux * ux + uy * uy).max(1);
        let start = e.stats.pingpong_start;
        let d = start + (range - start) * sin_pi_frac(tt, period.max(1)) / TRIG_ONE;
        e.x = (ox + ux * d / range) as f64 / 1000.0;
        e.y = (oy + uy * d / range) as f64 / 1000.0;
    }

    pub(super) fn projectile_homing(&mut self, i: usize) -> bool {
        if self.entities[i].temporary_remaining <= 0 { return false; }
        let Some(id) = self.entities[i].temporary_target else {
            self.entities[i].temporary_remaining = 0;
            return true;
        };
        let target = self.index(id).map(|j| (self.entities[j].x,self.entities[j].y))
            .unwrap_or(self.entities[i].temporary_aim);
        let e = &mut self.entities[i];
        e.temporary_aim = target;
        e.aim = target;
        if e.stats.projectile_range > 0.0 {
            let (dx,dy) = norm(units(target.0)-units(e.x),units(target.1)-units(e.y),units(e.stats.projectile_range));
            e.aim = ((units(e.x)+dx) as f64/1000.0,(units(e.y)+dy) as f64/1000.0);
            e.stats.homing = Some(false);
        }
        e.temporary_remaining -= 50;
        true
    }

    /// Ported from RoyaleSim (MIT), combat.rs `straight_hits`: every enemy whose centre is within ProjectileRadius
    /// + its radius of the sample, once per shot; radial push from the sample (no combat interrupt, hit reset).
    pub(super) fn rolling_character_hits(&mut self, i: usize) {
        let shot = &self.entities[i];
        let (cx,cy,reach) = (units(shot.x),units(shot.y),units(shot.stats.rolling_radius));
        let victims: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j,e)| {
            let r = reach+units(e.stats.radius);
            let (dx,dy) = (units(e.x)-cx,units(e.y)-cy);
            // can_receive_area_damage: an effect-immune unit (dash travel) or a stealthed one is skipped
            // without being marked hit.
            (e.alive && e.owner!=shot.owner && !e.hidden && !e.spirit && !e.underground
                && e.stagger<=1e-9 && !e.above_surface() && e.death_immunity.is_none() && !e.dash_travel()
                && !(e.stealth_until > self.tick*50 && !e.stats.area_while_invisible)
                && (e.class=="Troop" || e.class=="Building") && !shot.hit_ids.contains(&e.id)
                && dx*dx+dy*dy <= r*r).then_some(j)
        }).collect();
        let (damage,push) = (shot.stats.damage,shot.stats.projectile_knockback);
        for j in victims {
            let id = self.entities[j].id;
            let center = (self.entities[i].x,self.entities[i].y);
            self.entities[i].hit_ids.push(id);
            self.damage(j,damage);
            self.radial_knockback(j,center,push,false,true,None);
        }
    }

    /// Ported from RoyaleSim (MIT), combat.rs `step_straight` + path.rs `advance_client`: step the speed toward the
    /// fixed endpoint (trunc0, nothing carried); the reaching step ends the shot without moving or testing.
    pub(super) fn rolling_character_tick(&mut self, i: usize) {
        if self.entities[i].birth == self.tick { return; }
        let e = &mut self.entities[i];
        e.effect_age += 0.05;
        let (dx,dy) = (units(e.aim.0)-units(e.x),units(e.aim.1)-units(e.y));
        let n = isqrt(dx*dx+dy*dy);
        let speed = e.stats.speed;
        if n <= speed { e.alive = false; return; }
        e.x=(units(e.x)+dx*speed/n) as f64/1000.0;e.y=(units(e.y)+dy*speed/n) as f64/1000.0;
        self.rolling_character_hits(i);
    }
    pub(super) fn projectile_status(&mut self, i: usize, j: usize) {
        let stats = &self.entities[i].stats;
        let (stun, duration, multiplier) = (stats.projectile_stun, stats.projectile_slow_duration, stats.projectile_slow_multiplier);
        self.stun_target(j, stun);
        self.slow_target(j, duration, (multiplier, multiplier, multiplier));
    }

    pub(super) fn projectile_splash_status(&mut self, i: usize) {
        let shot = &self.entities[i];
        if shot.stats.projectile_stun <= 0.0 && (shot.stats.projectile_slow_duration <= 0.0 || shot.stats.projectile_slow_multiplier >= 1.0) { return; }
        // entities.py:5721-5740 queries again after damage, including death children.
        let victims: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j,e)| {
            (e.alive && !e.hidden && !e.spirit && !e.underground && e.stagger <= 1e-9
                && e.owner != shot.owner && (!shot.source_character || e.death_immunity.is_none())
                && (e.class == "Troop" || e.class == "Building")
                && shot.can_hit_plane(e)
                && Self::in_area(e,shot.aim.0,shot.aim.1,shot.stats.projectile_radius)).then_some(j)
        }).collect();
        for j in victims { self.projectile_status(i,j); }
    }

    pub(super) fn vector_angle(&self, x: i64, y: i64) -> i64 {
        let atan = &self.config.atan;
        if x == 0 && y == 0 {
            return 0;
        }
        let (ax, ay) = (x.abs(), y.abs());
        if x > 0 && y >= 0 {
            if y < x {
                atan[(y * 128 / x) as usize]
            } else {
                90 - atan[(x * 128 / y) as usize]
            }
        } else if x <= 0 && y > 0 {
            if ax < y {
                90 + atan[(ax * 128 / y) as usize]
            } else {
                180 - atan[(y * 128 / ax) as usize]
            }
        } else if x < 0 && y <= 0 {
            if ay < ax {
                180 + atan[(ay * 128 / ax) as usize]
            } else {
                270 - atan[(ax * 128 / ay) as usize]
            }
        } else if ax < ay {
            270 + atan[(ax * 128 / ay) as usize]
        } else {
            (360 - atan[(ay * 128 / ax) as usize]) % 360
        }
    }

    pub(super) fn recoil(&mut self, i: usize, j: usize) {
        let (dx, dy) = (
            units(self.entities[i].x - self.entities[j].x),
            units(self.entities[i].y - self.entities[j].y),
        );
        let e = &mut self.entities[i];
        if e.push.is_some() || (dx == 0 && dy == 0) {
            return;
        }
        let amount = units(e.stats.recoil).min(10000);
        let (mx, my) = norm(dx, dy, amount);
        e.push = Some((
            (units(e.x) + mx) as f64 / 1000.0,
            (units(e.y) + my) as f64 / 1000.0,
        ));
        e.push_velocity = 0;
        let mut work = 0;
        while work < amount {
            e.push_velocity += 25;
            work += e.push_velocity;
        }
        e.push_preserve = true;
        e.push_reset = false;
        // Batch C1 (firecracker.py AttackRecoil): an armed recoil releases a LoadFirstHit unit's swing.
        if e.clock.refund != 0 {
            e.clock.stop();
            e.force_due = false;
        }
    }

    pub(super) fn projectile_children(&mut self, i: usize) {
        let source = self.entities[i].clone();
        if source.stats.child_damage <= 0.0 || source.stats.child_range <= 0 {
            return;
        }
        let angle = self.vector_angle(
            units(source.aim.0 - source.projectile_origin.0),
            units(source.aim.1 - source.projectile_origin.1),
        );
        for index in 0..source.stats.child_count {
            let spread = if source.stats.child_count > 1 {
                (index as i64 - source.stats.child_count as i64 / 2) * source.stats.child_spread
                    / source.stats.child_count as i64
            } else {
                0
            };
            let (dx, dy) = self.rotate(
                source.stats.child_range,
                0,
                (angle + spread).rem_euclid(360) as usize,
            );
            let mut child = source.clone();
            child.id = self.next_id as i32;
            self.next_id += 1;
            child.x = source.aim.0;
            child.y = source.aim.1;
            child.aim = (child.x + dx as f64 / 1000.0, child.y + dy as f64 / 1000.0);
            child.projectile_origin = (child.x, child.y);
            child.shot_target = None;
            child.source_character = false;
            child.piercing = true;
            child.stats.homing = Some(false);
            child.stats.damage = source.stats.child_damage;
            child.stats.speed = source.stats.child_speed;
            child.stats.projectile_radius = source.stats.child_radius;
            child.stats.child_count = 0;
            child.hit_ids.clear();
            child.birth = self.tick;
            let next = self.entities.len();
            self.entities.push(child);
            // Reserve the ID before the enlarged start sample can kill.
            if source.stats.child_extra > 0.0 {
                self.piercing_hits(next, source.stats.child_radius + source.stats.child_extra);
            }
        }
    }

    pub(super) fn piercing_hits(&mut self, i: usize, radius: f64) {
        let shot = &self.entities[i];
        let victims: Vec<usize> = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(j, e)| {
                (e.alive
                    && e.owner != shot.owner
                    && !e.hidden
                    && !e.spirit
                    && !e.underground
                    && (!shot.source_character || e.death_immunity.is_none())
                    && e.stagger <= 1e-9
                    && (e.class == "Troop" || e.class == "Building")
                    && (!e.airborne() || shot.stats.can_air)
                    && !shot.hit_ids.contains(&e.id)
                    && Self::in_area(e, shot.x, shot.y, radius))
                .then_some(j)
            })
            .collect();
        let damage = shot.stats.damage;
        for j in victims {
            let id = self.entities[j].id;
            self.entities[i].hit_ids.push(id);
            self.damage(j, damage);
        }
    }

    pub(super) fn piercing_tick(&mut self, i: usize) {
        self.projectile_homing(i);
        let e = &mut self.entities[i];
        let (dx, dy) = (units(e.aim.0 - e.x), units(e.aim.1 - e.y));
        let reached = isqrt(dx * dx + dy * dy) <= e.stats.speed;
        let (mx, my) = if reached {
            (dx, dy)
        } else {
            norm(dx, dy, e.stats.speed)
        };
        e.x = (units(e.x) + mx) as f64 / 1000.0;
        e.y = (units(e.y) + my) as f64 / 1000.0;
        let radius = e.stats.projectile_radius;
        self.piercing_hits(i, radius);
        if reached {
            self.entities[i].alive = false;
        }
    }
}
