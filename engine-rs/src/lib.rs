//! Experimental pilot-card native engine. No Python callbacks in step or clone.
//! The differential gate, not this module's existence, determines admission.
mod astar;
mod attacks;
mod c56;
mod champions;
mod deployment;
mod dash;
mod leap;
mod hook;
mod clone;
mod clock;
mod leaf;
mod mt;
mod projectiles;
mod souls;
mod scope;
mod scripts;
mod spawn;

use clock::Clock;
use mt::Mt;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, VecDeque};
use std::sync::Arc;

fn one() -> f64 {
    1.0
}

fn units(x: f64) -> i64 {
    (x * 1000.0).round_ties_even() as i64
}
fn isqrt(n: i64) -> i64 {
    let mut r = (n as f64).sqrt() as i64;
    while (r + 1) * (r + 1) <= n {
        r += 1;
    }
    while r * r > n {
        r -= 1;
    }
    r
}
fn norm(dx: i64, dy: i64, amount: i64) -> (i64, i64) {
    let d = isqrt(dx * dx + dy * dy).max(1);
    (dx * amount / d, dy * amount / d)
}
fn cell(x: f64, y: f64) -> (i32, i32) {
    (
        (units(x) / 500).clamp(0, 35) as i32,
        (units(y) / 500).clamp(0, 63) as i32,
    )
}
fn center(c: (i32, i32)) -> (i64, i64) {
    (c.0 as i64 * 500 + 250, c.1 as i64 * 500 + 250)
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct Stats {
    #[serde(default)]
    payload_key: String,
    #[serde(default)]
    spawn_push: Option<(f64,f64,bool,bool)>,
    #[serde(default)]
    dash: Option<dash::Spec>,
    #[serde(default)]
    leap: Option<leap::Spec>,
    #[serde(default)]
    hook: Option<hook::Spec>,
    #[serde(default)]
    multi_attack: Option<attacks::Multi>,
    #[serde(default)]
    souls: Option<souls::Spec>,
    #[serde(default)]
    hit_buff: Option<attacks::Buff>,
    #[serde(default)]
    skip_deploy_snap: bool,
    #[serde(default)]
    break_on_building_hit: bool,
    #[serde(default)]
    death_spawn_radius: f64,
    #[serde(default)]
    death_spawn_angle: i64,
    #[serde(default)]
    death_spawn_const: bool,
    #[serde(default)]
    death_zero_count: usize,
    #[serde(default)]
    leaf_elixir_share: Option<f64>,
    #[serde(default)]
    projectile_stun: f64,
    #[serde(default)]
    projectile_slow_duration: f64,
    #[serde(default = "one")]
    projectile_slow_multiplier: f64,
    #[serde(default)]
    area_while_invisible: bool,
    #[serde(default)]
    spawner: Option<spawn::Spec>,
    #[serde(default)]
    collect_interval: f64,
    #[serde(default)]
    collect_amount: f64,
    #[serde(default)]
    collect_death: f64,
    #[serde(default)]
    crown_damage: Option<f64>,
    #[serde(default)]
    tunnel_speed: i64,
    #[serde(default)]
    tunnel_reached_from_speed: bool,
    #[serde(default)]
    tunnel_emergence: f64,
    #[serde(default)]
    ramp_stages: Vec<(i64, f64)>,
    #[serde(default)]
    ramp_approach: f64,
    name: String,
    #[serde(default)]
    hover: bool,
    #[serde(default)]
    ghost_fade: i64,
    #[serde(default)]
    ghost_range: bool,
    #[serde(default)]
    kamikaze: bool,
    #[serde(default)]
    kamikaze_delay: Option<f64>,
    #[serde(default)]
    projectile_air: Option<bool>,
    #[serde(default)]
    projectile_ground: Option<bool>,
    #[serde(default)]
    rolling: bool,
    #[serde(default)]
    projectile_knockback: f64,
    #[serde(default)]
    homing_time: i64,
    #[serde(default)]
    homing_min: f64,
    #[serde(default)]
    rolling_radius: f64,
    #[serde(default)]
    projectile_extra: f64,
    #[serde(default)]
    projectile_range: f64,
    #[serde(default)]
    recoil: f64,
    #[serde(default)]
    projectile_damage: Option<f64>,
    #[serde(default)]
    child_count: usize,
    #[serde(default)]
    child_damage: f64,
    #[serde(default)]
    child_speed: i64,
    #[serde(default)]
    child_radius: f64,
    #[serde(default)]
    child_range: i64,
    #[serde(default)]
    child_spread: i64,
    #[serde(default)]
    child_extra: f64,
    #[serde(default)]
    air: bool,
    #[serde(default)]
    electro_chain: bool,
    #[serde(default)]
    dragon_chain: bool,
    #[serde(default)]
    chain_range: f64,
    #[serde(default)]
    chain_count: usize,
    #[serde(default)]
    chain_interval: f64,
    #[serde(default)]
    ordinary: bool,
    #[serde(default)]
    finish_allowed: Option<bool>,
    #[serde(default)]
    can_air: bool,
    #[serde(default)]
    can_ground: Option<bool>,
    #[serde(default)]
    jump_speed: i64,
    #[serde(default)]
    charge_range: i64,
    #[serde(default)]
    charge_speed: i64,
    #[serde(default)]
    special_damage: f64,
    #[serde(default)]
    death_damage: f64,
    #[serde(default)]
    death_radius: f64,
    #[serde(default)]
    death_knockback: f64,
    #[serde(default)]
    spirit_speed: i64,
    #[serde(default)]
    spirit_radius: f64,
    #[serde(default)]
    spirit_stun: f64,
    #[serde(default)]
    area_radius: f64,
    #[serde(default)]
    self_area: bool,
    #[serde(default)]
    knockback_immune: bool,
    #[serde(default)]
    hide_ms: i64,
    #[serde(default)]
    rise_ms: i64,
    #[serde(default)]
    lifetime: i64,
    #[serde(default)]
    max_hp: f64,
    radius: f64,
    mass: f64,
    range: f64,
    sight: f64,
    speed: i64,
    damage: f64,
    interval: i64,
    load: i64,
    projectile_speed: i64,
    #[serde(default)]
    projectile_radius: f64,
    #[serde(default)]
    homing: Option<bool>,
    only_buildings: bool,
    stop_ms: i64,
    wait_ms: i64,
    sight_back: f64,
    sight_side: f64,
    first: f64,
    #[serde(default)]
    retarget: Option<f64>,
    muzzle: f64,
    muzzle_y: f64,
    activation: f64,
    activation_hit: f64,
    distance_discount: f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct FrozenStopRoute {
    target_id: i32,
    route: VecDeque<(i32, i32)>,
    goal: Option<(i32, i32)>,
    occupied: Arc<Vec<usize>>,
    direction: Option<(i64, i64)>,
    position: (f64, f64),
    cell: (i32, i32),
    frozen: bool,
    reacquired: bool,
    resumable: bool,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
struct Entity {
    #[serde(default)]
    clone_template: Option<Arc<Entity>>,
    #[serde(default)]
    spawn_push_done: bool,
    #[serde(default)]
    clock_reseed: Option<i64>,
    #[serde(default)]
    clock_initialized: bool,
    #[serde(default)]
    dash: Option<dash::State>,
    #[serde(default)]
    leap: Option<leap::State>,
    #[serde(default)]
    hook: Option<hook::State>,
    #[serde(default)]
    forced_active: bool,
    #[serde(default)]
    kamikaze_primed: bool,
    #[serde(default)]
    kamikaze_timer: f64,
    #[serde(default)]
    roll_direction: (i64,i64),
    #[serde(default)]
    temporary_remaining: i64,
    #[serde(default)]
    temporary_target: Option<i32>,
    #[serde(default)]
    temporary_aim: (f64,f64),
    #[serde(default)]
    souls_collected: i64,
    #[serde(default)]
    scope_skip_birth: bool,
    #[serde(default)]
    freeze_carrier: bool,
    #[serde(default)]
    entity_kind: i32,
    #[serde(default)]
    freeze_pause: f64,
    #[serde(default)]
    champion: Option<champions::Champion>,
    #[serde(default)]
    is_clone: bool,
    #[serde(default = "one")]
    move_mode: f64,
    #[serde(default = "one")]
    attack_mode: f64,
    #[serde(default)]
    production: Option<spawn::State>,
    #[serde(default)]
    spawn_area_done: bool,
    #[serde(default)]
    collect_elapsed: f64,
    #[serde(default)]
    scope: Option<scope::Effect>,
    #[serde(default)]
    grounded: bool,
    #[serde(default)]
    freeze_expiry: f64,
    #[serde(default)]
    source_character: bool,
    #[serde(default)]
    underground: bool,
    #[serde(default)]
    tunnel_origin: (f64, f64),
    #[serde(default)]
    tunnel_destination: (f64, f64),
    #[serde(default)]
    tunnel_duration: f64,
    #[serde(default)]
    tunnel_total: f64,
    #[serde(default)]
    placement_radius: Option<f64>,
    #[serde(default)]
    ramp_target: Option<i32>,
    #[serde(default)]
    ramp_time: f64,
    #[serde(default)]
    death_immunity: Option<i64>,
    #[serde(default)]
    death_travel: Option<(f64, f64)>,
    #[serde(default)]
    death_ticks: i64,
    #[serde(default)]
    stealth_until: i64,
    #[serde(default)]
    ghost_time: f64,
    #[serde(default)]
    piercing: bool,
    #[serde(default)]
    projectile_origin: (f64, f64),
    #[serde(default)]
    bomb_timer: f64,
    #[serde(default)]
    bomb_knockback: f64,
    #[serde(default)]
    bomb_ignores_mass: bool,
    #[serde(default)]
    bomb_damage: f64,
    #[serde(default)]
    bomb_radius: f64,
    #[serde(default)]
    chain_origin: (f64, f64),
    #[serde(default)]
    chain_remaining: usize,
    #[serde(default)]
    chain_time: f64,
    #[serde(default)]
    controlled_vector: (i64, i64, i64),
    #[serde(default)]
    controlled_bypass: bool,
    #[serde(default)]
    area_slows: Vec<(f64, f64, f64, f64)>,
    #[serde(default)]
    hastes: Vec<(f64, f64, f64, f64)>,
    #[serde(default)]
    periodic: Vec<c56::Periodic>,
    #[serde(default)]
    damage_ticks: usize,
    #[serde(default)]
    next_damage: Option<f64>,
    #[serde(default)]
    next_effect: Option<f64>,
    id: i32,
    owner: i32,
    x: f64,
    y: f64,
    hp: f64,
    alive: bool,
    class: String,
    target: Option<i32>,
    #[serde(default)]
    last_target: Option<i32>,
    #[serde(default)]
    preload_blocked: bool,
    stats: Stats,
    deploy: f64,
    stagger: f64,
    king: bool,
    active: bool,
    lane: i32,
    #[serde(default)]
    age: i64,
    #[serde(default)]
    decay_work: i64,
    #[serde(default)]
    hide_phase: i64,
    #[serde(default)]
    hidden: bool,
    #[serde(default)]
    finish_tick: i64,
    #[serde(default)]
    stun: f64,
    #[serde(default)]
    frozen_moving: bool,
    #[serde(default)]
    spell_name: String,
    #[serde(default)]
    launch_delay: f64,
    #[serde(default)]
    damage_group: Option<i32>,
    #[serde(default)]
    strikes_elapsed: usize,
    #[serde(default)]
    push: Option<(f64, f64)>,
    #[serde(default)]
    push_velocity: i64,
    #[serde(default)]
    push_reset: bool,
    #[serde(default)]
    push_tick: i64,
    #[serde(default)]
    nav_target: Option<i32>,
    #[serde(default)]
    jump: Option<(f64, f64)>,
    #[serde(default)]
    landed_tick: i64,
    #[serde(default)]
    charge: i64,
    #[serde(default)]
    public_speed_base: Option<f64>,
    #[serde(default)]
    force_due: bool,
    #[serde(default)]
    shield: f64,
    #[serde(default)]
    spirit: bool,
    #[serde(default)]
    spirit_launch: i64,
    #[serde(default)]
    slow_ms: i64,
    #[serde(default)]
    effect_duration: f64,
    #[serde(default)]
    effect_radius: f64,
    #[serde(default)]
    effect_slow_ms: i64,
    #[serde(default)]
    effect_multiplier: f64,
    #[serde(default)]
    effect_applied: bool,
    #[serde(default)]
    push_preserve: bool,
    #[serde(default)]
    effect_age: f64,
    #[serde(default)]
    traveled: f64,
    #[serde(default)]
    hit_ids: Vec<i32>,
    #[serde(default)]
    clock: Clock,
    #[serde(default)]
    route: VecDeque<(i32, i32)>,
    #[serde(default)]
    goal: Option<(i32, i32)>,
    #[serde(default)]
    route_occupied: Arc<Vec<usize>>,
    #[serde(default)]
    route_friendly: Vec<i32>,
    #[serde(default)]
    route_backwards: bool,
    #[serde(default)]
    frozen_stop: Option<FrozenStopRoute>,
    #[serde(default)]
    direction: (i64, i64),
    #[serde(default)]
    move_target: Option<i32>,
    #[serde(default)]
    moving: bool,
    #[serde(default)]
    move_clock: i64,
    #[serde(default)]
    cooldown: f64,
    #[serde(default)]
    birth: i64,
    #[serde(default)]
    shot_target: Option<i32>,
    #[serde(default)]
    aim: (f64, f64),
    #[serde(default)]
    facing: (i64, i64),
    #[serde(default)]
    avoidance: i64,
    #[serde(default)]
    started: bool,
    #[serde(default)]
    windup: bool,
    #[serde(default)]
    activation_remaining: f64,
    #[serde(default)]
    activation_hit_remaining: f64,
    #[serde(default)]
    pending_ms: i64,
    #[serde(default)]
    pending_lethal: bool,
    #[serde(default)]
    attacked_current: bool,
    #[serde(default)]
    resume_pending: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Player {
    #[serde(default)]
    last_card: Option<String>,
    #[serde(default)]
    last_cost: Option<f64>,
    elixir: f64,
    hand: Vec<Option<String>>,
    cycle: VecDeque<String>,
    refill: i64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Spell {
    name: String,
    radius: f64,
    damage: f64,
    #[serde(default)]
    stun_duration: f64,
    #[serde(default)]
    slow_duration: f64,
    #[serde(default = "one")]
    slow_multiplier: f64,
    #[serde(default)]
    freeze_effect: bool,
    crown_tower_damage: Option<f64>,
    crown_tower_damage_multiplier: f64,
    #[serde(default)]
    affects_hidden: bool,
    #[serde(default)]
    travel_speed: f64,
    #[serde(default)]
    requires_territory: bool,
    #[serde(default)]
    casting_speed: f64,
    #[serde(default)]
    casting_min_distance: f64,
    #[serde(default)]
    projectile_range: f64,
    #[serde(default)]
    radius_y: f64,
    #[serde(default)]
    knockback_distance: f64,
    #[serde(default)]
    knockback_ignores_mass: bool,
    #[serde(default)]
    multiple_projectiles: Option<usize>,
    #[serde(default)]
    damage_waves: Option<usize>,
    #[serde(default)]
    damage_wave_interval: f64,
    #[serde(default)]
    spread_radius: f64,
    #[serde(default)]
    projectile_pattern: String,
    #[serde(default)]
    max_targets: usize,
    #[serde(default)]
    strike_interval: f64,
    #[serde(default)]
    impact_delay: f64,
    #[serde(default)]
    ignore_buildings: bool,
    #[serde(default)]
    building_damage: Option<f64>,
    #[serde(default)]
    hits_air: Option<bool>,
    #[serde(default)]
    speed_multiplier: Option<f64>,
    #[serde(default)]
    slows_attack_speed: Option<bool>,
    #[serde(default)]
    slow_refresh_duration: f64,
    #[serde(default)]
    effect_tick_interval: f64,
    #[serde(default)]
    cap_buff_time_to_effect: bool,
    #[serde(default)]
    target_local_damage: bool,
    #[serde(default)]
    periodic_damage_buff_duration: f64,
    #[serde(default)]
    damage_tick_interval: f64,
    #[serde(default)]
    initial_damage_delay: Option<f64>,
    #[serde(default)]
    max_damage_ticks: usize,
    #[serde(default)]
    periodic_damage_controlled_by_parent: bool,
    #[serde(default)]
    attract_percentage: f64,
    #[serde(default)]
    push_speed_factor: f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Cast {
    player: usize,
    name: String,
    x: f64,
    y: f64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Card {
    #[serde(default)]
    mirror: bool,
    #[serde(default)]
    recruits_line: bool,
    #[serde(default)]
    anywhere: bool,
    cost: f64,
    #[serde(default)]
    margin: i64,
    #[serde(default)]
    mirror_x: Option<bool>,
    #[serde(default)]
    spawns: [Vec<Entity>; 2],
    #[serde(default)]
    chain: Option<Entity>,
    #[serde(default)]
    anchors: Vec<(f64, f64)>,
    #[serde(default)]
    footprint: i64,
    #[serde(default)]
    spell: Option<Spell>,
    units: [Vec<Entity>; 2],
}
#[derive(Clone, Debug, Deserialize, Serialize)]
struct Config {
    #[serde(default)]
    atan: Vec<i64>,
    #[serde(default)]
    rotations: Vec<(i64, i64)>,
    costs: Vec<i64>,
    water: Vec<bool>,
    cards: BTreeMap<String, Card>,
    blocked_tiles: Vec<bool>,
    spawn_clear: Vec<bool>,
    walkable: Vec<bool>,
    #[serde(default)]
    death_areas: BTreeMap<String, Entity>,
    #[serde(default)]
    death_objects: BTreeMap<String, Entity>,
    #[serde(default)]
    death_children: BTreeMap<String, Vec<Entity>>,
    #[serde(default)]
    bomb_children: BTreeMap<String, Vec<Entity>>,
    #[serde(default)]
    spirit_areas: BTreeMap<String, Entity>,
    #[serde(default)]
    production_children: BTreeMap<String, Entity>,
    #[serde(default)]
    spawn_areas: BTreeMap<String, Entity>,
    #[serde(default)]
    soul_skeletons: Vec<Vec<Vec<Entity>>>,
    #[serde(default)]
    soul_offsets: Vec<Vec<(f64, f64)>>,
    #[serde(default)]
    ability_bombs: BTreeMap<String, Entity>,
    #[serde(default)]
    lane_ids: Vec<i32>,
}

#[pyclass(module = "clasher_core")]
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct BattleState {
    #[serde(default)]
    placement_signature: Vec<i32>,
    #[serde(default)]
    placement_masks: BTreeMap<i64, Vec<bool>>,
    #[serde(default)]
    champion_owners: Vec<(i32, String, i32)>,
    tick: i64,
    next_id: i64,
    players: [Player; 2],
    entities: Vec<Entity>,
    rng: Mt,
    game_over: bool,
    winner: Option<i32>,
    #[serde(default)]
    sudden_death: bool,
    config: Arc<Config>,
    #[serde(default)]
    pending_casts: Vec<Cast>,
}

fn distance(a: &Entity, b: &Entity) -> f64 {
    ((a.x - b.x).powi(2) + (a.y - b.y).powi(2) - b.stats.distance_discount / 1_000_000.0)
        .max(0.0)
        .sqrt()
}
fn reach(a: &Entity, b: &Entity, extra: f64) -> bool {
    distance(a, b) <= a.stats.range + a.stats.radius + b.stats.radius + extra + 1e-9
}
fn engagement_radius(a: &Entity, b: &Entity) -> f64 {
    (a.stats.range + a.stats.radius
        - if a.ramp_target != Some(b.id) {
            a.stats.ramp_approach
        } else {
            0.0
        })
    .max(0.0)
}
fn engagement_reach(a: &Entity, b: &Entity) -> bool {
    distance(a, b) <= engagement_radius(a, b) + b.stats.radius + 1e-9
}
fn started_projectile(a: &Entity) -> bool {
    let phase = if !a.stats.ordinary {
        (-units(a.cooldown.max(0.0))).rem_euclid(a.stats.interval)
    } else {
        a.clock.timeline % a.stats.interval
    };
    a.stats.projectile_speed > 0 && a.started && phase > 50
}
fn keep_reach(a: &Entity, b: &Entity) -> bool {
    let extra = if started_projectile(a) {
        0.5
    } else if a.class == "Troop" {
        0.025
    } else {
        0.0
    };
    reach(a, b, extra)
}
fn sight(a: &Entity, b: &Entity) -> bool {
    let r = a.stats.sight
        + a.stats.radius
        + b.stats.radius
        + if b.king || b.stats.name == "Tower" {
            2.0
        } else {
            0.0
        };
    if distance(a, b) > r + 1e-9 {
        return false;
    }
    if a.king || b.king || a.stats.name == "Tower" || b.stats.name == "Tower" {
        return true;
    }
    if a.stats.sight_side > 0.0 && (a.x - b.x).abs() > (r - a.stats.sight_side).max(0.0) + 1e-9 {
        return false;
    }
    let behind = if a.owner == 0 { a.y - b.y } else { b.y - a.y };
    !(a.stats.sight_back > 0.0 && behind > (r - a.stats.sight_back).max(0.0) + 1e-9)
}

impl Stats {
    fn key(&self) -> &str {
        if self.payload_key.is_empty() { &self.name } else { &self.payload_key }
    }
}

impl BattleState {
    fn in_area(e: &Entity, x: f64, y: f64, radius: f64) -> bool {
        let (x, y, r) = (units(x), units(y), units(radius));
        let (ex, ey, er) = (units(e.x), units(e.y), units(e.stats.radius));
        if e.class == "Building" {
            let dx = x.clamp(ex - er, ex + er) - x;
            let dy = y.clamp(ey - er, ey + er) - y;
            dx * dx + dy * dy < r * r
        } else {
            (ex - x).pow(2) + (ey - y).pow(2) < (r + er).pow(2)
        }
    }
    fn direct_spell(&mut self, cast: &Cast, spell: &Spell, origin: Option<(f64, f64)>) {
        self.grouped_spell(cast, spell, origin, None);
    }
    fn grouped_spell(
        &mut self,
        cast: &Cast,
        spell: &Spell,
        origin: Option<(f64, f64)>,
        group: Option<i32>,
    ) {
        let previous = group
            .and_then(|g| self.entities.iter().find(|e| e.damage_group == Some(g)))
            .map(|e| e.hit_ids.clone())
            .unwrap_or_default();
        let targets: Vec<usize> = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(i, e)| {
                (e.alive
                    && !previous.contains(&e.id)
                    && !(spell.ignore_buildings && e.class == "Building")
                    && !e.spirit
                    && !e.underground
                    && e.stagger <= 1e-9
                    && e.owner != cast.player as i32
                    && (e.class == "Troop" || e.class == "Building")
                    && (!e.hidden || spell.affects_hidden)
                    && Self::in_area(e, cast.x, cast.y, spell.radius))
                .then_some(i)
            })
            .collect();
        if let Some(g) = group {
            let ids: Vec<i32> = targets.iter().map(|&i| self.entities[i].id).collect();
            for e in &mut self.entities {
                if e.damage_group == Some(g) {
                    e.hit_ids.extend(&ids);
                }
            }
        }
        for &i in &targets {
            self.spell_hit(i, cast, spell, origin);
        }
        if spell.stun_duration > 0.0 || (spell.slow_duration > 0.0 && spell.slow_multiplier < 1.0) {
            // Status admission is a fresh query after synchronous death payloads.
            let status_targets: Vec<usize> = self
                .entities
                .iter()
                .enumerate()
                .filter_map(|(i, e)| {
                    (e.alive
                        && e.owner != cast.player as i32
                        && (e.class == "Troop" || e.class == "Building")
                        && !e.hidden
                        && !e.spirit
                        && !e.underground
                        && e.stagger <= 1e-9
                        && Self::in_area(e, cast.x, cast.y, spell.radius))
                    .then_some(i)
                })
                .collect();
            for i in status_targets {
                self.stun_target(i, spell.stun_duration);
                self.slow_target(i, spell.slow_duration, (spell.slow_multiplier, spell.slow_multiplier, spell.slow_multiplier));
            }
        }
    }
    fn spell_hit(&mut self, i: usize, cast: &Cast, spell: &Spell, origin: Option<(f64, f64)>) {
        let e = &self.entities[i];
        let damage = if e.king || e.stats.name == "Tower" {
            spell
                .crown_tower_damage
                .unwrap_or((spell.damage * spell.crown_tower_damage_multiplier).floor())
        } else {
            spell.damage
        };
        self.damage(i, damage);
        self.radial_knockback(
            i,
            (cast.x, cast.y),
            spell.knockback_distance,
            spell.knockback_ignores_mass,
            spell.requires_territory,
            origin,
        );
    }
    fn radial_knockback(
        &mut self,
        i: usize,
        center: (f64, f64),
        push_distance: f64,
        ignores_mass: bool,
        territory: bool,
        origin: Option<(f64, f64)>,
    ) {
        let e = &mut self.entities[i];
        if e.alive
            && !e.underground
            && e.class == "Troop"
            && push_distance > 0.0
            && (!e.stats.knockback_immune || ignores_mass)
            && e.push.is_none()
            && !e.dash_travel()
        {
            e.dash_cancel();
            e.leap_cancel();
            let (mut dx, mut dy) = (units(e.x - center.0), units(e.y - center.1));
            if dx == 0 && dy == 0 {
                if let Some((ox, oy)) = origin {
                    dx = ((center.0 - ox) * 1_000_000.0).round_ties_even() as i64;
                    dy = ((center.1 - oy) * 1_000_000.0).round_ties_even() as i64;
                }
                if dx == 0 && dy == 0 {
                    dx = if e.owner == 0 { 1 } else { -1 };
                }
            }
            let distance = units(push_distance).min(10000);
            let (mx, my) = norm(dx, dy, distance);
            e.push = Some((
                (units(e.x) + mx) as f64 / 1000.0,
                (units(e.y) + my) as f64 / 1000.0,
            ));
            let mut work = 0;
            e.push_velocity = 0;
            while work < distance {
                e.push_velocity += 25;
                work += e.push_velocity;
            }
            e.push_reset = e.stats.ordinary || territory;
            e.push_preserve = territory;
            if !e.push_preserve && !e.stats.ordinary && e.charge < 10000 {
                e.cooldown = e.cooldown.max(e.stats.interval as f64 / 1000.0);
                e.preload_blocked = true;
                e.clock.finish = 0;
                e.windup = false;
                e.started = false;
            }
            if !e.push_preserve && e.charge >= 10000 {
                e.charge = 0;
                e.public_speed_base = Some(e.stats.speed as f64);
                e.force_due = false;
                e.clock.stop();
                e.clock.remaining = 0;
                e.windup = false;
                e.started = false;
            }
            if !e.stats.ramp_stages.is_empty() {
                e.reset_ramp();
                e.target = None;
            }
        }
    }
    fn spirit_tick(&mut self, i: usize) {
        if let Some(j) = self.entities[i].shot_target.and_then(|id| self.index(id)) {
            self.entities[i].aim = (self.entities[j].x, self.entities[j].y);
        }
        let e = &mut self.entities[i];
        let (dx, dy) = (units(e.aim.0 - e.x), units(e.aim.1 - e.y));
        let remaining = isqrt(dx * dx + dy * dy);
        let speed = e.stats.spirit_speed;
        let (mx, my) = if speed >= remaining {
            (dx, dy)
        } else {
            norm(dx, dy, speed)
        };
        e.x = (units(e.x) + mx) as f64 / 1000.0;
        e.y = (units(e.y) + my) as f64 / 1000.0;
        if remaining > speed {
            return;
        }
        let source = e.clone();
        if source.stats.electro_chain {
            self.electro_land(i, &source);
            return;
        }
        let victims: Vec<usize> = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(j, e)| {
                (e.alive
                    && !e.spirit
                    && !e.underground
                    && !e.hidden
                    && e.stagger <= 1e-9
                    && e.owner != source.owner
                    && (e.class == "Troop" || e.class == "Building")
                    && source.can_hit_plane(e)
                    && Self::in_area(e, source.x, source.y, source.stats.spirit_radius))
                .then_some(j)
            })
            .collect();
        for &j in &victims {
            self.damage(j, source.stats.damage);
        }
        if source.stats.spirit_stun > 0.0 {
            let status: Vec<usize> = self
                .entities
                .iter()
                .enumerate()
                .filter_map(|(j, e)| {
                    (e.alive
                        && !e.spirit
                        && !e.underground
                        && !e.hidden
                        && e.stagger <= 1e-9
                        && e.owner != source.owner
                        && (e.class == "Troop" || e.class == "Building")
                        && source.can_hit_plane(e)
                        && Self::in_area(e, source.x, source.y, source.stats.spirit_radius))
                    .then_some(j)
                })
                .collect();
            for j in status {
                self.stun_target_mode(j, source.stats.spirit_stun, false);
            }
        }
        if let Some(template) = self.config.spirit_areas.get(source.stats.key()) {
            let mut area = template.clone();
            area.id = self.next_id as i32;
            self.next_id += 1;
            area.owner = source.owner;
            area.x = source.x;
            area.y = source.y;
            area.birth = self.tick;
            self.entities.push(area);
        }
        self.entities[i].alive = false;
        self.entities[i].hp = 0.0;
    }
    fn area_tick(&mut self, i: usize) {
        if self.entities[i].birth >= self.tick {
            return;
        }
        self.entities[i].effect_age += 0.05;
        if !self.entities[i].effect_applied {
            self.entities[i].effect_applied = true;
            let effect = self.entities[i].clone();
            for e in &mut self.entities {
                if e.alive
                    && !e.spirit
                    && !e.underground
                    && e.owner != effect.owner
                    && (e.class == "Troop" || e.class == "Building")
                    && e.stagger <= 1e-9
                    && Self::in_area(e, effect.x, effect.y, effect.effect_radius)
                {
                    e.slow_ms = e.slow_ms.max(effect.effect_slow_ms);
                }
            }
        }
        if self.entities[i].effect_age >= self.entities[i].effect_duration - 1e-9 {
            self.entities[i].alive = false;
        }
    }
    fn rolling_tick(&mut self, i: usize) {
        let name = self.entities[i].spell_name.clone();
        let spell = self.config.cards[&name].spell.clone().unwrap();
        let e = &mut self.entities[i];
        let before = e.effect_age;
        e.effect_age += 0.05;
        let delay = spell.casting_min_distance / spell.casting_speed;
        if before + 1e-9 < delay {
            if e.effect_age + 1e-9 < delay {
                return;
            }
        } else {
            let movement = e
                .stats
                .speed
                .min(units(spell.projectile_range - e.traveled).max(0));
            e.traveled += movement as f64 / 1000.0;
            e.y = (units(e.y) + movement * if e.owner == 0 { 1 } else { -1 }) as f64 / 1000.0;
        }
        let cast = Cast {
            player: e.owner as usize,
            name,
            x: e.x,
            y: e.y,
        };
        let (cx, cy, rx, ry) = (
            units(e.x),
            units(e.y),
            units(spell.radius),
            units(spell.radius_y),
        );
        for j in 0..self.entities.len() {
            let target = &self.entities[j];
            if !target.alive
                || target.owner == cast.player as i32
                || !(target.class == "Troop" || target.class == "Building")
                || self.entities[i].hit_ids.contains(&target.id)
            {
                continue;
            }
            let (x, y, r) = (units(target.x), units(target.y), units(target.stats.radius));
            let overlap = if target.class == "Building" {
                x + r >= cx - rx && y + r >= cy - ry && x - r < cx + rx && y - r < cy + ry
            } else {
                let dx = x - x.clamp(cx - rx, cx + rx);
                let dy = y - y.clamp(cy - ry, cy + ry);
                dx * dx + dy * dy < r * r
            };
            if !overlap {
                continue;
            }
            let id = target.id;
            if target.stagger > 1e-9 {
                self.entities[i].hit_ids.push(id);
                continue;
            }
            if target.hidden || target.spirit || target.above_surface() {
                continue;
            }
            self.spell_hit(j, &cast, &spell, None);
            self.entities[i].hit_ids.push(id);
        }
        if self.entities[i].traveled >= spell.projectile_range - 1e-9 {
            let source = &self.entities[i];
            let (x, y, owner) = (source.x, source.y, source.owner as usize);
            let spawns = self.config.cards[&cast.name].spawns[owner].clone();
            for mut child in spawns {
                child.id = self.next_id as i32;
                self.next_id += 1;
                child.x = x.clamp(0.25, 17.75);
                child.y = y.clamp(0.25, 31.75);
                child.lane = if x < 9.0 { 1 } else { 2 };
                child.birth = self.tick;
                // Newly spawned characters receive this interval's object
                // phase, but not its completed combat/movement phases.
                self.entities.push(child);
            }
            self.entities[i].alive = false;
        }
    }
    fn can_deploy_anywhere(&self, x: f64, y: f64) -> bool {
        (0.0..18.0).contains(&x)
            && (0.0..32.0).contains(&y)
            && !self.config.blocked_tiles[(y as usize) * 18 + x as usize]
            && !self.entities.iter().any(|e| {
                let r = if e.king { 2.0 } else { 1.5 };
                e.alive
                    && e.class == "Building"
                    && (e.king || e.stats.name == "Tower")
                    && (x - e.x).abs() <= r + 1e-9
                    && (y - e.y).abs() <= r + 1e-9
            })
    }
    fn can_deploy(&self, player: usize, x: f64, y: f64, spell: bool) -> bool {
        if !(0.0..18.0).contains(&x)
            || !(0.0..32.0).contains(&y)
            || self.config.blocked_tiles[(y as usize) * 18 + x as usize]
        {
            return false;
        }
        if !spell
            && self.entities.iter().any(|e| {
                let radius = if e.king { 2.0 } else { 1.5 };
                e.alive
                    && e.class == "Building"
                    && (e.king || e.stats.name == "Tower")
                    && (x - e.x).abs() <= radius + 1e-9
                    && (y - e.y).abs() <= radius + 1e-9
            })
        {
            return false;
        }
        if (player == 0 && ((1.0..15.0).contains(&y) || ((6.0..12.0).contains(&x) && y < 6.0)))
            || (player == 1
                && ((17.0..31.0).contains(&y) || ((6.0..12.0).contains(&x) && y >= 26.0)))
        {
            return true;
        }
        for lane in [1, 2] {
            let alive = self.entities.iter().any(|e| {
                e.alive
                    && e.class == "Building"
                    && e.stats.name == "Tower"
                    && e.owner != player as i32
                    && e.lane == lane
            });
            if alive {
                continue;
            }
            if ((lane == 1 && x < 9.0) || (lane == 2 && x >= 9.0))
                && ((player == 0 && (17.0..21.0).contains(&y))
                    || (player == 1 && (11.0..15.0).contains(&y)))
            {
                return true;
            }
            if (15.0..17.0).contains(&y)
                && ((lane == 1 && (2.5..4.5).contains(&x))
                    || (lane == 2 && (13.5..15.5).contains(&x)))
            {
                return true;
            }
        }
        false
    }
    fn footprint_blocked(&self, x: f64, y: f64, size: f64) -> bool {
        if let Some(mask) = self.placement_masks.get(&(size as i64)) {
            if (0.0..18.0).contains(&x) && (0.0..32.0).contains(&y) {
                return mask[y as usize * 18 + x as usize];
            }
        }
        self.entities.iter().any(|e| {
            let other_size = (e.stats.radius * 2.0).ceil() + 1.0;
            e.alive
                && e.class == "Building"
                && (x - e.x).abs() < (size + other_size) / 2.0
                && (y - e.y).abs() < (size + other_size) / 2.0
        })
    }
    fn payload_blocked(&self, x: f64, y: f64, radius: f64, half: Option<f64>) -> bool {
        self.entities.iter().any(|e| {
            e.alive
                && e.placement_radius.is_some_and(|r| {
                    let (dx, dy, r) = if let Some(h) = half {
                        ((e.x - x).abs().max(h) - h, (e.y - y).abs().max(h) - h, r)
                    } else {
                        (e.x - x, e.y - y, r + radius)
                    };
                    (dx * dx + dy * dy).sqrt() <= r + 1e-9
                })
        })
    }
    fn troop_anchor(
        &self,
        player: usize,
        x: f64,
        y: f64,
        mover_radius: f64,
        anywhere: bool,
    ) -> Option<(f64, f64)> {
        for radius in 0i32..31 {
            let mut offsets = Vec::new();
            if radius == 0 {
                offsets.push((0, 0));
            } else {
                for k in -radius..radius {
                    offsets.extend([(k, -radius), (-radius, -k), (-k, radius), (radius, k)]);
                }
            }
            let mut best = None;
            let mut best_d = i64::MAX;
            for (dx, dy) in offsets {
                let (cx, cy) = (x.floor() + 0.5 + dx as f64, y.floor() + 0.5 + dy as f64);
                if !(if anywhere {
                    self.can_deploy_anywhere(cx, cy)
                } else {
                    self.can_deploy(player, cx, cy, false)
                }) || !self.config.spawn_clear[(cy as usize) * 18 + cx as usize]
                    || self.footprint_blocked(cx, cy, 1.0)
                    || self.payload_blocked(cx, cy, mover_radius, None)
                {
                    continue;
                }
                let d = (units(cx) - units(x)).pow(2) + (units(cy) - units(y)).pow(2);
                if d < best_d {
                    best = Some((cx, cy));
                    best_d = d;
                }
            }
            if best.is_some() {
                return best;
            }
        }
        None
    }
    fn index(&self, id: i32) -> Option<usize> {
        self.entities.iter().position(|e| e.id == id)
    }
    fn pending_lethal(&self, j: usize) -> bool {
        let target = &self.entities[j];
        if target.pending_ms > 600 || target.shield > 0.0 {
            return false;
        }
        let damage: f64 = self
            .entities
            .iter()
            .filter(|e| {
                e.alive
                    && ((e.class == "Projectile" && e.stats.homing.unwrap_or(true))
                        || (e.spirit && !e.stats.electro_chain))
                    && (if e.spirit { e.spirit_launch } else { e.birth }) < self.tick
                    && e.shot_target == Some(target.id)
            })
            .map(|e| e.stats.damage)
            .sum();
        damage > 0.0 && damage >= target.hp
    }
    fn target(&self, i: usize, grid: &[Vec<usize>]) -> Option<i32> {
        let id = self.target_candidate(i, grid)?;
        let a = &self.entities[i];
        let b = &self.entities[self.index(id)?];
        (a.class != "Building" || reach(a, b, 0.0) || (a.target == Some(id) && keep_reach(a, b)))
            .then_some(id)
    }
    fn target_candidate(&self, i: usize, grid: &[Vec<usize>]) -> Option<i32> {
        let a = &self.entities[i];
        if let Some(j) = a.target.and_then(|id| self.index(id)) {
            let b = &self.entities[j];
            if b.owner != a.owner
                && !b.hidden
                && b.death_immunity.is_none()
                && b.stealth_until <= self.tick * 50
                && !b.underground
                && (!b.spirit || b.spirit_launch == self.tick)
                && a.can_hit_plane(b)
                && b.stagger <= 1e-9
                && keep_reach(a, b)
                && (a.stats.projectile_speed == 0 || a.attacked_current || !self.pending_lethal(j))
            {
                return Some(b.id);
            }
        }
        let mut best: Option<&Entity> = None;
        let mut best_d = f64::INFINITY;
        let mut candidates = Vec::new();
        // Python concatenates troop candidates before buildings for exact ties.
        for class in ["Troop", "Building"] {
            for (j, b) in self.entities.iter().enumerate() {
                if !b.alive
                    || b.hidden
                    || b.death_immunity.is_some()
                    || b.stealth_until > self.tick * 50
                    || b.spirit
                    || b.underground
                    || !a.can_hit_plane(b)
                    || b.stagger > 1e-9
                    || b.owner == a.owner
                    || b.class != class
                    || (a.stats.only_buildings && class != "Building")
                    || !sight(a, b)
                    || (a.stats.projectile_speed > 0 && self.pending_lethal(j))
                {
                    continue;
                }
                let d = distance(a, b);
                candidates.push((j, d));
                if d < best_d {
                    best = Some(b);
                    best_d = d;
                }
            }
        }
        if let Some(selected) = best {
            // Outside keep range, a valid current lock loses only to a
            // strictly nearer visible replacement (not to a new tie).
            if let Some(j) = a.target.and_then(|id| self.index(id)) {
                let old = &self.entities[j];
                let retained_depleted = (!old.alive
                    || (old.spirit && old.spirit_launch == self.tick))
                    && (a.class == "Building"
                        || (a.stats.projectile_speed > 0
                            && (!a.stats.ordinary || a.clock.timeline > 0))
                        || keep_reach(a, old));
                if a.class == "Troop"
                    && (retained_depleted
                        || (old.alive
                            && !old.spirit
                            && !old.underground
                            && !old.hidden
                            && old.death_immunity.is_none()
                            && old.stealth_until <= self.tick * 50
                            && old.stagger <= 1e-9))
                    && old.owner != a.owner
                    && a.can_hit_plane(old)
                    && (old.king || old.stats.name == "Tower" || sight(a, old))
                    && (a.stats.projectile_speed == 0 || !self.pending_lethal(j))
                    && best_d >= distance(a, old) - 1e-6
                {
                    return Some(old.id);
                }
            }
            // entities.py:_select_first_nearest_target uses owner-relative
            // building ties and exact character ties in fixed spatial buckets.
            if selected.class == "Building" {
                let direction = if a.owner == 0 { 1.0 } else { -1.0 };
                return candidates
                    .iter()
                    .filter(|&&(j, d)| self.entities[j].class == "Building" && d <= best_d + 1e-6)
                    .map(|&(j, _)| &self.entities[j])
                    .min_by(|x, y| {
                        (direction * (x.x - 9.0))
                            .total_cmp(&(direction * (y.x - 9.0)))
                            .then((direction * (x.y - 16.0)).total_cmp(&(direction * (y.y - 16.0))))
                            .then(x.id.cmp(&y.id))
                    })
                    .map(|e| e.id);
            }
            let tied: Vec<usize> = candidates
                .iter()
                .filter(|&&(j, d)| self.entities[j].class == "Troop" && d == best_d)
                .map(|&(j, _)| j)
                .collect();
            if tied.len() > 1 {
                let radius = units(a.stats.sight + a.stats.radius) + 2000;
                let (x, y) = (units(a.x), units(a.y));
                for bx in ((x - radius) >> 10).max(0)..=((x + radius) >> 10).min(17) {
                    for by in ((y - radius) >> 10).max(0)..=((y + radius) >> 10).min(31) {
                        for j in &grid[(bx * 32 + by) as usize] {
                            if tied.contains(j) {
                                return Some(self.entities[*j].id);
                            }
                        }
                    }
                }
            }
            return Some(selected.id);
        }
        if a.class != "Troop" {
            return None;
        }
        if a.route_backwards && a.moving {
            if let Some(j) = a.target.and_then(|id| self.index(id)) {
                let b = &self.entities[j];
                if b.alive
                    && !b.hidden
                    && b.death_immunity.is_none()
                    && b.stealth_until <= self.tick * 50
                    && !b.spirit
                    && !b.underground
                    && b.stagger <= 1e-9
                    && a.can_hit_plane(b)
                    && (a.stats.projectile_speed == 0
                        || a.attacked_current
                        || !self.pending_lethal(j))
                {
                    return a.target;
                }
            }
        }
        let kings: Vec<&Entity> = self
            .entities
            .iter()
            .enumerate()
            .filter(|(j, e)| {
                e.owner != a.owner
                    && e.class == "Building"
                    && a.can_hit_plane(e)
                    && e.king
                    && (!e.alive || a.stats.projectile_speed == 0 || !self.pending_lethal(*j))
            })
            .map(|(_, e)| e)
            .collect();
        let princesses: Vec<&Entity> = self
            .entities
            .iter()
            .enumerate()
            .filter(|(j, e)| {
                e.owner != a.owner
                    && e.class == "Building"
                    && a.can_hit_plane(e)
                    && !e.king
                    && e.stats.name == "Tower"
                    && (!e.alive || a.stats.projectile_speed == 0 || !self.pending_lethal(*j))
            })
            .map(|(_, e)| e)
            .collect();
        if kings.is_empty() {
            return princesses
                .into_iter()
                .min_by(|x, y| distance(a, x).total_cmp(&distance(a, y)))
                .map(|e| e.id);
        }
        let king = kings
            .into_iter()
            .min_by(|x, y| distance(a, x).total_cmp(&distance(a, y)));
        let princess = princesses
            .iter()
            .copied()
            .filter(|e| e.lane == a.lane || (a.age >= 500 && princesses.len() > 1))
            .min_by_key(|e| (units(e.x) - units(a.x)).abs());
        match (king, princess) {
            (Some(k), Some(p)) => {
                let dx = (units(p.x) - units(a.x)).abs();
                let dy = (units(p.y) - units(a.y)).abs();
                let d = dx.max(dy) + ((53 * dx.min(dy)) >> 7);
                let kx = units(k.x) - units(a.x);
                let ky = units(k.y) - units(a.y);
                Some(if d * d < kx * kx + ky * ky {
                    p.id
                } else {
                    k.id
                })
            }
            (Some(k), None) => Some(k.id),
            (None, Some(p)) => Some(p.id),
            (None, None) => None,
        }
    }
    fn occupied(&self) -> Vec<bool> {
        let mut out = vec![false; 2304];
        for e in self
            .entities
            .iter()
            .filter(|e| e.class == "Building" && e.alive)
        {
            let x = (units(e.x) - 1) / 500 * 500 + 500;
            let y = (units(e.y) - 1) / 500 * 500 + 500;
            let r = units(e.stats.radius);
            if x - r < 0 || y - r < 0 || x + r >= 18000 || y + r >= 32000 {
                continue;
            }
            for cy in (y - r) / 500..=(y + r - 1) / 500 {
                for cx in (x - r) / 500..=(x + r - 1) / 500 {
                    out[(cy * 36 + cx) as usize] = true;
                }
            }
        }
        out
    }
    fn goal_for(&self, i: usize, j: usize, occupied: &[bool]) -> Option<(i32, i32)> {
        let a = &self.entities[i];
        let b = &self.entities[j];
        let range = units(engagement_radius(a, b));
        let radius = range / 500 + 1;
        let (tx, ty) = cell(b.x, b.y);
        let mut best = None;
        let mut pri = 0;
        let mut dist = i64::MAX;
        let minx = (tx as i64 - radius).max(0);
        let maxx = (tx as i64 + radius).min(35);
        for y in (ty as i64 - radius).max(0)..=(ty as i64 + radius).min(63) {
            for k in minx..=maxx {
                let x = if a.x < 9.0 { k } else { maxx - (k - minx) };
                let (cx, cy) = (x * 500 + 250, y * 500 + 250);
                let (dx, dy) = (cx - units(b.x), cy - units(b.y));
                if dx * dx + dy * dy > range * range {
                    continue;
                }
                let p = if !a.stats.air
                    && ((!a.stats.hover && occupied[(y * 36 + x) as usize])
                        || self.config.water[(y * 36 + x) as usize])
                {
                    1
                } else {
                    2
                };
                let (dx, dy) = (cx - units(a.x), cy - units(a.y));
                let d = dx * dx + dy * dy;
                if p > pri || (p == pri && d < dist) {
                    best = Some((x as i32, y as i32));
                    pri = p;
                    dist = d;
                }
            }
        }
        best
    }
    fn prepare_route(
        &mut self,
        i: usize,
        j: usize,
        occupied: &[bool],
        cells: &Arc<Vec<usize>>,
        signatures: &[Vec<i32>; 2],
    ) -> (i64, i64) {
        self.entities[i].nav_target = Some(self.entities[j].id);
        let goal = self.goal_for(i, j, occupied);
        let start = cell(self.entities[i].x, self.entities[i].y);
        let friendly = &signatures[self.entities[i].owner as usize];
        let same_goal = goal == self.entities[i].goal;
        if self.entities[i].stats.air || self.entities[i].stats.hover {
            let e = &mut self.entities[i];
            if !same_goal || e.route.is_empty() {
                e.goal = goal;
                e.route = goal.into_iter().collect();
                if let Some(g) = goal {
                    let (gx, gy) = center(g);
                    e.direction = norm(gx - units(e.x), gy - units(e.y), 256);
                }
                e.route_backwards = false;
            }
            return goal
                .map(center)
                .unwrap_or((units(self.entities[j].x), units(self.entities[j].y)));
        }
        let occupied_indices = Arc::clone(cells);
        if same_goal
            && *friendly == self.entities[i].route_friendly
            && !self.entities[i].route.is_empty()
        {
            self.entities[i].route_occupied = occupied_indices;
        } else if let Some(g) = goal {
            let mut costs = self.config.costs.clone();
            if self.entities[i].stats.jump_speed > 0 {
                for (k, v) in costs.iter_mut().enumerate() {
                    if self.config.water[k] {
                        *v = 7;
                    }
                }
            }
            for &k in occupied_indices.iter() {
                costs[k] = costs[k].max(50);
            }
            let mut route: VecDeque<_> = astar::find(&costs, start, g)
                .unwrap_or_default()
                .into_iter()
                .skip(1)
                .collect();
            let (tx, ty) = (units(self.entities[j].x), units(self.entities[j].y));
            let e = &mut self.entities[i];
            let mut preserve_direction = false;
            if same_goal && !e.route.is_empty() && start != g {
                let blocked = e.route.iter().any(|&(x, y)| {
                    let k = (y * 36 + x) as usize;
                    occupied[k] && !e.route_occupied.contains(&k)
                });
                let freed = route.iter().any(|&(x, y)| {
                    let k = (y * 36 + x) as usize;
                    !occupied[k] && e.route_occupied.contains(&k)
                });
                if !blocked && !freed {
                    route = e.route.clone();
                    preserve_direction = !e.moving;
                }
            }
            if e.goal.is_none() && e.push.is_none() && e.push_tick == self.tick - 1 && self.tick > 1
            {
                route.push_front(start);
            }
            let origin = isqrt((units(e.x) - tx).pow(2) + (units(e.y) - ty).pow(2));
            e.route_backwards = route
                .iter()
                .copied()
                .chain(if route.is_empty() { Some(g) } else { None })
                .any(|c| {
                    let (x, y) = center(c);
                    isqrt((x - tx).pow(2) + (y - ty).pow(2)) > origin
                });
            e.route = route;
            e.goal = goal;
            e.route_occupied = occupied_indices;
            e.route_friendly = friendly.clone();
            if !preserve_direction {
                e.direction = e
                    .route
                    .front()
                    .map(|&c| {
                        let (x, y) = center(c);
                        norm(x - units(e.x), y - units(e.y), 256)
                    })
                    .unwrap_or((0, 0));
            }
        }
        self.entities[i]
            .route
            .front()
            .copied()
            .or(goal)
            .map(center)
            .unwrap_or((units(self.entities[j].x), units(self.entities[j].y)))
    }
    fn move_one(
        &mut self,
        i: usize,
        j: usize,
        occupied: &[bool],
        external: (i64, i64),
        cells: &Arc<Vec<usize>>,
        signatures: &[Vec<i32>; 2],
    ) {
        let (wx, wy) = self.prepare_route(i, j, occupied, cells, signatures);
        let e = &mut self.entities[i];
        let (dx, dy) = (wx - units(e.x), wy - units(e.y));
        let dist = isqrt(dx * dx + dy * dy).max(1);
        let speed = if e.charge >= 10000 {
            e.stats.charge_speed
        } else {
            e.stats.speed
        };
        e.public_speed_base = Some(speed as f64);
        let speed = (speed * e.haste_percent(1) / 100) * e.slow_percent(false) / 100;
        let mut work = speed.min(dist);
        if e.stats.stop_ms > 0 && e.stats.wait_ms > 0 {
            e.move_clock += (50 * e.haste_percent(1) / 100) * e.slow_percent(false) / 100;
            if e.move_clock >= e.stats.stop_ms + e.stats.wait_ms {
                e.move_clock %= e.stats.stop_ms + e.stats.wait_ms;
            } else if e.move_clock > e.stats.stop_ms {
                work = 0;
            }
        }
        let (vx, vy) = norm(dx, dy, 256);
        if dx != 0 || dy != 0 {
            e.facing = (dx, dy);
        }
        let (mut mx, mut my) = (vx * work / 256, vy * work / 256);
        if e.avoidance != 0 {
            let retained = 256 - e.avoidance.abs();
            let rx = (retained * mx >> 8) + (e.avoidance * my >> 8);
            let ry = (retained * my >> 8) + (-mx * e.avoidance >> 8);
            (mx, my) = norm(rx, ry, work);
        }
        e.x = ((units(e.x) + mx + external.0).clamp(0, 17999)) as f64 / 1000.0;
        e.y = ((units(e.y) + my + external.1).clamp(0, 31999)) as f64 / 1000.0;
        if (e.direction.0 * (wx - units(e.x)) / 256 + e.direction.1 * (wy - units(e.y)) / 256)
            < 1001
        {
            e.route.pop_front();
            e.direction = e
                .route
                .front()
                .map(|c| {
                    let (x, y) = center(*c);
                    norm(x - units(e.x), y - units(e.y), 256)
                })
                .unwrap_or((0, 0));
        }
        e.moving = true;
        if e.stats.charge_range > 0 {
            if work < 1 {
                e.charge = 0;
                e.public_speed_base = Some(e.stats.speed as f64);
                e.force_due = false;
            } else if e.charge <= 9999 {
                e.charge += 1000 * work / e.stats.charge_range;
            } else {
                e.force_due = true;
                e.clock.stop();
                e.clock.remaining = 0;
            }
        }
        if e.stats.jump_speed > 0
            && e.route.front().is_some_and(|&(x, y)| {
                self.config.water[(y * 36 + x) as usize] && (30..=33).contains(&y)
            })
        {
            if let Some(land) = e
                .route
                .iter()
                .copied()
                .find(|&(x, y)| !self.config.water[(y * 36 + x) as usize])
            {
                let (x, y) = center(land);
                e.jump = Some((x as f64 / 1000.0, y as f64 / 1000.0));
                e.route = VecDeque::from([land]);
                e.goal = None;
            }
        }
    }
    fn collide(&self, i: usize) -> (i64, i64) {
        let a = &self.entities[i];
        if a.stagger > 1e-9 || a.dash_travel() {
            return (0, 0);
        }
        let (mut vx, mut vy, mut count) = a.controlled_vector;
        for (j, b) in self.entities.iter().enumerate() {
            let air_a = a.collision_air(self.tick);
            let air_b = b.collision_air(self.tick);
            if a.underground
                || (a.push.is_some() && a.push_velocity < 1)
                || i == j
                || !b.alive
                || b.spirit
                || b.dash_travel()
                || (b.underground && b.class == "Troop")
                || (b.class != "Troop" && b.class != "Building")
                || air_a != air_b
            {
                continue;
            }
            let dx = units(a.x - b.x);
            let mut dy = units(a.y - b.y);
            let r = if b.class == "Building" {
                units(a.stats.radius.max(0.2).min(0.5) + b.stats.radius)
            } else {
                units(a.stats.radius.max(0.2) + b.stats.radius.max(0.2))
            };
            let ds = dx * dx + dy * dy;
            if ds > r * r {
                continue;
            }
            let d = if ds == 0 {
                dy = if a.owner == 0 { -1 } else { 1 };
                1
            } else {
                isqrt(ds).max(1)
            };
            let overlap = (r - d).clamp(0, 300);
            let mag = ((overlap as f64 * b.stats.mass / a.stats.mass.round_ties_even().max(1.0))
                as i64
                + 1)
            .min(300);
            count += 1;
            vx += dx * mag / d;
            vy += dy * mag / d;
        }
        if count > 0 {
            vx /= count;
            vy /= count;
        }
        if !a.controlled_bypass && vx * vx + vy * vy > 150 * 150 {
            return norm(vx, vy, 150);
        }
        (vx, vy)
    }
    fn apply_external(&mut self, i: usize, v: (i64, i64)) {
        let e = &mut self.entities[i];
        let (x, y) = (units(e.x), units(e.y));
        let (cx, cy) = (x / 500, y / 500);
        let (mut nx, mut ny) = (x + v.0, y + v.1);
        if e.deploy > 0.0 && !e.collision_air(self.tick) {
            let water = |cx: i64, cy: i64| {
                (0..36).contains(&cx)
                    && (30..=33).contains(&cy)
                    && self.config.water[(cy * 36 + cx) as usize]
            };
            if v.0 > 0 && nx >= (cx + 1) * 500 && water(cx + 1, cy) {
                nx = (cx + 1) * 500 - 1;
            } else if v.0 < 0 && nx < cx * 500 && water(cx - 1, cy) {
                nx = cx * 500;
            }
            if v.1 > 0 && ny >= (cy + 1) * 500 && water(cx, cy + 1) {
                ny = (cy + 1) * 500 - 1;
            } else if v.1 < 0 && ny < cy * 500 && water(cx, cy - 1) {
                ny = cy * 500;
            }
        }
        e.x = nx.clamp(0, 17999) as f64 / 1000.0;
        e.y = ny.clamp(0, 31999) as f64 / 1000.0;
    }
    fn avoidance_grid(&self) -> Vec<Vec<usize>> {
        let mut buckets = vec![Vec::new(); 18 * 32];
        for i in 0..self.entities.len() { self.add_avoidance_entity(i, &mut buckets); }
        buckets
    }
    fn add_avoidance_entity(&self, i: usize, buckets: &mut [Vec<usize>]) {
            let e = &self.entities[i];
            if e.class != "Troop" && e.class != "Building" {
                return;
            }
            let mut r = units(e.stats.radius);
            if r < 1 { return; }
            if e.class == "Troop" && e.alive && e.stagger <= 1e-9 {
                r += 250;
            }
            let (x, y) = (units(e.x), units(e.y));
            for bx in ((x - r) >> 10).max(0)..=((x + r) >> 10).min(17) {
                for by in ((y - r) >> 10).max(0)..=((y + r) >> 10).min(31) {
                    buckets[(bx * 32 + by) as usize].push(i);
                }
            }
    }
    fn update_avoidance(&mut self, i: usize, grid: &[Vec<usize>]) {
        if self.entities[i].leap.as_ref().is_some_and(|s| s.phase=="airborne" || s.phase=="landing") {
            self.entities[i].avoidance=0; return;
        }
        let a = self.entities[i].clone();
        let (fx, fy) = norm(a.facing.0, a.facing.1, 256);
        let stopped = a.death_ticks <= 0
            && a.push.is_none()
            && a.push_tick != self.tick
            && ((a.move_target.is_none() && a.jump.is_none()) || a.deploy > 0.0 || a.stun > 0.0)
            && !(a.stun > 0.0 && a.frozen_moving);
        let (mut moving, mut statics, mut moving_side, mut static_side) = (0, 0, true, true);
        if !(stopped && !(a.deploy > 0.0 && a.stun <= 0.0)) && (fx != 0 || fy != 0) {
            let (x, y) = (units(a.x), units(a.y));
            let (px, py) = (x + fx, y + fy);
            let r = units(a.stats.radius).clamp(0, 500);
            let mut seen = vec![false; self.entities.len()];
            let mut candidates = Vec::new();
            for bx in ((px - r) >> 10).max(0)..=((px + r) >> 10).min(17) {
                for by in ((py - r) >> 10).max(0)..=((py + r) >> 10).min(31) {
                    for &j in &grid[(bx * 32 + by) as usize] {
                        if !seen[j] {
                            seen[j] = true;
                            candidates.push(j);
                        }
                    }
                }
            }
            for j in candidates {
                if j == i {
                    continue;
                }
                let b = &self.entities[j];
                if b.spirit && b.spirit_launch != self.tick {
                    continue;
                }
                if (a.collision_air(self.tick)) != (b.collision_air(self.tick)) {
                    continue;
                }
                let (bx, by) = (units(b.x), units(b.y));
                let br = units(b.stats.radius);
                if (bx - px) * (bx - px) + (by - py) * (by - py) > (r + br) * (r + br) {
                    continue;
                }
                let side = fy * (bx - x) - fx * (by - y) < 0;
                if b.class == "Troop" && b.alive && !b.spirit && b.stagger <= 1e-9 {
                    let dot = if b.death_ticks <= 0
                        && b.push.is_none()
                        && b.push_tick != self.tick
                        && b.deploy <= 0.0
                        && ((b.move_target.is_none() && b.jump.is_none()) || b.stun > 0.0)
                        && !(b.stun > 0.0 && b.frozen_moving)
                    {
                        0
                    } else {
                        let (x, y) = norm(b.facing.0, b.facing.1, 256);
                        x * fx + y * fy
                    };
                    if dot > 0 || (a.charge >= 10000 && a.stats.mass > b.stats.mass) {
                        continue;
                    }
                    moving += 1;
                    moving_side = if b.avoidance != 0 {
                        b.avoidance > 0
                    } else {
                        side
                    };
                } else {
                    if self.entities[i].route.len() >= 2 {
                        let (wx, wy) = center(*self.entities[i].route.front().unwrap());
                        if (wx - bx) * (wx - bx) + (wy - by) * (wy - by) < br * br {
                            self.entities[i].route.pop_front();
                        }
                    }
                    statics += 1;
                    static_side = side;
                }
            }
        }
        let e = &mut self.entities[i];
        let side = if statics > 0 {
            static_side
        } else {
            moving_side
        };
        if moving + statics > 0 {
            if e.avoidance == 0 {
                e.avoidance = if side { 200 } else { -200 };
            } else if statics > 0 {
                e.avoidance = (e.avoidance + if side { 20 } else { -20 }).clamp(-200, 200);
            }
        }
        e.avoidance = if e.avoidance > 0 {
            (e.avoidance - 10).max(0)
        } else {
            (e.avoidance + 10).min(0)
        };
    }
    fn push_move(
        &mut self,
        i: usize,
        external: (i64, i64),
        occupied: &[bool],
        cells: &Arc<Vec<usize>>,
        signatures: &[Vec<i32>; 2],
    ) {
        self.entities[i].push_tick = self.tick;
        if self.entities[i].push_reset && self.entities[i].stun <= 0.0 {
            let finishing = self.entities[i].clock.finish > 0;
            self.entities[i].push_reset = false;
            if !finishing {
                self.entities[i].preload_blocked = false;
                self.entities[i].clock.stop();
                self.entities[i].windup = false;
                self.entities[i].started = false;
                if !self.entities[i].moving && !self.entities[i].stats.air {
                    if let Some(j) = self.entities[i].target.and_then(|t| self.index(t)) {
                        self.prepare_route(i, j, occupied, cells, signatures);
                        self.entities[i].moving = true;
                    }
                }
            }
        }
        if let Some(j) = self.entities[i].move_target.and_then(|t| self.index(t)) {
            if !self.entities[i].stats.air
                && (!self.entities[i].moving
                    || self.entities[i].nav_target != self.entities[i].move_target)
            {
                self.prepare_route(i, j, occupied, cells, signatures);
                self.entities[i].moving = true;
            }
        }
        let e = &mut self.entities[i];
        let (mut x, mut y) = (units(e.x), units(e.y));
        let ground_plane = !e.collision_air(self.tick);
        if e.push_velocity > 0 && ground_plane {
            x = x.clamp(250, 17750);
            y = y.clamp(250, 31750);
        }
        if e.push_velocity > 0
            && ground_plane
            && self.config.water[(y / 500 * 36 + x / 500) as usize]
        {
            let mut best = (x, y);
            let mut distance = i64::MAX;
            for dy in (-2250i64..=2750).step_by(500) {
                for dx in (-2250i64..=2750).step_by(500) {
                    let (cx, cy) = (x + dx, y + dy);
                    if !(0..18000).contains(&cx)
                        || !(0..32000).contains(&cy)
                        || self.config.water[(cy / 500 * 36 + cx / 500) as usize]
                    {
                        continue;
                    }
                    let d = dx.abs().max(dy.abs()) + (53 * dx.abs().min(dy.abs()) >> 7);
                    if d < distance {
                        best = (cx, cy);
                        distance = d;
                    }
                }
            }
            (x, y) = best;
        }
        e.push_velocity -= 25;
        let target = e.push.unwrap();
        let (dx, dy) = (units(target.0) - x, units(target.1) - y);
        let work = e.push_velocity.min(250).min(isqrt(dx * dx + dy * dy));
        if work < 10 {
            e.charge = 0;
            e.public_speed_base = Some(e.stats.speed as f64);
            e.force_due = false;
        } else if e.moving && e.move_target.is_some() && e.stats.charge_range > 0 {
            if e.charge <= 9999 {
                e.charge += 1000 * work / e.stats.charge_range;
            } else {
                e.force_due = true;
                e.clock.stop();
                e.clock.remaining = 0;
            }
        }
        let (fx, fy) = norm(dx, dy, 256);
        let (mut mx, mut my) = (fx * work / 256, fy * work / 256);
        if e.avoidance != 0 && work != 0 {
            let retained = 256 - e.avoidance.abs();
            (mx, my) = norm(
                (retained * mx >> 8) + (e.avoidance * my >> 8),
                (retained * my >> 8) + (-mx * e.avoidance >> 8),
                work,
            );
        }
        e.x = (x + mx + external.0).clamp(0, 17999) as f64 / 1000.0;
        e.y = (y + my + external.1).clamp(0, 31999) as f64 / 1000.0;
        if e.push_velocity < 0 {
            e.push = None;
            e.push_velocity = 0;
            e.push_reset = false;
            e.forced_active = false;
        }
    }
    fn combat_one(&mut self, i: usize, grid: &[Vec<usize>]) {
        self.entities[i].move_target = None;
        if self.entities[i].deploy > 0.0 || !self.entities[i].active {
            return;
        }
        if self.entities[i].freeze_pause > 0.0
            || (self.entities[i].stun > 0.0
                && (self.entities[i].stats.ordinary
                    || self.entities[i].king
                    || self.entities[i].stats.name == "Tower"))
        {
            if self.entities[i].active && self.entities[i].activation_remaining > 0.0 {
                self.entities[i].activation_remaining =
                    (self.entities[i].activation_remaining - 0.05).max(0.0);
                if self.entities[i].activation_remaining <= 1e-9 {
                    self.entities[i].activation_remaining = 0.0;
                }
            }
            return;
        }
        if self.entities[i].forced_active && self.entities[i].push.is_none()
            && self.entities[i].clock.finish==0 && self.entities[i].jump.is_none() { return; }
        if self.entities[i].clock.finish > 0 {
            self.entities[i].consume_clock_reseed();
            self.entities[i].finish_tick = self.tick;
            self.entities[i].clock.advance(50, 0, false);
            if !self.entities[i].stats.ordinary && !self.entities[i].preload_blocked {
                self.entities[i].cooldown =
                    (self.entities[i].cooldown - 0.05).max(self.entities[i].stats.first);
            }
            if self.entities[i].clock.finish == 0 {
                self.entities[i].started = false;
                self.entities[i].windup = false;
                self.entities[i].last_target = None;
            }
            return;
        }
        if self.entities[i].jump.is_some() {
            self.entities[i].consume_clock_reseed();
            self.entities[i].clock.advance(50, 0, false);
            return;
        }
        self.collect_souls(i);
        if self.entities[i].activation_remaining > 0.0 {
            self.entities[i].activation_remaining =
                (self.entities[i].activation_remaining - 0.05).max(0.0);
            if self.entities[i].activation_remaining < 1e-9 {
                self.entities[i].activation_remaining = 0.0;
            }
            return;
        }
        let mut activation_completed = false;
        if self.entities[i].activation_hit_remaining > 0.0 {
            self.entities[i].activation_hit_remaining =
                (self.entities[i].activation_hit_remaining - 0.05).max(0.0);
            if self.entities[i].activation_hit_remaining > 1e-9 {
                self.entities[i].target = self.target(i, grid);
                return;
            }
            self.entities[i].activation_hit_remaining = 0.0;
            activation_completed = true;
            self.entities[i].cooldown = 0.0;
        }
        if self.champion_combat_tick(i) {
            return;
        }
        if self.dash_combat(i,grid) { return; }
        if self.leap_combat(i,grid) { return; }
        if self.hook_combat(i) { return; }
        self.entities[i].consume_clock_reseed();
        let target = self.target(i, grid);
        let old = self.entities[i].target;
        let had_attacked_current = self.entities[i].attacked_current;
        let previous = self.entities[i].last_target;
        let acquired_from_idle = previous.is_none();
        if old.is_some() && old != target && old.and_then(|t| self.index(t)).is_none() {
            self.entities[i].clock.removed();
        }
        if old != target {
            self.entities[i].attacked_current = false;
        }
        self.entities[i].target = target;
        self.entities[i].last_target = target;
        let j = target.and_then(|t| self.index(t));
        let in_range = j.is_some_and(|j| engagement_reach(&self.entities[i], &self.entities[j]));
        let preserve_pending = in_range
            && self.entities[i].stats.projectile_speed > 0
            && !had_attacked_current
            && old.and_then(|id| self.index(id)).is_some_and(|j| {
                let e = &self.entities[j];
                e.alive
                    && !e.hidden
                    && !e.spirit
                    && !e.underground
                    && e.stagger <= 1e-9
                    && self.pending_lethal(j)
            });
        if (previous != target
            && !in_range
            && (previous.is_some() || self.entities[i].stats.ordinary))
            || (previous.is_some()
                && previous != target
                && !self.entities[i].stats.ordinary
                && self.entities[i].class == "Troop"
                && !preserve_pending)
        {
            let e = &mut self.entities[i];
            e.windup = false;
            e.started = false;
            e.clock.stop();
            e.cooldown = e.cooldown.max(e.stats.retarget.unwrap_or(e.stats.first));
        }
        let engaged = j.is_some_and(|j| {
            in_range
                || (started_projectile(&self.entities[i])
                    && keep_reach(&self.entities[i], &self.entities[j]))
                || (self.entities[i].windup
                    && (!self.entities[i].stats.ordinary
                        || self.entities[i].clock.timeline % self.entities[i].stats.interval > 50))
        });
        self.entities[i].pending_lethal = self.entities[i].stats.projectile_speed > 0
            && self.entities[i].attacked_current
            && j.is_some_and(|j| self.pending_lethal(j));
        if self.entities[i].resume_pending {
            self.entities[i].resume_pending = false;
            if !engaged {
                self.entities[i].clock.stop();
            } else {
                self.entities[i].windup = true;
            }
        }
        self.observe_ramp(i, j, in_range);
        if engaged {
            let b = &self.entities[j.unwrap()];
            let a = &self.entities[i];
            if a.class == "Troop" {
                self.entities[i].facing = (units(b.x - a.x), units(b.y - a.y));
            }
        }
        if self.entities[i].stun > 0.0 {
            return;
        }
        if !self.entities[i].stats.ordinary
            && !self.entities[i].preload_blocked
            && (if self.entities[i].class == "Building" {
                old.is_none()
            } else {
                acquired_from_idle || self.entities[i].moving
            })
            && !self.entities[i].windup
            && in_range
            && self.entities[i].cooldown > self.entities[i].stats.first
        {
            self.entities[i].cooldown =
                (self.entities[i].cooldown - 0.05).max(self.entities[i].stats.first);
        }
        if self.entities[i].push.is_some() && !self.entities[i].push_preserve {
            self.entities[i].clock.advance(50, 0, false);
            if !engaged {
                self.entities[i].move_target = target;
            }
            return;
        }
        // Target observation during interrupting pushback does not start a hit.
        if self.entities[i].kamikaze_primed {
            self.entities[i].kamikaze_timer = (self.entities[i].kamikaze_timer-0.05).max(0.0);
            if self.entities[i].kamikaze_timer<=1e-9 { self.damage(i,self.entities[i].hp); }
            return;
        }
        if engaged {
            self.entities[i].started = true;
        }
        self.entities[i].windup = engaged;
        if self.entities[i].class == "Building" && self.entities[i].stats.ordinary && !engaged {
            self.entities[i].clock.stop();
            self.entities[i].force_due = false;
        }
        let attack_work = if activation_completed {
            0
        } else {
            self.entities[i].attack_work()
        };
        let due = if !self.entities[i].stats.ordinary {
            let floor = if engaged {
                0.0
            } else {
                self.entities[i].stats.first
            };
            self.entities[i].cooldown = if engaged {
                self.entities[i].cooldown - attack_work as f64 / 1000.0
            } else if self.entities[i].preload_blocked {
                self.entities[i].cooldown
            } else {
                (self.entities[i].cooldown - 0.05).max(floor)
            };
            engaged && self.entities[i].cooldown <= 1e-9
        } else {
            {
                let active = engaged && self.entities[i].push.is_none();
                if active && self.entities[i].force_due {
                    let e = &mut self.entities[i];
                    e.force_due = false;
                    e.clock.timeline = e.stats.interval;
                    e.clock.remaining = e.stats.load;
                    true
                } else {
                    let load_work = if self.entities[i].preload_blocked && self.entities[i].clock.timeline==0 { 0 } else { 50 };
                    self.entities[i].clock.advance_with_load(50, attack_work, active, load_work) > 0
                }
            }
        };
        if let Some(j) = j {
            if !engaged && self.entities[i].class == "Troop" {
                self.entities[i].move_target = target;
            }
            if due {
                if let Some(delay) = self.entities[i].stats.kamikaze_delay {
                    if delay>0.0 {
                        self.entities[i].kamikaze_primed=true;
                        self.entities[i].kamikaze_timer=delay;
                        self.entities[i].windup=false;
                    } else { self.damage(i,self.entities[i].hp); }
                    return;
                }
                if !self.entities[i].stats.ramp_stages.is_empty() {
                    let e = &mut self.entities[i];
                    if e.ramp_target != target {
                        e.ramp_target = target;
                        e.ramp_time = 0.0;
                    }
                    e.stats.damage = e.ramp_damage();
                }
                if self.entities[i].stats.ghost_fade > 0 {
                    self.entities[i].stealth_until = 0;
                    self.entities[i].ghost_time = 0.0;
                }
                if self.entities[i].stats.spirit_speed > 0 {
                    let aim = (self.entities[j].x, self.entities[j].y);
                    let e = &mut self.entities[i];
                    e.spirit = true;
                    e.entity_kind = 2;
                    e.spirit_launch = self.tick;
                    e.shot_target = target;
                    e.aim = aim;
                    if !e.alive && !e.stats.electro_chain {
                        e.hp = 1.0;
                        e.alive = true;
                    }
                    return;
                }
                self.entities[i].windup = false;
                self.entities[i].preload_blocked = false;
                self.entities[i].attacked_current = true;
                let a = self.entities[i].clone();
                let target_body = &self.entities[j];
                let cancel = a.stats.speed > 0
                    && ((a.x - target_body.x).powi(2) + (a.y - target_body.y).powi(2)).sqrt()
                        > engagement_radius(&a, target_body)
                            + target_body.stats.radius
                            + 1.5
                            + 1e-9;
                if cancel {
                    self.entities[i].charge = 0;
                    self.entities[i].public_speed_base = Some(self.entities[i].stats.speed as f64);
                    self.entities[i].force_due = false;
                    return;
                }
                if a.stats.projectile_speed > 0 {
                    let mut shot = a.clone();
                    shot.id = self.next_id as i32;
                    self.next_id += 1;
                    shot.class = "Projectile".into();
                    shot.champion = None;
                    shot.entity_kind = 2;
                    shot.freeze_pause = 0.0;
                    shot.source_character = true;
                    shot.hp = 1.0;
                    shot.alive = true;
                    shot.target = None;
                    shot.shot_target = if self.entities[j].alive { target } else { None };
                    shot.aim = (self.entities[j].x, self.entities[j].y);
                    let (mx, my) = norm(
                        units(shot.aim.0 - a.x),
                        units(shot.aim.1 - a.y),
                        units(a.stats.muzzle),
                    );
                    shot.x = (units(a.x) + mx) as f64 / 1000.0;
                    shot.y = (units(a.y)
                        + my
                        + units(a.stats.muzzle_y) * if a.owner == 0 { 1 } else { -1 })
                        as f64
                        / 1000.0;
                    shot.projectile_origin = (shot.x, shot.y);
                    shot.stats.can_air = a.stats.projectile_air.unwrap_or(a.stats.can_air);
                    shot.stats.can_ground = a.stats.projectile_ground.or(a.stats.can_ground);
                    if a.stats.projectile_range > 0.0 {
                        let (dx, dy) = norm(
                            units(shot.aim.0 - a.x),
                            units(shot.aim.1 - a.y),
                            units(a.stats.projectile_range),
                        );
                        shot.aim = (
                            (units(shot.x) + dx) as f64 / 1000.0,
                            (units(shot.y) + dy) as f64 / 1000.0,
                        );
                        shot.piercing = true;
                        shot.stats.homing = Some(false);
                    }
                    shot.stats.damage = a.stats.projectile_damage.unwrap_or(a.stats.damage);
                    if a.stats.rolling {
                        shot.class = "RollingProjectile".into();
                        shot.roll_direction = (units(self.entities[j].x-a.x),units(self.entities[j].y-a.y));
                        shot.traveled = 0.0;
                        shot.effect_age = 0.0;
                    } else if a.stats.homing_time > 0 && shot.shot_target.is_some() {
                        let (dx,dy) = (units(self.entities[j].x)-units(shot.x),units(self.entities[j].y)-units(shot.y));
                        if isqrt(dx*dx+dy*dy) > units(a.stats.homing_min) {
                            shot.temporary_remaining = a.stats.homing_time;
                            shot.temporary_target = shot.shot_target;
                            shot.temporary_aim = (self.entities[j].x,self.entities[j].y);
                        }
                    }
                    shot.birth = self.tick;
                    shot.stats.speed = a.stats.projectile_speed;
                    shot.route.clear();
                    shot.goal = None;
                    let index = self.entities.len();
                    let start_radius = shot.stats.projectile_radius + shot.stats.projectile_extra;
                    let start_hit = shot.piercing && shot.stats.projectile_extra > 0.0;
                    self.entities.push(shot);
                    if start_hit { self.piercing_hits(index,start_radius); }
                } else {
                    let secondary = self.secondary_recipients(i, j);
                    let damage = if a.charge >= 10000 && a.stats.special_damage > 0.0 {
                        a.stats.special_damage
                    } else {
                        a.stats.damage
                    };
                    let origin = if a.stats.self_area {
                        (a.x, a.y)
                    } else {
                        (self.entities[j].x, self.entities[j].y)
                    };
                    let mut victims = Vec::new();
                    if self.entities[j].alive
                        && self.entities[j].stagger <= 1e-9
                        && !self.entities[j].hidden
                    {
                        victims.push(j);
                    }
                    if a.stats.area_radius > 0.0 {
                        for (k, e) in self.entities.iter().enumerate() {
                            if k != j
                                && e.death_immunity.is_none()
                                && e.alive
                                && !e.spirit
                                && !e.underground
                                && e.owner != a.owner
                                && (e.class == "Troop" || e.class == "Building")
                                && e.stagger <= 1e-9
                                && !e.hidden
                                && a.can_hit_plane(e)
                                && Self::in_area(e, origin.0, origin.1, a.stats.area_radius)
                            {
                                victims.push(k);
                            }
                        }
                    }
                    for k in victims {
                        let victim = &self.entities[k];
                        let amount = if victim.king || victim.stats.name == "Tower" {
                            a.stats.crown_damage.unwrap_or(damage)
                        } else {
                            damage
                        };
                        self.damage(k, amount);
                    }
                    for k in secondary {
                        let scaled = damage * a.stats.multi_attack.as_ref().unwrap().scale;
                        let amount = if self.entities[k].king || self.entities[k].stats.name == "Tower" {
                            a.stats.crown_damage.unwrap_or(scaled)
                        } else { scaled };
                        self.damage(k, amount);
                        self.character_hit_buff(i, k);
                    }
                    self.character_hit_buff(i, j);
                }
                if self.entities[i].stats.kamikaze
                    || (self.entities[i].stats.break_on_building_hit
                        && self.entities[j].class == "Building")
                {
                    self.damage(i, self.entities[i].hp);
                }
                if self.entities[i].stats.recoil > 0.0 {
                    self.recoil(i, j);
                }
                let carry = if self.entities[i].king || self.entities[i].stats.name == "Tower" {
                    self.entities[i].cooldown.min(0.0)
                } else {
                    0.0
                };
                self.entities[i].cooldown = self.entities[i].stats.interval as f64 / 1000.0 + carry;
                self.entities[i].charge = 0;
                self.entities[i].public_speed_base = Some(self.entities[i].stats.speed as f64);
                self.entities[i].force_due = false;
            }
        }
    }
    fn hide_tick(&mut self, i: usize) {
        let e = &mut self.entities[i];
        if e.stats.hide_ms == 0 || e.stun > 0.0 {
            return;
        }
        let has_target = e.target.is_some() || e.clock.finish > 0 || e.finish_tick == self.tick;
        let old = e.hide_phase;
        let work = e.attack_work();
        let mut next = old + work;
        let cycle = e.stats.hide_ms + e.stats.rise_ms;
        if !has_target {
            e.hide_phase = if next >= e.stats.hide_ms && old <= e.stats.hide_ms {
                e.stats.hide_ms
            } else {
                next % cycle
            };
        } else {
            if old < e.stats.hide_ms {
                next = (old - work).max(0);
            }
            e.hide_phase = if next > cycle || old == 0 {
                0
            } else {
                next % cycle
            };
        }
        e.hidden = e.hide_phase == e.stats.hide_ms;
        if e.hidden {
            e.target = None;
        }
    }
    fn resume_frozen_stop(&mut self, i: usize, j: usize) {
        if self.entities[i].moving {
            return;
        }
        let id = self.entities[j].id;
        let e = &mut self.entities[i];
        if let Some(saved) = e.frozen_stop.take() {
            if saved.resumable && id == saved.target_id && e.route.is_empty() {
                e.route = saved.route;
                e.goal = saved.goal;
                e.route_occupied = saved.occupied;
                e.direction = saved.direction.unwrap_or_else(|| {
                    e.route
                        .front()
                        .map(|&c| {
                            let (x, y) = center(c);
                            norm(x - units(e.x), y - units(e.y), 256)
                        })
                        .unwrap_or((0, 0))
                });
            }
        }
    }
    fn note_stopped_route(&mut self, i: usize) {
        let stopping = self.entities[i].moving || !self.entities[i].route.is_empty();
        let target_is_building = self.entities[i]
            .nav_target
            .and_then(|id| self.index(id))
            .is_some_and(|j| self.entities[j].class == "Building");
        let e = &mut self.entities[i];
        if stopping {
            e.frozen_stop = if e.moving
                && !e.route.is_empty()
                && e.charge < 10000
                && e.nav_target.is_some()
                && e.target == e.nav_target
                && target_is_building
            {
                Some(FrozenStopRoute {
                    target_id: e.nav_target.unwrap(),
                    route: e.route.clone(),
                    goal: e.goal,
                    occupied: Arc::clone(&e.route_occupied),
                    direction: Some(e.direction),
                    position: (e.x, e.y),
                    cell: cell(e.x, e.y),
                    frozen: false,
                    reacquired: false,
                    resumable: false,
                })
            } else {
                None
            };
        } else if let Some(saved) = &mut e.frozen_stop {
            if saved.frozen && !saved.reacquired && e.target == Some(saved.target_id) {
                saved.reacquired = true;
                let (x, y) = center(*saved.route.front().unwrap());
                let direction = saved.direction.unwrap_or_else(|| {
                    norm(
                        x - units(saved.position.0),
                        y - units(saved.position.1),
                        256,
                    )
                });
                let remaining =
                    direction.0 * (x - units(e.x)) / 256 + direction.1 * (y - units(e.y)) / 256;
                saved.resumable = remaining >= 1001 && cell(e.x, e.y) == saved.cell;
            }
        }
    }

    fn tick_once(&mut self, trace: bool) -> Vec<(&'static str, serde_json::Value)> {
        let mut phases = Vec::new();
        macro_rules! capture {
            ($name:expr) => {
                if trace {
                    phases.push(($name, serde_json::to_value(&*self).unwrap()));
                }
            };
        }
        if self.game_over {
            return phases;
        }
        self.tick += 1;
        let regen = if self.tick > 4800 {
            0.93
        } else if self.tick > 2400 {
            1.4
        } else {
            2.8
        };
        for p in &mut self.players {
            if p.elixir < 10.0 {
                p.elixir = ((p.elixir * 10000.0).round_ties_even()
                    + (500.0_f64 / regen) as i64 as f64)
                    .min(100000.0)
                    / 10000.0;
            }
            p.refill = (p.refill - 50).max(0);
            if p.refill == 0 {
                if let Some(k) = p.hand.iter().position(|c| c.is_none()) {
                    if let Some(card) = p.cycle.pop_front() {
                        p.hand[k] = Some(card);
                        p.refill = if self.tick < 2400 {
                            1000
                        } else if self.tick < 4800 {
                            500
                        } else {
                            350
                        };
                    }
                }
            }
        }
        capture!("start");
        let n = self.entities.len();
        let occupied = self.occupied();
        let cells = Arc::new(
            occupied
                .iter()
                .enumerate()
                .filter_map(|(k, &v)| v.then_some(k))
                .collect(),
        );
        let signatures = [0, 1].map(|owner| {
            self.entities
                .iter()
                .filter(|e| e.alive && e.class == "Building" && e.owner == owner)
                .map(|e| e.id)
                .collect()
        });
        let mut grid = self.avoidance_grid();
        let mut indexed = n;
        let eligible: Vec<bool> = self.entities.iter().map(|e| e.alive).collect();
        for i in 0..n {
            while indexed < self.entities.len() {
                self.add_avoidance_entity(indexed, &mut grid);
                indexed += 1;
            }
            if eligible[i]
                && !self.entities[i].spirit
                && (self.entities[i].class == "Troop" || self.entities[i].class == "Building")
            {
                self.combat_one(i, &grid);
            }
        }
        capture!("combat");
        for i in 0..n {
            while indexed < self.entities.len() {
                self.add_avoidance_entity(indexed, &mut grid);
                indexed += 1;
            }
            if self.entities[i].alive
                && self.entities[i].class == "Building"
                && self.entities[i].underground
            {
                self.tunnel_move(i);
                continue;
            }
            if !self.entities[i].alive
                || self.entities[i].spirit
                || self.entities[i].class != "Troop"
            {
                continue;
            }
            let external = self.collide(i);
            self.entities[i].controlled_vector = (0, 0, 0);
            self.entities[i].controlled_bypass = false;
            if self.entities[i].stagger > 1e-9 {
                continue;
            }
            if self.entities[i].moving {
                self.entities[i].frozen_stop = None;
            }
            if self.entities[i].deploy <= 0.0
                && self.entities[i].stun <= 0.0
                && self.entities[i].push.is_none()
                && self.entities[i].jump.is_none()
                && self.entities[i].death_ticks <= 0
                && !self.entities[i].dash_active()
                && !self.entities[i].leap_active()
                && !self.entities[i].hook_active()
                && !self.entities[i].forced_active
            {
                if let Some(j) = self.entities[i].move_target.and_then(|id| self.index(id)) {
                    self.resume_frozen_stop(i, j);
                    self.prepare_route(i, j, &occupied, &cells, &signatures);
                }
            }
            if self.entities[i].death_ticks > 0 {
                if self.entities[i].push.is_none() {
                    self.update_avoidance(i, &grid);
                }
                self.death_travel_move(i, external);
                continue;
            }
            if self.entities[i].push.is_some() {
                self.push_move(i, external, &occupied, &cells, &signatures);
                // Python finish_movement_tick still services the frozen route
                // after pushback consumed the movement vector (entities.py:391).
                let e = &mut self.entities[i];
                if e.stun > 0.0 && e.frozen_moving {
                    if let Some(&waypoint) = e.route.front() {
                        let (x, y) = center(waypoint);
                        let (dx, dy) = (x - units(e.x), y - units(e.y));
                        if dx != 0 || dy != 0 { e.facing = (dx, dy); }
                        if e.direction.0 * dx / 256 + e.direction.1 * dy / 256 < 1001 {
                            e.route.pop_front();
                            e.direction = e.route.front().map(|&c| {
                                let (x, y) = center(c);
                                norm(x - units(e.x), y - units(e.y), 256)
                            }).unwrap_or((0, 0));
                        }
                    }
                }
                continue;
            }
            self.update_avoidance(i, &grid);
            if self.entities[i].underground {
                self.tunnel_move(i);
                self.apply_external(i, external);
                continue;
            }
            if self.entities[i].deploy > 0.0 {
                self.apply_external(i, external);
                continue;
            }
            if let Some(target) = self.entities[i].jump {
                let e = &mut self.entities[i];
                e.moving = false;
                let (dx, dy) = (units(target.0 - e.x), units(target.1 - e.y));
                e.facing = (dx, dy);
                let work = e.stats.jump_speed;
                let (fx, fy) = norm(dx, dy, 256);
                let (mut mx, mut my) = (fx * work / 256, fy * work / 256);
                if e.avoidance != 0 {
                    let retained = 256 - e.avoidance.abs();
                    (mx, my) = norm(
                        (retained * mx >> 8) + (e.avoidance * my >> 8),
                        (retained * my >> 8) + (-mx * e.avoidance >> 8),
                        work.min(isqrt(dx * dx + dy * dy)),
                    );
                }
                e.x = (units(e.x) + mx) as f64 / 1000.0;
                e.y = (units(e.y) + my) as f64 / 1000.0;
                let (dx, dy) = (units(target.0 - e.x), units(target.1 - e.y));
                if isqrt(dx * dx + dy * dy) / work <= 1 {
                    e.jump = None;
                    e.landed_tick = self.tick;
                    e.moving = true;
                }
                self.apply_external(i, external);
                continue;
            }
            if self.dash_movement(i,external) { continue; }
            if self.leap_movement(i,external) { continue; }
            if self.hook_stop_movement(i,external) { continue; }
            if self.entities[i].stun > 0.0 {
                if let Some(saved) = &mut self.entities[i].frozen_stop {
                    saved.frozen = true;
                    saved.reacquired = false;
                }
                self.entities[i].charge = 0;
                self.entities[i].public_speed_base = Some(self.entities[i].stats.speed as f64);
                self.entities[i].force_due = false;
                self.entities[i].moving = false;
                let waypoint = if self.entities[i].frozen_moving {
                    self.entities[i].route.front().copied().map(center)
                } else {
                    None
                };
                if let Some((x, y)) = waypoint {
                    self.entities[i].facing =
                        (x - units(self.entities[i].x), y - units(self.entities[i].y));
                }
                self.apply_external(i, external);
                if let Some((x, y)) = waypoint {
                    let e = &mut self.entities[i];
                    if e.direction.0 * (x - units(e.x)) / 256
                        + e.direction.1 * (y - units(e.y)) / 256
                        < 1001
                    {
                        e.route.pop_front();
                        e.direction = e
                            .route
                            .front()
                            .map(|&c| {
                                let (x, y) = center(c);
                                norm(x - units(e.x), y - units(e.y), 256)
                            })
                            .unwrap_or((0, 0));
                    }
                }
                continue;
            }
            if let Some(j) = self.entities[i].move_target.and_then(|id| self.index(id)) {
                // Later combat can make already-reserved projectile damage lethal
                // after this troop selected its goal. Python revalidates that
                // living target before spending committed natural movement.
                if self.entities[j].alive
                    && !self.entities[j].spirit
                    && (self.entities[j].hidden
                        || self.entities[j].underground
                        || self.entities[j].stagger > 1e-9
                        || self.entities[j].death_immunity.is_some()
                        || self.entities[j].stealth_until > self.tick * 50
                        || (self.entities[i].stats.projectile_speed > 0
                            && !self.entities[i].attacked_current
                            && self.pending_lethal(j)))
                {
                    self.entities[i].moving = false;
                    self.apply_external(i, external);
                    continue;
                }
                if !self.entities[i].moving {
                    self.entities[i].charge = 0;
                    self.entities[i].public_speed_base = Some(self.entities[i].stats.speed as f64);
                    self.entities[i].force_due = false;
                    self.entities[i].clock.stop();
                }
                self.move_one(i, j, &occupied, external, &cells, &signatures);
            } else {
                self.note_stopped_route(i);
                self.entities[i].charge = 0;
                self.entities[i].public_speed_base = Some(self.entities[i].stats.speed as f64);
                self.entities[i].force_due = false;
                self.entities[i].moving = false;
                self.entities[i].route.clear();
                self.entities[i].goal = None;
                self.apply_external(i, external);
            }
        }
        for i in 0..n {
            let e = &mut self.entities[i];
            if e.alive && e.class == "Building" && e.deploy <= 0.0 && e.stats.lifetime > 0 {
                e.decay_work += 5000 * e.stats.max_hp.round_ties_even() as i64 / e.stats.lifetime;
                e.hp = (e.hp - (e.decay_work / 100) as f64).max(0.0);
                e.decay_work %= 100;
                if e.hp == 0.0 {
                    e.alive = false;
                    let source = e.clone();
                    self.death_effects(source);
                }
            }
        }
        for i in 0..n {
            if !self.entities[i].spirit
                && (self.entities[i].class == "Troop" || self.entities[i].class == "Building")
            {
                self.periodic_tick(i);
            }
        }
        for e in &mut self.entities[..n] {
            if e.alive && !e.spirit && (e.class == "Troop" || e.class == "Building") {
                for haste in &mut e.hastes { haste.0 -= 0.05; }
                e.hastes.retain(|haste| haste.0 > 1e-9);
                for slow in &mut e.area_slows {
                    slow.0 -= 0.05;
                }
                e.area_slows.retain(|slow| slow.0 > 1e-9);
                e.slow_ms = (e.slow_ms - 50).max(0);
                e.freeze_pause = (e.freeze_pause - 0.05).max(0.0);
                if e.freeze_pause <= 1e-9 {
                    e.freeze_pause = 0.0;
                }
                e.stun = (e.stun - 0.05).max(0.0);
                if e.stun <= 1e-9 {
                    e.stun = 0.0;
                }
            }
        }
        capture!("movement");
        for cast in std::mem::take(&mut self.pending_casts) {
            let spell = self.config.cards[&cast.name].spell.clone().unwrap();
            self.direct_spell(&cast, &spell, None);
        }
        let mut projectile_alive: Option<std::collections::BTreeSet<i32>> = None;
        let mut object_indices: Vec<usize> = (0..n).collect();
        object_indices.sort_by_key(|&i| {
            (
                if self.entities[i].scope.is_some()
                    || self.entities[i].class == "AreaEffect"
                    || self.entities[i].class == "RankedStrikeArea"
                    || self.entities[i].class == "ChainLightning"
                    || self.entities[i].class == "TimedExplosive"
                {
                    0
                } else if self.entities[i].class == "Projectile"
                    || self.entities[i].class == "SpawnProjectile"
                    || self.entities[i].spirit
                {
                    1
                } else {
                    2
                },
                self.entities[i].id,
            )
        });
        for i in object_indices {
            if !self.entities[i].alive {
                continue;
            }
            if self.entities[i].scope.is_some() {
                self.scope_tick(i);
            } else if self.entities[i].spirit {
                if self.entities[i].spirit_launch < self.tick {
                    self.spirit_tick(i);
                }
            } else if self.entities[i].class == "AreaEffect" {
                if self.entities[i].spell_name.is_empty() {
                    self.area_tick(i);
                } else {
                    self.c56_area_tick(i);
                }
            } else if self.entities[i].class == "RankedStrikeArea" {
                self.ranked_strike_tick(i);
            } else if self.entities[i].class == "ChainLightning" {
                self.chain_tick(i);
            } else if self.entities[i].class == "TimedExplosive" {
                self.bomb_tick(i);
            } else if self.entities[i].class == "RollingProjectile" {
                if self.entities[i].spell_name.is_empty() { self.rolling_character_tick(i); }
                else { self.rolling_tick(i); }
            } else if self.entities[i].class == "SpawnProjectile" {
                self.delivery_tick(i);
            } else if self.entities[i].class == "Projectile" {
                if projectile_alive.is_none() {
                    projectile_alive = Some(self.entities.iter().filter(|e| e.alive).map(|e| e.id).collect());
                }
                if self.entities[i].piercing {
                    self.piercing_tick(i);
                    continue;
                }
                let mut dt = 0.05;
                if self.entities[i].launch_delay > 0.0 {
                    if dt <= self.entities[i].launch_delay + 1e-12 {
                        self.entities[i].launch_delay =
                            (self.entities[i].launch_delay - dt).max(0.0);
                        continue;
                    }
                    dt -= self.entities[i].launch_delay;
                    self.entities[i].launch_delay = 0.0;
                }
                let temporary = self.projectile_homing(i);
                let target_index = self.entities[i].shot_target.and_then(|id| self.index(id));
                if let Some(j) =
                    target_index.filter(|_| self.entities[i].stats.homing.unwrap_or(true))
                {
                    if !temporary { self.entities[i].aim = (self.entities[j].x, self.entities[j].y); }
                }
                {
                    let (dx, dy) = (
                        units(self.entities[i].aim.0 - self.entities[i].x),
                        units(self.entities[i].aim.1 - self.entities[i].y),
                    );
                    let d = isqrt(dx * dx + dy * dy);
                    let speed = (self.entities[i].stats.speed as f64 * (dt / 0.05))
                        .round_ties_even() as i64;
                    if d <= speed {
                        let damage = self.entities[i].stats.damage;
                        if !self.entities[i].spell_name.is_empty() {
                            let name = self.entities[i].spell_name.clone();
                            let spell = self.config.cards[&name].spell.clone().unwrap();
                            let cast = Cast {
                                player: self.entities[i].owner as usize,
                                name,
                                x: self.entities[i].aim.0,
                                y: self.entities[i].aim.1,
                            };
                            self.grouped_spell(
                                &cast,
                                &spell,
                                Some((self.entities[i].x, self.entities[i].y)),
                                self.entities[i].damage_group,
                            );
                        } else if self.entities[i].stats.projectile_radius > 0.0 {
                            let shot = &self.entities[i];
                            let victims: Vec<usize> = self
                                .entities
                                .iter()
                                .enumerate()
                                .filter_map(|(j, e)| {
                                    (e.alive
                                        && !e.hidden
                                        && !e.spirit
                                        && !e.underground
                                        && e.stagger <= 1e-9
                                        && e.owner != shot.owner
                                        && (!shot.source_character || e.death_immunity.is_none())
                                        && (e.class == "Troop" || e.class == "Building")
                                        && shot.can_hit_plane(e)
                                        && Self::in_area(
                                            e,
                                            shot.aim.0,
                                            shot.aim.1,
                                            shot.stats.projectile_radius,
                                        ))
                                    .then_some(j)
                                })
                                .collect();
                            for j in victims {
                                self.damage(j, damage);
                            }
                            self.projectile_splash_status(i);
                        } else if let Some(j) = target_index {
                            let shot = &self.entities[i];
                            let target = &self.entities[j];
                            let ground_jumper = target.jump.is_some() && shot.stats.can_ground.unwrap_or(true);
                            if !target.hidden && (shot.can_hit_plane(target) || ground_jumper) {
                                self.damage(j, damage);
                                self.projectile_status(i, j);
                                if projectile_alive.as_ref().unwrap().contains(&self.entities[j].id) { self.dragon_chain_hit(i, j); }
                            }
                        } else if self.entities[i].shot_target.is_none() {
                            // A shot created after its target died has no primary
                            // target. Python performs a zero-radius endpoint query.
                            let shot = &self.entities[i];
                            let victims: Vec<usize> = self
                                .entities
                                .iter()
                                .enumerate()
                                .filter_map(|(j, e)| {
                                    (e.alive
                                        && e.owner != shot.owner
                                        && (!shot.source_character || e.death_immunity.is_none())
                                        && !e.hidden
                                        && !e.spirit
                                        && !e.underground
                                        && (e.class == "Troop" || e.class == "Building")
                                        && shot.can_hit_plane(e)
                                        && e.stagger <= 1e-9
                                        && Self::in_area(e, shot.aim.0, shot.aim.1, 0.0))
                                    .then_some(j)
                                })
                                .collect();
                            for j in victims {
                                self.damage(j, damage);
                            }
                            self.projectile_splash_status(i);
                        }
                        if self.entities[i].stats.child_count > 0 {
                            self.projectile_children(i);
                        }
                        self.entities[i].alive = false;
                    } else {
                        let (vx, vy) = norm(dx, dy, speed);
                        self.entities[i].x = (units(self.entities[i].x) + vx) as f64 / 1000.0;
                        self.entities[i].y = (units(self.entities[i].y) + vy) as f64 / 1000.0;
                    }
                }
            } else {
                let deploying = self.entities[i].deploy > 0.0;
                let e = &mut self.entities[i];
                e.tick_death_immunity();
                e.pending_ms = (e.pending_ms - 50).max(0);
                e.stagger = (e.stagger - 0.05).max(0.0);
                if e.deploy > 0.0 {
                    e.deploy = (e.deploy - 0.05).max(0.0);
                    if e.deploy < 1e-9 {
                        e.deploy = 0.0;
                        if e.underground {
                            e.x = units(e.tunnel_destination.0) as f64 / 1000.0;
                            e.y = units(e.tunnel_destination.1) as f64 / 1000.0;
                            e.underground = false;
                            if e.champion.is_some() {
                                let (x, y) = cell(e.x, e.y);
                                e.lane = self.config.lane_ids[(y * 36 + x) as usize];
                            }
                        }
                        if e.class == "Troop" && e.stun > 0.0 {
                            e.frozen_moving = true;
                        }
                    }
                } else {
                    e.age += 50;
                }
                if self.entities[i].deploy == 0.0 {
                    self.spawn_hook(i);
                    self.champion_object_tick(i);
                    self.hook_object_tick(i);
                    if self.entities[i].stats.spawner.is_some() {
                        self.production_tick(i);
                    }
                }
                if self.entities[i].deploy == 0.0 && self.entities[i].stats.hide_ms > 0 {
                    if deploying {
                        self.combat_one(i, &grid);
                    }
                    self.hide_tick(i);
                }
                if self.entities[i].deploy == 0.0 && self.entities[i].stats.ghost_fade > 0 {
                    self.ghost_tick(i);
                }
                if self.entities[i].deploy == 0.0 && self.entities[i].stats.collect_interval > 0.0 {
                    self.collector_tick(i);
                }
            }
        }
        let mut i = n;
        while i < self.entities.len() {
            if self.entities[i].class == "Troop" && self.entities[i].alive {
                let e = &mut self.entities[i];
                e.tick_death_immunity();
                e.pending_ms = (e.pending_ms - 50).max(0);
                e.stagger = (e.stagger - 0.05).max(0.0);
                if e.deploy > 0.0 {
                    e.deploy = (e.deploy - 0.05).max(0.0);
                    if e.deploy < 1e-9 {
                        e.deploy = 0.0;
                        if e.stun > 0.0 {
                            e.frozen_moving = true;
                        }
                    }
                } else {
                    e.age += 50;
                }
            }
            if self.entities[i].scope.is_some() && self.entities[i].alive {
                self.scope_tick(i);
            } else if self.entities[i].class == "ChainLightning" && self.entities[i].alive {
                self.chain_tick(i);
            } else if self.entities[i].class == "TimedExplosive" && self.entities[i].alive {
                self.bomb_tick(i);
            } else if self.entities[i].class == "RollingProjectile" && self.entities[i].alive && self.entities[i].spell_name.is_empty() {
                self.rolling_character_tick(i);
            }
            i += 1;
        }
        // New homing reservations publish after character object timers.
        for i in 0..self.entities.len() {
            if !((i >= n
                && self.entities[i].class == "Projectile"
                && self.entities[i].stats.homing.unwrap_or(true))
                || (self.entities[i].spirit
                    && !self.entities[i].stats.electro_chain
                    && self.entities[i].spirit_launch == self.tick))
            {
                continue;
            }
            if let Some(j) = self.entities[i].shot_target.and_then(|id| self.index(id)) {
                let (dx, dy) = (
                    units(self.entities[j].x - self.entities[i].x),
                    units(self.entities[j].y - self.entities[i].y),
                );
                let speed = if self.entities[i].spirit {
                    self.entities[i].stats.spirit_speed
                } else {
                    self.entities[i].stats.speed
                };
                let duration = isqrt(dx * dx + dy * dy) * 50 / speed;
                self.entities[j].pending_ms = self.entities[j]
                    .pending_ms
                    .max(((duration + 49) / 50 * 50).min(1000));
            }
        }
        capture!("objects");
        let dead: Vec<i32> = self
            .entities
            .iter()
            .filter(|e| !e.alive || e.spirit)
            .map(|e| e.id)
            .collect();
        for e in &mut self.entities {
            if e.alive && e.target.is_some_and(|id| dead.contains(&id)) {
                e.target = None;
                e.move_target = None;
                if e.clock_initialized { e.clock_reseed = None; }
                if e.pending_lethal {
                    e.last_target = None;
                    e.pending_lethal = false;
                    e.resume_pending = true;
                    e.started = false;
                    e.windup = false;
                    e.clock.finish = 0;
                } else if e.stats.finish_allowed.unwrap_or(true)
                    && if !e.stats.ordinary {
                        e.started
                    } else {
                        e.clock.timeline > 0
                    }
                {
                    e.clock.finish = 1;
                } else {
                    e.clock.stop();
                    e.started = false;
                    e.windup = false;
                }
            }
        }
        let wake: Vec<i32> = self
            .entities
            .iter()
            .filter(|e| !e.alive && e.class == "Building" && e.stats.name == "Tower")
            .map(|e| e.owner)
            .collect();
        for owner in wake {
            self.activate_king(owner);
        }
        let removed_positions: BTreeMap<i32, (f64, f64)> = self
            .entities
            .iter()
            .filter(|e| !e.alive)
            .map(|e| (e.id, (e.x, e.y)))
            .collect();
        for e in &mut self.entities {
            if let Some(position) = e.temporary_target.and_then(|id| removed_positions.get(&id)) {
                e.temporary_aim = *position;
            }
            if e.class == "Projectile" && e.stats.homing.unwrap_or(true) {
                if let Some(position) = e.shot_target.and_then(|id| removed_positions.get(&id)) {
                    e.aim = *position;
                }
            }
        }
        self.remember_cursed_dead();
        self.refresh_dead_champions();
        self.entities.retain(|e| e.alive);
        capture!("cleanup");
        let kings = [0, 1].map(|owner| {
            self.entities
                .iter()
                .any(|e| e.class == "Building" && e.king && e.owner == owner)
        });
        if !kings[0] || !kings[1] {
            self.game_over = true;
            self.winner = match kings {
                [true, false] => Some(0),
                [false, true] => Some(1),
                _ => None,
            };
        }
        if !self.game_over && self.tick > 3600 {
            self.sudden_death = true;
            let crowns = [0, 1].map(|owner| {
                self.entities
                    .iter()
                    .filter(|e| {
                        e.alive
                            && e.owner == owner
                            && e.class == "Building"
                            && e.stats.name == "Tower"
                    })
                    .count()
            });
            if crowns[0] != crowns[1] {
                self.game_over = true;
                self.winner = Some(if crowns[0] > crowns[1] { 0 } else { 1 });
            } else if self.tick > 6000 {
                let lowest = [0, 1].map(|owner| {
                    self.entities
                        .iter()
                        .filter(|e| {
                            e.alive
                                && e.owner == owner
                                && e.class == "Building"
                                && (e.king || e.stats.name == "Tower")
                        })
                        .map(|e| e.hp)
                        .fold(f64::INFINITY, f64::min)
                });
                self.game_over = true;
                self.winner = if lowest[0] == lowest[1] {
                    None
                } else {
                    Some(if lowest[0] > lowest[1] { 0 } else { 1 })
                };
            }
        }
        capture!("complete");
        phases
    }
    fn activate_king(&mut self, owner: i32) {
        for e in &mut self.entities {
            if e.king && e.owner == owner && !e.active {
                e.active = true;
                e.activation_remaining = e.stats.activation;
                e.activation_hit_remaining = e.stats.activation_hit;
            }
        }
    }
    fn damage(&mut self, j: usize, amount: f64) {
        let e = &mut self.entities[j];
        if e.stagger > 1e-9 || e.spirit || e.underground
            || e.dash_travel() || e.dash.as_ref().is_some_and(|s| self.tick*50 < s.immunity) {
            return;
        }
        if e.shield > 0.0 {
            e.shield = (e.shield - amount).max(0.0);
            if e.shield == 0.0 {
                let id = e.id;
                for beam in &mut self.entities {
                    if !beam.stats.ramp_stages.is_empty()
                        && beam.target == Some(id)
                        && beam.ramp_target == Some(id)
                    {
                        beam.ramp_time = 0.0;
                        beam.stats.damage = beam.stats.ramp_stages[0].1;
                    }
                }
            }
            return;
        }
        let was_alive = e.alive;
        e.hp = (e.hp - amount).max(0.0);
        let wake = if e.king && amount > 0.0 {
            Some(e.owner)
        } else {
            None
        };
        if e.hp == 0.0 {
            e.alive = false;
        }
        let death = was_alive
            && !e.alive
            && (e.stats.collect_death > 0.0
                || e.stats.death_damage > 0.0
                || self.config.death_objects.contains_key(e.stats.key())
                || self.config.death_areas.contains_key(e.stats.key())
                || self.config.death_children.contains_key(e.stats.key())
                || e.souls_collected > 0);
        let died = was_alive && !e.alive;
        let source = if death { Some(e.clone()) } else { None };
        if died {
            self.hook_cancel(j);
            self.champion_death(j);
        }
        if let Some(owner) = wake {
            self.activate_king(owner);
        }
        if let Some(source) = source {
            self.death_effects(source);
        }
    }
    fn death_effects(&mut self, source: Entity) {
        self.drop_souls(&source);
        if source.stats.collect_death > 0.0 && !self.game_over {
            let p = &mut self.players[source.owner as usize];
            p.elixir = (p.elixir + source.stats.collect_death).min(10.0);
        }
        let victims: Vec<usize> = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(k, e)| {
                (source.stats.death_damage > 0.0
                    && e.death_immunity.is_none()
                    && e.alive
                    && !e.spirit
                    && !e.underground
                    && e.owner != source.owner
                    && (e.class == "Troop" || e.class == "Building")
                    && e.stagger <= 1e-9
                    && !e.hidden
                    && Self::in_area(e, source.x, source.y, source.stats.death_radius))
                .then_some(k)
            })
            .collect();
        for k in victims {
            self.damage(k, source.stats.death_damage);
            self.radial_knockback(
                k,
                (source.x, source.y),
                source.stats.death_knockback,
                false,
                false,
                None,
            );
        }
        if let Some(templates) = self.config.death_children.get(source.stats.key()).cloned() {
            self.spawn_death_templates(&source,templates);
        }
        if let Some(template) = self.config.death_areas.get(source.stats.key()) {
            let mut effect = template.clone();
            effect.id = self.next_id as i32;
            self.next_id += 1;
            effect.x = source.x;
            effect.y = source.y;
            effect.owner = source.owner;
            effect.birth = self.tick;
            self.entities.push(effect);
        }
        if let Some(template) = self.config.death_objects.get(source.stats.key()) {
            let mut effect = template.clone();
            effect.is_clone = source.is_clone;
            effect.id = self.next_id as i32;
            self.next_id += 1;
            effect.x = source.x;
            effect.y = source.y;
            effect.owner = source.owner;
            effect.facing = source.facing;
            effect.birth = self.tick;
            self.entities.push(effect);
        }
    }
    fn spawn_death_templates(&mut self, source: &Entity, templates: Vec<Entity>) {
            let count = templates.len();
            for (index, mut child) in templates.into_iter().enumerate() {
                Self::clone_payload(&mut child, source);
                let target = if source.stats.death_zero_count > 0 {
                    let (x, y) = self.child_position_without_radius(
                        &source, &child, source.stats.death_zero_count == 1,
                    );
                    (x.clamp(250, 17750) as f64 / 1000.0,
                     y.clamp(250, 31750) as f64 / 1000.0)
                } else if source.stats.death_spawn_radius > 0.0 {
                    let base = if source.stats.death_spawn_angle!=0 {
                        self.vector_angle(source.facing.0,source.facing.1)+source.stats.death_spawn_angle
                    } else {0};
                    let angle = (base
                        + ((count - 1 - index) * 360 / count) as i64).rem_euclid(360);
                    let (cos, sin) = self.config.rotations[angle as usize];
                    let radius = units(source.stats.death_spawn_radius);
                    let mut dx=cos*radius/1024;let mut dy=sin*radius/1024;
                    if source.stats.death_spawn_const {
                        let (x,y)=cell(source.x,source.y);
                        if self.config.lane_ids[(y*36+x) as usize]==1 {dx=-dx;}
                        if source.owner==1 {dy=-dy;}
                    }
                    ((units(source.x) + dx).clamp(250, 17750) as f64 / 1000.0,
                     (units(source.y) + dy).clamp(250, 31750) as f64 / 1000.0)
                } else { (
                    (units(source.x + child.x).clamp(250, 17750)) as f64 / 1000.0,
                    (units(source.y + child.y).clamp(250, 31750)) as f64 / 1000.0,
                ) };
                child.id = self.next_id as i32;
                self.next_id += 1;
                child.owner = source.owner;
                child.lane = if target.0 < 9.0 { 1 } else { 2 };
                let radial = child.death_travel.is_some();
                child.x = if radial { source.x } else { target.0 };
                child.y = if radial { source.y } else { target.1 };
                child.facing = (0, if source.owner == 0 { 1000 } else { -1000 });
                let (dx, dy) = (units(target.0 - source.x), units(target.1 - source.y));
                child.death_ticks = if radial {
                    isqrt(dx * dx + dy * dy) / 250
                } else {
                    0
                };
                child.death_travel = (child.death_ticks > 0).then_some(target);
                child.birth = self.tick;
                let inherit = child.deploy <= 0.0 || source.freeze_carrier;
                self.entities.push(child);
                if inherit {
                    self.freeze_until(self.entities.len() - 1, source.freeze_expiry);
                }
            }
    }
    fn hex_digest(&self) -> String {
        // Exactly es_common.battle_digest's binary packing and Python repr fields.
        let mut h = Sha256::new();
        h.update((self.tick as i32).to_le_bytes());
        h.update(self.next_id.to_le_bytes());
        for p in &self.players {
            h.update(p.elixir.to_le_bytes());
            h.update(py_tuple(p.hand.iter().map(|v| v.as_deref())));
            h.update(py_tuple(p.cycle.iter().map(|v| Some(v.as_str()))));
        }
        for e in &self.entities {
            h.update(e.id.to_le_bytes());
            h.update(e.owner.to_le_bytes());
            h.update(e.x.to_le_bytes());
            h.update(e.y.to_le_bytes());
            h.update(e.hp.to_le_bytes());
            h.update([e.alive as u8]);
            h.update(e.class.as_bytes());
            h.update(
                e.target
                    .map(|v| v.to_string())
                    .unwrap_or_else(|| "None".into()),
            );
        }
        let winner = self
            .winner
            .map(|v| v.to_string())
            .unwrap_or_else(|| "None".into());
        h.update(format!(
            "({}, {})",
            if self.game_over { "True" } else { "False" },
            winner
        ));
        h.update(format!(
            "({}, {}, {}, {})",
            self.rng.state[0], self.rng.state[1], self.rng.state[2], self.rng.state[3]
        ));
        format!("{:x}", h.finalize())
    }
}
fn py_tuple<'a>(items: impl Iterator<Item = Option<&'a str>>) -> String {
    let v: Vec<String> = items
        .map(|v| v.map(|s| format!("'{s}'")).unwrap_or_else(|| "None".into()))
        .collect();
    format!("({}{})", v.join(", "), if v.len() == 1 { "," } else { "" })
}

#[pymethods]
impl BattleState {
    #[new]
    fn new(snapshot: &str) -> PyResult<Self> {
        let s: Self =
            serde_json::from_str(snapshot).map_err(|e| PyValueError::new_err(e.to_string()))?;
        if s.config.costs.len() != 2304
            || s.config.water.len() != 2304
            || s.rng.state.len() != 624
            || s.rng.index > 624
        {
            return Err(PyValueError::new_err("invalid arena/RNG snapshot"));
        }
        Ok(s)
    }
    #[pyo3(signature=(ticks=1))]
    fn step(&mut self, ticks: usize) {
        for _ in 0..ticks {
            self.tick_once(false);
        }
    }
    #[pyo3(name = "clone")]
    fn py_clone(&self) -> Self {
        Clone::clone(self)
    }
    /// Import unslowed public speed modes without changing native movement work.
    fn set_public_movement_speeds(&mut self, speeds: Vec<(i32, f64)>) -> PyResult<()> {
        for (id, speed) in speeds {
            if !speed.is_finite() || speed < 0.0 {
                return Err(PyValueError::new_err("invalid public movement speed"));
            }
            let j = self
                .index(id)
                .ok_or_else(|| PyValueError::new_err("unknown entity"))?;
            self.entities[j].public_speed_base = Some(speed);
        }
        Ok(())
    }
    fn debug_step(&mut self) -> String {
        serde_json::to_string(&self.tick_once(true)).unwrap()
    }
    fn digest(&self) -> String {
        self.hex_digest()
    }
    fn snapshot(&self) -> String {
        serde_json::to_string(self).unwrap()
    }
    fn rng_state(&self) -> (Vec<u32>, usize) {
        (self.rng.state.clone(), self.rng.index)
    }
    fn rng_u32(&mut self) -> u32 {
        self.rng.next()
    }
    fn rng_random(&mut self) -> f64 {
        self.rng.random()
    }
    fn rng_below(&mut self, n: u32) -> PyResult<u32> {
        if n == 0 {
            Err(PyValueError::new_err("n must be positive"))
        } else {
            Ok(self.rng.below(n))
        }
    }
    fn can_activate_champion_ability(&mut self, player: usize) -> bool {
        self.champion_can_activate(player)
    }
    fn activate_champion_ability(&mut self, player: usize) -> bool {
        self.champion_activate(player)
    }
    fn apply_action(&mut self, player: usize, card: &str, x: f64, y: f64) -> PyResult<bool> {
        let config = Arc::clone(&self.config);
        let c = config.cards.get(card).ok_or_else(|| {
            PyValueError::new_err("unsupported card absent from imported pilot configuration")
        })?;
        if player > 1
            || !x.is_finite()
            || !y.is_finite()
            || x < 0.5
            || x > 17.5
            || y < 0.5
            || y > 31.5
        {
            return Err(PyValueError::new_err("invalid player/position"));
        }
        if self.game_over {
            return Ok(false);
        }
        let mirror = c.mirror;
        let effective_name = if mirror {
            let Some(name) = &self.players[player].last_card else { return Ok(false); };
            format!("level12:{name}")
        } else { card.to_owned() };
        let c = match config.cards.get(&effective_name) {
            Some(payload) => payload,
            None if mirror => return Ok(false),
            None => return Err(PyValueError::new_err("missing card payload")),
        };
        let cost = if mirror {
            let Some(previous) = self.players[player].last_cost else { return Ok(false); };
            previous + 1.0
        } else { c.cost };
        if x.floor() < c.margin as f64 || x.floor() >= (18 - c.margin) as f64 {
            return Ok(false);
        }
        if c.spell.is_some() {
            if c.spell.as_ref().unwrap().requires_territory && !self.can_deploy(player, x, y, true)
            {
                return Ok(false);
            }
            if self.config.blocked_tiles[(y as usize) * 18 + x as usize] {
                return Ok(false);
            }
        } else if !(if c.anywhere {
            self.can_deploy_anywhere(x, y)
        } else {
            self.can_deploy(player, x, y, false)
        }) {
            return Ok(false);
        }
        if c.spell.is_none()
            && c.footprint == 0
            && self.payload_blocked(x, y, c.units[player][0].stats.radius, None)
        {
            return Ok(false);
        }
        let requested_x = x;
        if c.spell.is_none() && !c.units[player].first().is_some_and(|e| e.stats.air) {
            self.prepare_placement_mask(if c.footprint > 0 { c.footprint } else { 1 });
        }
        let (x, y) = if c.spell.is_some() {
            (x, y)
        } else if c.footprint > 0 {
            let offset = if c.footprint % 2 == 1 { 0.5 } else { 0.0 };
            let anchor = (x.floor() + offset, y.floor() + offset);
            let anchor = if c.anchors.contains(&anchor) {
                anchor
            } else {
                *c.anchors
                    .iter()
                    .min_by(|a, b| {
                        let da = (a.0 - x).powi(2) + (a.1 - y).powi(2);
                        let db = (b.0 - x).powi(2) + (b.1 - y).powi(2);
                        da.total_cmp(&db)
                            .then(b.0.total_cmp(&a.0))
                            .then(b.1.total_cmp(&a.1))
                    })
                    .unwrap()
            };
            if self.payload_blocked(anchor.0, anchor.1, 0.0, Some(c.footprint as f64 / 2.0))
                || self.entities.iter().any(|e| {
                    let size = (e.stats.radius * 2.0).ceil() + 1.0;
                    e.alive
                        && e.class == "Building"
                        && (anchor.0 - e.x).abs() < (size + c.footprint as f64) / 2.0
                        && (anchor.1 - e.y).abs() < (size + c.footprint as f64) / 2.0
                })
            {
                return Ok(false);
            }
            anchor
        } else if c.units[player].first().is_some_and(|e| e.stats.air) {
            let radius = c.units[player][0].stats.radius.min(0.5);
            if self.entities.iter().any(|e| {
                e.alive
                    && e.class == "Building"
                    && units(x - e.x).pow(2) + units(y - e.y).pow(2)
                        < units(radius + e.stats.radius).pow(2)
            }) {
                return Ok(false);
            }
            (x, y)
        } else {
            match self.troop_anchor(player, x, y, c.units[player][0].stats.radius, c.anywhere) {
                Some(p) => p,
                None => return Ok(false),
            }
        };
        let edge = if c.spell.is_none()
            && !c.anywhere
            && c.footprint == 0
            && !c.units[player].first().is_some_and(|e| e.stats.air)
        {
            let column = x.floor() as usize;
            (0..32usize)
                .map(|k| if player == 0 { 31 - k } else { k })
                .find(|&row| {
                    let (cx, cy) = (column as f64 + 0.5, row as f64 + 0.5);
                    self.config.walkable[row * 18 + column]
                        && self.can_deploy(player, cx, cy, false)
                        && !self.footprint_blocked(cx, cy, 1.0)
                })
                .map(|row| row as f64 + 0.5 - if player == 1 && !c.units[player][0].stats.skip_deploy_snap { 0.001 } else { 0.0 })
        } else {
            None
        };
        let p = &mut self.players[player];
        let slot = p.hand.iter().position(|n| n.as_deref() == Some(card));
        if p.elixir + 1e-9 < cost || slot.is_none() {
            return Ok(false);
        }
        p.elixir = (p.elixir - cost).max(0.0);
        p.hand[slot.unwrap()] = None;
        p.cycle.push_back(card.into());
        if !mirror {
            p.last_card = Some(card.into());
            p.last_cost = Some(cost);
        }
        if let Some(spell) = &c.spell {
            if spell.name == "Clone" {
                self.clone_spell(&Cast { player, name: card.into(), x, y }, spell);
                return Ok(true);
            }
            if spell.travel_speed > 0.0 {
                if spell.multiple_projectiles.unwrap_or(1) > 1 {
                    let volley = c.clone();
                    self.projectile_volley(&volley, player, x, y);
                    return Ok(true);
                }
                for template in &c.units[player] {
                    let mut e = template.clone();
                    e.id = self.next_id as i32;
                    self.next_id += 1;
                    if e.class == "RollingProjectile"
                        || (e.class == "SpawnProjectile" && spell.impact_delay > 0.0)
                    {
                        e.x = x;
                        e.y = y;
                    }
                    e.aim = (x, y);
                    e.birth = self.tick;
                    self.entities.push(e);
                }
            } else if !c.units[player].is_empty() {
                for template in &c.units[player] {
                    let mut e = template.clone();
                    e.id = self.next_id as i32;
                    self.next_id += 1;
                    e.x = x;
                    e.y = y;
                    e.birth = self.tick;
                    self.entities.push(e);
                }
            } else {
                self.pending_casts.push(Cast {
                    player,
                    name: effective_name,
                    x,
                    y,
                });
            }
            return Ok(true);
        }
        let recruits = if c.recruits_line {
            Some(self.recruit_positions(
                x - if requested_x < 9.0 { 0.001 } else { 0.0 },
                y - if player == 1 { 0.001 } else { 0.0 },
                player, c.units[player].len(),
            ))
        } else { None };
        for (unit_index, template) in c.units[player].iter().enumerate() {
            let mut e = template.clone();
            e.id = self.next_id as i32;
            self.next_id += 1;
            let offset_x = units(template.x)
                * if x < 9.0 || !c.mirror_x.unwrap_or(true) {
                    1
                } else {
                    -1
                };
            e.x = (units(x) + offset_x
                - if requested_x < 9.0 && c.footprint == 0 && !e.stats.air && !e.stats.skip_deploy_snap {
                    1
                } else {
                    0
                }) as f64
                / 1000.0;
            e.y = (units(y) + units(template.y)
                - if player == 1 && c.footprint == 0 && !e.stats.air && !e.stats.skip_deploy_snap {
                    1
                } else {
                    0
                }) as f64
                / 1000.0;
            if let Some(positions) = &recruits {
                (e.x, e.y) = positions[unit_index];
            }
            let lane_x = if recruits.is_some() {
                units(e.x) + if requested_x < 9.0 { 1 } else { 0 }
            } else { units(x) + offset_x };
            if let Some(edge) = edge {
                e.y = if player == 0 {
                    e.y.min(edge)
                } else {
                    e.y.max(edge)
                };
            }
            e.x = e.x.clamp(0.25, 17.75);
            e.y = e.y.clamp(0.25, 31.75);
            if recruits.is_some() {
                (e.x, e.y) = self.snap_child(e.x, e.y, player);
                e.x = units(e.x) as f64 / 1000.0;
                e.y = units(e.y) as f64 / 1000.0;
            }
            e.lane = if lane_x < 9000 { 1 } else { 2 };
            e.birth = self.tick;
            if e.stats.tunnel_speed > 0 && e.underground {
                e.tunnel_destination = (e.x, e.y);
                let (dx, dy) = (
                    units(e.x - e.tunnel_origin.0),
                    units(e.y - e.tunnel_origin.1),
                );
                e.tunnel_duration = c56::tunnel_duration(
                    isqrt(dx * dx + dy * dy),
                    e.stats.tunnel_speed,
                    e.stats.tunnel_reached_from_speed,
                );
                e.deploy = e.tunnel_duration + e.stats.tunnel_emergence;
                e.tunnel_total = e.deploy;
                e.x = e.tunnel_origin.0;
                e.y = e.tunnel_origin.1;
                e.underground = e.deploy > 1e-9;
            }
            self.bind_champion(&mut e);
            self.entities.push(e);
        }
        Ok(true)
    }
}

#[pyfunction]
fn route(
    costs: Vec<i64>,
    start: (i32, i32),
    goal: (i32, i32),
) -> PyResult<Option<Vec<(i32, i32)>>> {
    if costs.len() != 2304
        || [start, goal]
            .iter()
            .any(|&(x, y)| !(0..36).contains(&x) || !(0..64).contains(&y))
    {
        return Err(PyValueError::new_err("invalid route input"));
    }
    Ok(astar::find(&costs, start, goal))
}
#[pymodule]
fn clasher_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BattleState>()?;
    m.add_class::<scripts::NativeScripts>()?;
    m.add_function(wrap_pyfunction!(route, m)?)?;
    Ok(())
}
