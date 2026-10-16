//! Attached riders (Goblin Giant's Spear Goblins); mirrors py/src/clasher/mechanics/shared/riders.py.
//! Ported from RoyaleSim (MIT), state.rs `spawn_riders` / `carry_riders` / `dismount_point` /
//! `riders_die_with_their_mounts` and formation.rs `rider_arc_offset`.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub(super) struct RiderSpec {
    pub(super) number: i64,
    pub(super) radius: i64,
    pub(super) shift: i64,
    pub(super) max_angle: i64,
}

impl Entity {
    /// Outside every target, damage, effect and body query: a unit waiting for its spawn stagger, or an attached
    /// rider (its mount is cleared when the mount dies). Equal to the stagger test for every C56 entity.
    pub(super) fn absent(&self) -> bool {
        self.stagger > 1e-9 || self.mount.is_some()
    }
}

impl BattleState {
    /// formation.rs `rider_arc_offset` in this engine's integer trigonometry (riders.py rider_arc_offset_units).
    pub(super) fn rider_offset(&self, spec: &RiderSpec, facing: (i64, i64), rank: i64) -> (i64, i64) {
        let n = spec.number.max(1);
        let a = 180 + spec.shift + (n - 1 - rank) * spec.max_angle / n;
        let deg = (self.vector_angle(facing.0, facing.1) + a).rem_euclid(360) as usize;
        let (cos, sin) = self.config.rotations[deg];
        (cos * spec.radius / 1024, sin * spec.radius / 1024)
    }

    /// Each live mount's id and heading at the start of the tick (battle.py `mount_facings`).
    pub(super) fn mount_facings(&self) -> Vec<(i32, (i64, i64))> {
        self.entities.iter().filter(|e| e.alive && e.stats.riders.is_some()).map(|e| (e.id, e.facing)).collect()
    }

    /// rider.POSITION: after the combat phase, every rider onto its live mount (riders.py AttachedRiders.carry).
    pub(super) fn carry_riders(&mut self, facings: &[(i32, (i64, i64))]) {
        for &(mount, facing) in facings {
            let Some(m) = self.index(mount).filter(|&m| self.entities[m].alive) else { continue };
            let Some(spec) = self.entities[m].stats.riders.clone() else { continue };
            let (mx, my) = (units(self.entities[m].x), units(self.entities[m].y));
            let riders: Vec<usize> = (0..self.entities.len())
                .filter(|&r| self.entities[r].alive && self.entities[r].class == "Troop" && self.entities[r].mount == Some(mount))
                .collect();
            for r in riders {
                let (dx, dy) = self.rider_offset(&spec, facing, self.entities[r].rider_rank);
                self.entities[r].x = (mx + dx) as f64 / 1000.0;
                self.entities[r].y = (my + dy) as f64 / 1000.0;
            }
        }
    }

    /// rider.DIES_WITH_MOUNT / DISMOUNT_POINT (riders.py AttachedRiders.on_death).
    pub(super) fn dismount_riders(&mut self, source: &Entity) {
        let Some(spec) = source.stats.riders.clone() else { return };
        let riders: Vec<usize> = (0..self.entities.len())
            .filter(|&r| self.entities[r].alive && self.entities[r].class == "Troop" && self.entities[r].mount == Some(source.id))
            .collect();
        for r in riders {
            let (dx, dy) = self.rider_offset(&spec, source.facing, self.entities[r].rider_rank);
            let e = &mut self.entities[r];
            e.mount = None;
            e.x = (units(source.x) + dx) as f64 / 1000.0;
            e.y = (units(source.y) + dy) as f64 / 1000.0;
            let hp = e.hp;
            self.damage(r, hp);
        }
    }
}
