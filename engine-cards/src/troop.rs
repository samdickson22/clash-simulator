//! Shared character heading, retained walking history and self-projectile mode.
use super::*;

impl Entity {
    /// entities.py Entity.face_towards: a quantized zero vector retains heading.
    pub(super) fn face_vector(&mut self, direction: (i64, i64)) {
        if direction != (0, 0) {
            self.facing = direction;
        }
    }

    pub(super) fn frozen_waypoint(&self) -> Option<(i64, i64)> {
        if self.stun > 0.0 && self.frozen_moving {
            self.route.front().copied().map(center)
        } else {
            None
        }
    }

    pub(super) fn face_waypoint(&mut self, waypoint: (i64, i64)) {
        self.face_vector((waypoint.0 - units(self.x), waypoint.1 - units(self.y)));
    }

    /// pathfinding.py advance_native_ground_route: consume at most one point,
    /// using the direction retained when that point became the route head.
    pub(super) fn advance_frozen_waypoint(&mut self, waypoint: (i64, i64)) {
        if self.route.front().copied().map(center) != Some(waypoint) {
            return;
        }
        let (dx, dy) = (waypoint.0 - units(self.x), waypoint.1 - units(self.y));
        if self.direction.0 * dx / 256 + self.direction.1 * dy / 256 < 1001 {
            self.route.pop_front();
            self.direction = self.route.front().map(|&cell| {
                let (x, y) = center(cell);
                norm(x - units(self.x), y - units(self.y), 256)
            }).unwrap_or((0, 0));
        }
    }

    /// Entity.finish_movement_tick after transport already consumed its vector
    /// (e.g. pushback). This does not reset charge, stun, or navigation history.
    pub(super) fn finish_frozen_route(&mut self) {
        if let Some(waypoint) = self.frozen_waypoint() {
            self.face_waypoint(waypoint);
            self.advance_frozen_waypoint(waypoint);
        }
    }

    /// IceSpiritFreeze.on_attack_start: the flight carrier changes kind and keeps its
    /// loaded clock. Its stats stay the character template (the exporter reports a
    /// launched carrier's mode stats as a character, differential.entity), so C56
    /// snapshots keep their pinned bytes; `spirit` marks the launch for readers.
    pub(super) fn launch_spirit(&mut self, tick: i64, target: Option<i32>, aim: (f64, f64)) {
        self.spirit = true;
        self.entity_kind = 2;
        self.spirit_launch = tick;
        self.shot_target = target;
        self.aim = aim;
    }

    /// on_combat_target_removed: an ordinary character reads its clock; after a Spirit
    /// launch supported(kind=2) is false and only an existing clock is consulted.
    pub(super) fn finish_started(&self) -> bool {
        let clocked = if self.spirit { self.clock_initialized } else { self.stats.ordinary };
        if clocked {
            self.clock.timeline > 0
        } else {
            self.started
        }
    }
}

impl BattleState {
    /// Entity.finish_movement_tick after special movement: face the retained
    /// point BEFORE consuming the external vector, advance its node AFTER it.
    pub(super) fn apply_external_and_finish_frozen_route(&mut self, i: usize, external: (i64, i64)) {
        let waypoint = self.entities[i].frozen_waypoint();
        if let Some(point) = waypoint {
            self.entities[i].face_waypoint(point);
        }
        self.apply_external(i, external);
        if let Some(point) = waypoint {
            self.entities[i].advance_frozen_waypoint(point);
        }
    }
}
