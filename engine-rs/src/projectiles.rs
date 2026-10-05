//! Fixed-endpoint child projectiles and recoil, following the Python oracle.
use super::*;

fn wide_roll_vector(direction: (i64,i64), work: i64) -> (i64,i64) {
    let (x,y) = (direction.0 as i128*1_000_000,direction.1 as i128*1_000_000);
    let square = x*x+y*y;
    let mut length = (square as f64).sqrt() as i128;
    while (length+1)*(length+1)<=square { length+=1; }
    while length*length>square { length-=1; }
    let length = length.max(1);
    ((x*work as i128/length) as i64,(y*work as i128/length) as i64)
}

impl BattleState {
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

    fn rolling_character_hits(&mut self, i: usize, radius: f64) {
        let shot = &self.entities[i];
        let victims: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j,e)| {
            (e.alive && e.owner!=shot.owner && !e.hidden && !e.spirit && !e.underground
                && e.stagger<=1e-9 && !e.above_surface() && e.death_immunity.is_none()
                && (e.class=="Troop" || e.class=="Building") && !shot.hit_ids.contains(&e.id)
                && Self::in_area(e,shot.x,shot.y,radius)).then_some(j)
        }).collect();
        let (damage,push,direction) = (shot.stats.damage,shot.stats.projectile_knockback,shot.roll_direction);
        for j in victims {
            let id = self.entities[j].id;
            self.entities[i].hit_ids.push(id);
            self.damage(j,damage);
            let center = (self.entities[j].x-direction.0 as f64/1000.0,self.entities[j].y-direction.1 as f64/1000.0);
            self.radial_knockback(j,center,push,false,false,None);
        }
    }

    pub(super) fn rolling_character_tick(&mut self, i: usize) {
        let e = &mut self.entities[i];
        e.effect_age += 0.05;
        let work = e.stats.speed.min(units(e.stats.projectile_range-e.traveled).max(0));
        let (dx,dy) = wide_roll_vector(e.roll_direction,work);
        e.x=(units(e.x)+dx) as f64/1000.0;e.y=(units(e.y)+dy) as f64/1000.0;
        e.traveled += work as f64/1000.0;
        let radius = e.stats.rolling_radius;
        let terminal = e.traveled >= e.stats.projectile_range-1e-9;
        self.rolling_character_hits(i,radius);
        if terminal {
            if self.entities[i].stats.projectile_radius>radius {
                self.rolling_character_hits(i,self.entities[i].stats.projectile_radius);
            }
            self.entities[i].alive=false;
        }
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
