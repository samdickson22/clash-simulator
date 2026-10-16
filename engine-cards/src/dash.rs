//! Bandit wind-up, committed dash and damage-only landing immunity.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    minimum: f64,
    maximum: f64,
    windup: f64,
    speed: i64,
    damage: f64,
    tail: i64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    pub phase: String,
    #[serde(default)]
    wait: i64,
    target: Option<i32>,
    #[serde(default)]
    blocked: bool,
    #[serde(default)]
    goal: Option<(i64,i64)>,
    pub immunity: i64,
    consumed: bool,
}
impl Entity {
    pub(super) fn clock_projection_ms(&self) -> i64 {
        if self.force_due { 0 }
        else if self.clock.finish != 0 || self.clock.timeline == 0 {
            self.clock.remaining+self.clock.interval-self.clock.load
        } else { self.clock.interval-self.clock.timeline.rem_euclid(self.clock.interval) }
    }
    pub(super) fn consume_clock_reseed(&mut self) {
        let remaining=self.clock_reseed.take();
        if self.stats.ordinary { self.clock_initialized=true; }
        let Some(remaining)=remaining else {return;};
        let finish = self.clock.finish;
        self.clock.stop();self.force_due=remaining==0;
        let first=self.clock.interval-self.clock.load;
        if remaining>0 && remaining<first {
            self.clock.timeline=self.clock.interval-remaining;self.clock.remaining=0;
        } else { self.clock.remaining=self.clock.load.min((remaining-first).max(0)); }
        self.clock.finish=finish;
    }
    pub(super) fn cancel_dash_for_hook(&mut self) {
        if let Some(s)=&mut self.dash {
            s.phase="idle".into();s.wait=0;s.target=None;s.blocked=false;s.goal=None;s.immunity=0;s.consumed=false;
        }
    }
    pub(super) fn dash_active(&self) -> bool {
        self.dash.as_ref().is_some_and(|s| s.phase == "travel" || s.consumed)
    }
    pub(super) fn dash_travel(&self) -> bool {
        self.dash.as_ref().is_some_and(|s| s.phase == "travel")
    }
    /// An interrupting stun or an accepted displacement ends a stand (bandit.py `_cancel_charge`); the seen
    /// target and its block are kept.
    pub(super) fn dash_cancel(&mut self) {
        if let Some(s) = &mut self.dash {
            if s.phase == "standing" {
                s.phase = "idle".into(); s.wait = 0;
            }
        }
    }
}

/// Ported from RoyaleSim (MIT), move16402.rs `dash_half_step`/`tunnel_step` (bandit.py `dash_half_step`).
pub(super) fn dash_half_step(p: (i64,i64), goal: (i64,i64), len: i64) -> ((i64,i64), bool) {
    let (dx,dy) = (goal.0-p.0, goal.1-p.1);
    let d = isqrt(dx*dx+dy*dy);
    let dist = d.max(1);
    let step = len.max(0).min(dist);
    ((p.0 + (dx*256/dist)*step/256, p.1 + (dy*256/dist)*step/256), d <= len)
}

impl BattleState {
    /// Combat component: dash travel owns the frame (bandit.py `_special_move_active`).
    pub(super) fn dash_combat(&mut self, i: usize) -> bool {
        if self.entities[i].stats.dash.is_none() { return false; }
        let Some(s) = &mut self.entities[i].dash else { return false; };
        if s.consumed { s.consumed = false; return true; }
        s.phase == "travel"
    }
    /// Python native_tilemap.recover_native_ground_position (LogicBattle::cf44d8).
    pub(super) fn recover_ground(&self, x: i64, y: i64) -> (i64,i64) {
        let x = x.clamp(250, 17750);
        let y = y.clamp(250, 31750);
        if !self.config.water[(y / 500 * 36 + x / 500) as usize] { return (x,y); }
        let mut best = (x, y);
        let mut distance = 0x7FFF_FFFF_i64;
        for dy in (-2250i64..=2750).step_by(500) {
            let cy = y + dy;
            if !(0..32000).contains(&cy) { continue; }
            for dx in (-2250i64..=2750).step_by(500) {
                let cx = x + dx;
                if !(0..18000).contains(&cx) || self.config.water[(cy / 500 * 36 + cx / 500) as usize] { continue; }
                let d = dx.abs().max(dy.abs()) + ((53 * dx.abs().min(dy.abs())) >> 7);
                if d < distance { best = (cx, cy); distance = d; }
            }
        }
        best
    }
    /// Movement component (bandit.py `BanditDash.on_movement_tick`): first-sight stand, still entry and travel.
    /// Returns true when the dash owns this movement frame.
    pub(super) fn dash_movement(&mut self, i: usize, external: (i64,i64)) -> bool {
        let Some(spec) = self.entities[i].stats.dash.clone() else { return false; };
        let Some(mut state) = self.entities[i].dash.take() else { return false; };
        if state.phase == "travel" {
            self.dash_travel_step(i, &spec, &mut state);
            state.consumed = false;
            self.entities[i].dash = Some(state);
            self.entities[i].moving = false;
            self.apply_external_and_finish_frozen_route(i,external);
            return true;
        }
        if self.entities[i].stun > 0.0 {
            self.entities[i].dash = Some(state); return false;
        }
        let target = self.entities[i].target.and_then(|id| self.index(id)).filter(|&j| self.entities[j].alive);
        let (windup, finish) = (self.entities[i].windup, self.entities[i].clock.finish != 0);
        let mut hold = false;
        if state.phase == "idle" {
            if let Some(j) = target.filter(|_| !windup && !finish) {
                let (a,b) = (&self.entities[i], &self.entities[j]);
                let (dx,dy) = (units(b.x)-units(a.x),units(b.y)-units(a.y));
                let d2 = dx*dx+dy*dy;
                let near = units(spec.minimum)+units(a.stats.radius)+units(b.stats.radius);
                let reach = units(spec.maximum)+units(b.stats.radius);
                if state.target != Some(b.id) {
                    state.target = Some(b.id);
                    state.blocked = d2 < near*near;
                }
                if d2 <= reach*reach && !state.blocked {
                    state.phase = "standing".into();
                    state.wait = ((spec.windup as i64)/50).max(1)-1;
                    self.entities[i].dash = Some(state);
                    self.entities[i].moving = false;
                    self.apply_external_and_finish_frozen_route(i,external);
                    return true;
                }
            }
        } else if state.phase == "standing"
            && (target.is_none() || target.map(|j| self.entities[j].id) != state.target || windup || finish)
        {
            state.phase = "idle".into(); state.wait = 0;
        }
        if state.phase == "standing" {
            state.wait -= 1;
            if state.wait <= 0 {
                let j = target.unwrap();
                let (a,b) = (&self.entities[i], &self.entities[j]);
                let (ax,ay,tx,ty) = (units(a.x),units(a.y),units(b.x),units(b.y));
                let rr = units(a.stats.radius)+units(b.stats.radius);
                let (dx,dy) = (ax-tx, ay-ty);
                let n = isqrt(dx*dx+dy*dy);
                let (px,py) = if n == 0 { (tx,ty) } else { (tx+dx*rr/n, ty+dy*rr/n) };
                state.goal = Some((px.div_euclid(500)*500+250, py.div_euclid(500)*500+250));
                state.phase = "travel".into();
                state.wait = 0;
            }
            hold = true;
        }
        self.entities[i].dash = Some(state);
        if hold {
            self.entities[i].moving = false;
            self.apply_external_and_finish_frozen_route(i,external);
        }
        hold
    }
    fn dash_travel_step(&mut self, i: usize, spec: &Spec, state: &mut State) {
        let target = state.target.and_then(|id| self.index(id)).filter(|&j| self.entities[j].alive);
        let mut ended = target.is_none();
        let mut hit = None;
        if let (Some(j), Some(goal)) = (target, state.goal) {
            let reach = units(self.entities[i].stats.range)+units(self.entities[i].stats.radius)+units(self.entities[j].stats.radius);
            let (mut x, mut y) = (units(self.entities[i].x), units(self.entities[i].y));
            for _ in 0..2 {
                let ((nx,ny), arrived) = dash_half_step((x,y), goal, spec.speed/2);
                (x,y) = (nx,ny);
                let e = &mut self.entities[i];
                e.x = x as f64/1000.0; e.y = y as f64/1000.0;
                let (ex,ey) = (units(self.entities[j].x)-x, units(self.entities[j].y)-y);
                if ex*ex+ey*ey <= reach*reach { hit = Some(j); ended = true; break; }
                if arrived { ended = true; break; }
            }
        }
        if let Some(j) = hit {
            self.entities[i].dash = Some(state.clone());
            self.damage(j,spec.damage);
            self.character_hit_buff(i,j);
            self.entities[i].dash = None;
            let e = &mut self.entities[i];
            if e.stats.ordinary && e.clock_projection_ms()!=e.stats.interval {
                e.clock_reseed=Some(e.stats.interval);
            }
            e.cooldown = e.stats.interval as f64/1000.0;
        }
        if ended {
            let (x,y) = self.recover_ground(units(self.entities[i].x), units(self.entities[i].y));
            let e = &mut self.entities[i];
            e.x = x as f64/1000.0; e.y = y as f64/1000.0;
            state.phase = "idle".into(); state.wait = 0;
            state.target = None; state.blocked = false; state.goal = None;
            state.immunity = self.tick*50+spec.tail;
        }
    }
}
