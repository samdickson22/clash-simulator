use pyo3::exceptions::{PyIndexError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::collections::VecDeque;

const FNV_OFFSET_BASIS: u64 = 0xcbf29ce484222325;
const FNV_PRIME: u64 = 0x100000001b3;

fn fnv1a(payload: &[u8]) -> u64 {
    payload.iter().fold(FNV_OFFSET_BASIS, |hash, byte| {
        (hash ^ u64::from(*byte)).wrapping_mul(FNV_PRIME)
    })
}

#[pyfunction]
fn noop_ticks(ticks: u32) -> u32 {
    ticks
}

#[pyfunction]
fn consume_state_bytes(payload: &[u8]) -> (usize, u64) {
    (payload.len(), fnv1a(payload))
}

fn sha256_hex(payload: &[u8]) -> String {
    format!("{:x}", Sha256::digest(payload))
}

fn validate_checkpoint(payload: &[u8]) -> PyResult<u64> {
    let root: Value = serde_json::from_slice(payload)
        .map_err(|error| PyValueError::new_err(format!("invalid battle checkpoint: {error}")))?;
    let schema_version = root
        .get("schema_version")
        .and_then(Value::as_u64)
        .ok_or_else(|| PyValueError::new_err("battle checkpoint has no integer schema_version"))?;
    if schema_version != 2 {
        return Err(PyValueError::new_err(format!(
            "unsupported battle checkpoint schema {schema_version}; expected 2"
        )));
    }
    Ok(schema_version)
}

fn object_fields(value: &Value) -> PyResult<&Map<String, Value>> {
    value
        .get("$object")
        .and_then(|object| object.get("fields"))
        .and_then(Value::as_object)
        .ok_or_else(|| PyValueError::new_err("checkpoint object has no normalized fields"))
}

fn object_type(value: &Value) -> PyResult<String> {
    value
        .get("$object")
        .and_then(|object| object.get("type"))
        .and_then(Value::as_str)
        .map(str::to_owned)
        .ok_or_else(|| PyValueError::new_err("checkpoint object has no normalized type"))
}

fn required_i64(fields: &Map<String, Value>, name: &str) -> PyResult<i64> {
    fields
        .get(name)
        .and_then(Value::as_i64)
        .ok_or_else(|| PyValueError::new_err(format!("checkpoint field {name:?} is not an i64")))
}

fn required_bool(fields: &Map<String, Value>, name: &str) -> PyResult<bool> {
    fields
        .get(name)
        .and_then(Value::as_bool)
        .ok_or_else(|| PyValueError::new_err(format!("checkpoint field {name:?} is not a bool")))
}

#[derive(Clone)]
enum ExactScalar {
    Int(i64),
    Float(u64),
}

impl ExactScalar {
    fn from_normalized(value: &Value) -> PyResult<Self> {
        if let Some(integer) = value.as_i64() {
            return Ok(Self::Int(integer));
        }
        let encoded = value
            .get("$float")
            .and_then(Value::as_str)
            .ok_or_else(|| PyValueError::new_err("checkpoint scalar is not int or binary64"))?;
        Ok(Self::Float(parse_python_float_hex(encoded)?))
    }

    fn diagnostic_value(&self) -> Value {
        match self {
            Self::Int(value) => json!({"kind": "int", "value": value}),
            Self::Float(bits) => json!({
                "bits": format!("{bits:016x}"),
                "kind": "float"
            }),
        }
    }

    fn as_f64(&self) -> f64 {
        match self {
            Self::Int(value) => *value as f64,
            Self::Float(bits) => f64::from_bits(*bits),
        }
    }

    fn set_f64(&mut self, value: f64) {
        *self = Self::Float(value.to_bits());
    }
}

fn optional_position(fields: &Map<String, Value>, name: &str) -> PyResult<Option<(f64, f64)>> {
    let Some(value) = fields.get(name) else {
        return Ok(None);
    };
    if value.is_null() {
        return Ok(None);
    }
    let position = object_fields(value)?;
    Ok(Some((
        normalized_f64(position, "x")?,
        normalized_f64(position, "y")?,
    )))
}

fn normalized_f64(fields: &Map<String, Value>, name: &str) -> PyResult<f64> {
    ExactScalar::from_normalized(
        fields
            .get(name)
            .ok_or_else(|| PyValueError::new_err(format!("entity has no {name}")))?,
    )
    .map(|value| value.as_f64())
}

fn optional_normalized_f64(fields: &Map<String, Value>, name: &str) -> PyResult<Option<f64>> {
    let value = fields
        .get(name)
        .ok_or_else(|| PyValueError::new_err(format!("entity has no {name}")))?;
    if value.is_null() {
        Ok(None)
    } else {
        ExactScalar::from_normalized(value).map(|value| Some(value.as_f64()))
    }
}

#[derive(Clone)]
struct ModifierEffect {
    remaining: f64,
    movement: f64,
    attack: f64,
    spawn: f64,
}

impl ModifierEffect {
    fn from_normalized(value: &Value) -> PyResult<Self> {
        let values = value
            .get("$tuple")
            .and_then(Value::as_array)
            .ok_or_else(|| PyValueError::new_err("modifier effect is not a tuple"))?;
        if values.len() != 4 {
            return Err(PyValueError::new_err(
                "modifier effect must have four values",
            ));
        }
        Ok(Self {
            remaining: ExactScalar::from_normalized(&values[0])?.as_f64(),
            movement: ExactScalar::from_normalized(&values[1])?.as_f64(),
            attack: ExactScalar::from_normalized(&values[2])?.as_f64(),
            spawn: ExactScalar::from_normalized(&values[3])?.as_f64(),
        })
    }

    fn diagnostic_value(&self) -> Value {
        json!([
            exact_f64_value(self.remaining),
            exact_f64_value(self.movement),
            exact_f64_value(self.attack),
            exact_f64_value(self.spawn),
        ])
    }
}

fn exact_f64_value(value: f64) -> Value {
    json!({"bits": format!("{:016x}", value.to_bits()), "kind": "float"})
}

fn normalized_effects(fields: &Map<String, Value>, name: &str) -> PyResult<Vec<ModifierEffect>> {
    fields
        .get(name)
        .and_then(Value::as_array)
        .ok_or_else(|| PyValueError::new_err(format!("entity {name} is not a list")))?
        .iter()
        .map(ModifierEffect::from_normalized)
        .collect()
}

fn normalized_mapping_is_empty(fields: &Map<String, Value>, name: &str) -> PyResult<bool> {
    fields
        .get(name)
        .and_then(|value| value.get("$mapping"))
        .and_then(Value::as_array)
        .map(Vec::is_empty)
        .ok_or_else(|| PyValueError::new_err(format!("entity {name} is not a mapping")))
}

fn normalized_optional_number_is_nonzero(
    fields: &Map<String, Value>,
    name: &str,
) -> PyResult<bool> {
    let Some(value) = fields.get(name) else {
        return Ok(false);
    };
    if value.is_null() {
        return Ok(false);
    }
    Ok(ExactScalar::from_normalized(value)?.as_f64() != 0.0)
}

fn normalized_optional_bool(fields: &Map<String, Value>, name: &str) -> bool {
    fields.get(name).and_then(Value::as_bool).unwrap_or(false)
}

#[derive(Clone)]
struct ModifierState {
    stun_timer: f64,
    slow_timer: f64,
    slow_multiplier: f64,
    original_speed: Option<f64>,
    movement_mode_multiplier: f64,
    attack_speed_debuff_multiplier: f64,
    spawn_speed_debuff_multiplier: f64,
    attack_speed_buff_multiplier: f64,
    movement_speed_buff_multiplier: f64,
    spawn_speed_buff_multiplier: f64,
    haste_timer: f64,
    speed: ExactScalar,
    slow_effects: Vec<ModifierEffect>,
    haste_effects: Vec<ModifierEffect>,
}

impl ModifierState {
    fn from_fields(fields: &Map<String, Value>) -> PyResult<Self> {
        Ok(Self {
            stun_timer: normalized_f64(fields, "stun_timer")?,
            slow_timer: normalized_f64(fields, "slow_timer")?,
            slow_multiplier: normalized_f64(fields, "slow_multiplier")?,
            original_speed: optional_normalized_f64(fields, "original_speed")?,
            movement_mode_multiplier: normalized_f64(fields, "movement_mode_multiplier")?,
            attack_speed_debuff_multiplier: normalized_f64(
                fields,
                "attack_speed_debuff_multiplier",
            )?,
            spawn_speed_debuff_multiplier: normalized_f64(fields, "spawn_speed_debuff_multiplier")?,
            attack_speed_buff_multiplier: normalized_f64(fields, "attack_speed_buff_multiplier")?,
            movement_speed_buff_multiplier: normalized_f64(
                fields,
                "movement_speed_buff_multiplier",
            )?,
            spawn_speed_buff_multiplier: normalized_f64(fields, "spawn_speed_buff_multiplier")?,
            haste_timer: normalized_f64(fields, "haste_timer")?,
            speed: ExactScalar::from_normalized(
                fields
                    .get("speed")
                    .ok_or_else(|| PyValueError::new_err("entity has no speed"))?,
            )?,
            slow_effects: normalized_effects(fields, "_slow_effects")?,
            haste_effects: normalized_effects(fields, "_haste_effects")?,
        })
    }

    fn advance(&mut self, dt: f64) {
        if self.stun_timer > 0.0 {
            self.stun_timer = 0.0_f64.max(self.stun_timer - dt);
            if self.stun_timer <= 1e-9 {
                self.stun_timer = 0.0;
            }
        }

        if !self.slow_effects.is_empty() {
            for effect in &mut self.slow_effects {
                effect.remaining -= dt;
            }
            self.slow_effects.retain(|effect| effect.remaining > 1e-9);
            self.slow_timer = self
                .slow_effects
                .iter()
                .map(|effect| effect.remaining)
                .reduce(f64::max)
                .unwrap_or(0.0);
            self.slow_multiplier = self
                .slow_effects
                .iter()
                .map(|effect| effect.movement)
                .reduce(f64::min)
                .unwrap_or(1.0);
            self.attack_speed_debuff_multiplier = self
                .slow_effects
                .iter()
                .map(|effect| effect.attack)
                .reduce(f64::min)
                .unwrap_or(1.0);
            self.spawn_speed_debuff_multiplier = self
                .slow_effects
                .iter()
                .map(|effect| effect.spawn)
                .reduce(f64::min)
                .unwrap_or(1.0);
            if let Some(original_speed) = self.original_speed {
                let movement_debuff = self
                    .slow_multiplier
                    .max(0.0)
                    .min(self.movement_mode_multiplier.max(0.0));
                self.speed = ExactScalar::Float((original_speed * movement_debuff).to_bits());
            }
            if self.slow_effects.is_empty()
                && let Some(original_speed) = self.original_speed
            {
                self.speed =
                    ExactScalar::Float((original_speed * self.movement_mode_multiplier).to_bits());
                self.original_speed = None;
            }
        }

        if !self.haste_effects.is_empty() {
            for effect in &mut self.haste_effects {
                effect.remaining -= dt;
            }
            self.haste_effects.retain(|effect| effect.remaining > 1e-9);
            self.haste_timer = self
                .haste_effects
                .iter()
                .map(|effect| effect.remaining)
                .reduce(f64::max)
                .unwrap_or(0.0);
            self.movement_speed_buff_multiplier = self
                .haste_effects
                .iter()
                .map(|effect| effect.movement)
                .reduce(f64::max)
                .unwrap_or(1.0);
            self.attack_speed_buff_multiplier = self
                .haste_effects
                .iter()
                .map(|effect| effect.attack)
                .reduce(f64::max)
                .unwrap_or(1.0);
            self.spawn_speed_buff_multiplier = self
                .haste_effects
                .iter()
                .map(|effect| effect.spawn)
                .reduce(f64::max)
                .unwrap_or(1.0);
        } else if self.haste_timer > 0.0 {
            self.haste_timer = 0.0_f64.max(self.haste_timer - dt);
            if self.haste_timer <= 0.0 {
                self.movement_speed_buff_multiplier = 1.0;
                self.attack_speed_buff_multiplier = 1.0;
                self.spawn_speed_buff_multiplier = 1.0;
            }
        }
    }

    fn diagnostic_value(&self, id: i64, encounter_index: usize) -> Value {
        json!({
            "attack_speed_buff_multiplier": exact_f64_value(self.attack_speed_buff_multiplier),
            "attack_speed_debuff_multiplier": exact_f64_value(self.attack_speed_debuff_multiplier),
            "encounter_index": encounter_index,
            "haste_effects": self.haste_effects.iter().map(ModifierEffect::diagnostic_value).collect::<Vec<_>>(),
            "haste_timer": exact_f64_value(self.haste_timer),
            "id": id,
            "movement_mode_multiplier": exact_f64_value(self.movement_mode_multiplier),
            "movement_speed_buff_multiplier": exact_f64_value(self.movement_speed_buff_multiplier),
            "original_speed": self.original_speed.map(exact_f64_value),
            "slow_effects": self.slow_effects.iter().map(ModifierEffect::diagnostic_value).collect::<Vec<_>>(),
            "slow_multiplier": exact_f64_value(self.slow_multiplier),
            "slow_timer": exact_f64_value(self.slow_timer),
            "spawn_speed_buff_multiplier": exact_f64_value(self.spawn_speed_buff_multiplier),
            "spawn_speed_debuff_multiplier": exact_f64_value(self.spawn_speed_debuff_multiplier),
            "speed": self.speed.diagnostic_value(),
            "stun_timer": exact_f64_value(self.stun_timer),
        })
    }
}

fn parse_python_float_hex(encoded: &str) -> PyResult<u64> {
    match encoded {
        "inf" => return Ok(f64::INFINITY.to_bits()),
        "-inf" => return Ok(f64::NEG_INFINITY.to_bits()),
        "nan" => return Ok(f64::NAN.to_bits()),
        _ => {}
    }
    let (negative, unsigned) = encoded
        .strip_prefix('-')
        .map_or((false, encoded), |rest| (true, rest));
    let (mantissa, exponent_text) = unsigned
        .split_once('p')
        .ok_or_else(|| PyValueError::new_err(format!("invalid float.hex value {encoded:?}")))?;
    let exponent = exponent_text.parse::<i32>().map_err(|error| {
        PyValueError::new_err(format!("invalid float.hex exponent {encoded:?}: {error}"))
    })?;
    let mantissa = mantissa
        .strip_prefix("0x")
        .ok_or_else(|| PyValueError::new_err(format!("invalid float.hex prefix {encoded:?}")))?;
    let (integer_text, fraction_text) = mantissa
        .split_once('.')
        .ok_or_else(|| PyValueError::new_err(format!("invalid float.hex mantissa {encoded:?}")))?;
    if fraction_text.len() > 13 {
        return Err(PyValueError::new_err(format!(
            "float.hex fraction exceeds binary64 width {encoded:?}"
        )));
    }
    let integer = u64::from_str_radix(integer_text, 16).map_err(|error| {
        PyValueError::new_err(format!("invalid float.hex integer {encoded:?}: {error}"))
    })?;
    let mut fraction = u64::from_str_radix(fraction_text, 16).map_err(|error| {
        PyValueError::new_err(format!("invalid float.hex fraction {encoded:?}: {error}"))
    })?;
    fraction <<= 4 * (13 - fraction_text.len());
    let sign = u64::from(negative) << 63;
    if integer == 0 {
        if fraction == 0 {
            return Ok(sign);
        }
        if exponent != -1022 {
            return Err(PyValueError::new_err(format!(
                "invalid subnormal float.hex exponent {encoded:?}"
            )));
        }
        return Ok(sign | fraction);
    }
    if integer != 1 || !(-1022..=1023).contains(&exponent) {
        return Err(PyValueError::new_err(format!(
            "unsupported normalized float.hex value {encoded:?}"
        )));
    }
    let exponent_bits = u64::try_from(exponent + 1023).expect("validated exponent");
    Ok(sign | (exponent_bits << 52) | fraction)
}

#[derive(Clone)]
struct ResidentEntity {
    encounter_index: usize,
    id: i64,
    player_id: i64,
    entity_kind: i64,
    python_type: String,
    card_name: String,
    position_x: ExactScalar,
    position_y: ExactScalar,
    hitpoints: ExactScalar,
    max_hitpoints: ExactScalar,
    is_alive: bool,
    target_id: Option<i64>,
    deploy_delay_remaining: f64,
    placement_pending: bool,
    spawn_hook_pending: bool,
    spawn_hook_fired: bool,
    death_spawn_target_immunity_elapsed_ms: i64,
    mechanics: Vec<String>,
    modifier_state: Option<ModifierState>,
    modifier_supported: bool,
    direct_combat_unsupported: Vec<String>,
    locked_combat: Option<LockedDirectCombatState>,
}

#[derive(Clone)]
struct LockedDirectCombatState {
    damage: f64,
    range: f64,
    attack_cooldown: f64,
    attack_windup_active: bool,
    attack_preload_blocked: bool,
    last_attack_time: f64,
    stun_timer: f64,
    collision_radius: f64,
    native_target_distance_discount_sq_units: i64,
    is_air_unit: bool,
    can_attack_air: bool,
    can_attack_ground: bool,
    facing_x_units: i64,
    facing_y_units: i64,
    last_combat_target_id: Option<i64>,
    has_attacked_once: bool,
    movement_target_id: Option<i64>,
    initial_position: Option<(f64, f64)>,
    attack_speed_debuff_multiplier: f64,
    attack_speed_buff_multiplier: f64,
    attack_mode_multiplier: f64,
    hit_speed_ms: i64,
    first_hit_ms: i64,
    hidden_building: bool,
    stealth_until_ms: i64,
}

impl LockedDirectCombatState {
    fn from_fields(
        fields: &Map<String, Value>,
        card_fields: &Map<String, Value>,
    ) -> PyResult<Self> {
        let hit_speed_ms = card_fields
            .get("hit_speed")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let load_time_ms = card_fields
            .get("load_time")
            .and_then(Value::as_i64)
            .unwrap_or(0);
        let first_hit_ms = if load_time_ms > hit_speed_ms {
            hit_speed_ms
        } else {
            (hit_speed_ms - load_time_ms).max(0)
        };
        Ok(Self {
            damage: normalized_f64(fields, "damage")?,
            range: normalized_f64(fields, "range")?,
            attack_cooldown: normalized_f64(fields, "attack_cooldown")?,
            attack_windup_active: required_bool(fields, "_attack_windup_active")?,
            attack_preload_blocked: required_bool(fields, "_attack_preload_blocked")?,
            last_attack_time: normalized_f64(fields, "last_attack_time")?,
            stun_timer: normalized_f64(fields, "stun_timer")?,
            collision_radius: normalized_f64(fields, "_collision_radius")?,
            native_target_distance_discount_sq_units: required_i64(
                fields,
                "_native_target_distance_discount_sq_units",
            )?,
            is_air_unit: required_bool(fields, "is_air_unit")?,
            can_attack_air: required_bool(fields, "_can_attack_air_cached")?,
            can_attack_ground: required_bool(fields, "_can_attack_ground_cached")?,
            facing_x_units: required_i64(fields, "_facing_x_units")?,
            facing_y_units: required_i64(fields, "_facing_y_units")?,
            last_combat_target_id: fields.get("_last_combat_target_id").and_then(Value::as_i64),
            has_attacked_once: normalized_optional_bool(fields, "_has_attacked_once"),
            movement_target_id: fields.get("_movement_target_id").and_then(Value::as_i64),
            initial_position: optional_position(fields, "initial_position")?,
            attack_speed_debuff_multiplier: normalized_f64(
                fields,
                "attack_speed_debuff_multiplier",
            )?,
            attack_speed_buff_multiplier: normalized_f64(fields, "attack_speed_buff_multiplier")?,
            attack_mode_multiplier: normalized_f64(fields, "attack_mode_multiplier")?,
            hit_speed_ms,
            first_hit_ms,
            hidden_building: normalized_optional_bool(fields, "_hidden_building"),
            stealth_until_ms: fields
                .get("_stealth_until")
                .and_then(Value::as_i64)
                .unwrap_or(0),
        })
    }

    fn attack_rate(&self) -> f64 {
        let debuff = (self.attack_speed_debuff_multiplier * 100.0)
            .round_ties_even()
            .max(0.0) as i64;
        let buff = (self
            .attack_speed_buff_multiplier
            .max(self.attack_mode_multiplier)
            * 100.0)
            .round_ties_even()
            .max(0.0) as i64;
        let buffed = 50_i64 * buff / 100;
        (buffed * debuff / 100) as f64 / 50.0
    }

    fn base_attack_interval(&self) -> f64 {
        if self.hit_speed_ms == 0 {
            1.0
        } else {
            self.hit_speed_ms as f64 / 1000.0
        }
    }

    fn diagnostic_value(&self, entity: &ResidentEntity) -> Value {
        json!({
            "attack_cooldown": exact_f64_value(self.attack_cooldown),
            "attack_preload_blocked": self.attack_preload_blocked,
            "attack_windup_active": self.attack_windup_active,
            "encounter_index": entity.encounter_index,
            "facing_x_units": self.facing_x_units,
            "facing_y_units": self.facing_y_units,
            "has_attacked_once": self.has_attacked_once,
            "hitpoints": entity.hitpoints.diagnostic_value(),
            "id": entity.id,
            "initial_position": self.initial_position.map(|(x, y)| json!([
                exact_f64_value(x), exact_f64_value(y)
            ])),
            "is_alive": entity.is_alive,
            "last_attack_time": exact_f64_value(self.last_attack_time),
            "last_combat_target_id": self.last_combat_target_id,
            "movement_target_id": self.movement_target_id,
            "target_id": entity.target_id,
        })
    }
}

impl ResidentEntity {
    fn from_normalized(encounter_index: usize, value: &Value) -> PyResult<Self> {
        let fields = object_fields(value)?;
        let position_fields = object_fields(
            fields
                .get("position")
                .ok_or_else(|| PyValueError::new_err("entity has no position"))?,
        )?;
        let card_fields = object_fields(
            fields
                .get("card_stats")
                .ok_or_else(|| PyValueError::new_err("entity has no card_stats"))?,
        )?;
        let mechanics = fields
            .get("mechanics")
            .and_then(Value::as_array)
            .ok_or_else(|| PyValueError::new_err("entity mechanics is not a list"))?
            .iter()
            .map(object_type)
            .collect::<PyResult<Vec<_>>>()?;
        let target_id = fields
            .get("target_id")
            .ok_or_else(|| PyValueError::new_err("entity has no target_id"))?
            .as_i64();
        let entity_kind = required_i64(fields, "entity_kind")?;
        let is_character = matches!(entity_kind, 0 | 1);
        let periodic_empty = normalized_mapping_is_empty(fields, "_periodic_damage_effects")?;
        let temporary_buff_active = fields
            .get("_buff_active")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let modifier_supported = !is_character || (periodic_empty && !temporary_buff_active);
        let modifier_state = if is_character {
            Some(ModifierState::from_fields(fields)?)
        } else {
            None
        };
        let locked_combat = if is_character {
            Some(LockedDirectCombatState::from_fields(fields, card_fields)?)
        } else {
            None
        };
        let mut direct_combat_unsupported = Vec::new();
        if !is_character {
            direct_combat_unsupported.push("non_character_entity".to_owned());
        }
        if entity_kind == 1 {
            direct_combat_unsupported.push("building_combat_not_implemented".to_owned());
        }
        if !mechanics.is_empty() {
            direct_combat_unsupported.push("executable_mechanics".to_owned());
        }
        if !card_fields
            .get("projectile_data")
            .is_none_or(Value::is_null)
        {
            direct_combat_unsupported.push("projectile_payload".to_owned());
        }
        for (field, reason) in [
            ("area_damage_radius", "area_damage"),
            ("projectile_splash_radius", "projectile_splash"),
            ("attack_pushback", "attack_pushback"),
            ("charge_range", "charge_payload"),
        ] {
            if normalized_optional_number_is_nonzero(card_fields, field)? {
                direct_combat_unsupported.push(reason.to_owned());
            }
        }
        if normalized_optional_bool(card_fields, "self_as_aoe_center") {
            direct_combat_unsupported.push("self_centered_aoe".to_owned());
        }
        if normalized_optional_bool(card_fields, "kamikaze") {
            direct_combat_unsupported.push("kamikaze_payload".to_owned());
        }
        if !card_fields
            .get("death_spawn_character")
            .is_none_or(Value::is_null)
        {
            direct_combat_unsupported.push("death_spawn_payload".to_owned());
        }
        if normalized_optional_bool(fields, "_force_melee_attack") {
            direct_combat_unsupported.push("forced_melee_override".to_owned());
        }
        for (field, reason) in [
            ("_river_jump_active", "active_river_jump"),
            ("_special_move_active", "active_special_move"),
            ("_special_move_consumed_tick", "consumed_special_move_tick"),
            ("kamikaze_primed", "active_kamikaze"),
            ("is_charging", "active_charge"),
            ("has_charged", "completed_charge_state"),
        ] {
            if normalized_optional_bool(fields, field) {
                direct_combat_unsupported.push(reason.to_owned());
            }
        }
        let forced_movement_active = normalized_optional_bool(fields, "forced_movement_active");
        let knockback_target_present = fields
            .get("_knockback_target")
            .is_some_and(|value| !value.is_null());
        let knockback_interrupts_combat = fields
            .get("_knockback_interrupts_combat")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        if forced_movement_active && !(knockback_target_present && !knockback_interrupts_combat) {
            direct_combat_unsupported.push("interrupting_forced_movement".to_owned());
        }
        for field in [
            "hitpoints",
            "max_hitpoints",
            "damage",
            "range",
            "sight_range",
            "attack_cooldown",
            "deploy_delay_remaining",
            "last_attack_time",
            "stun_timer",
        ] {
            let number = ExactScalar::from_normalized(
                fields
                    .get(field)
                    .ok_or_else(|| PyValueError::new_err(format!("entity has no {field}")))?,
            )?
            .as_f64();
            if !number.is_finite() {
                direct_combat_unsupported.push(format!("nonfinite_{field}"));
            }
        }
        Ok(Self {
            encounter_index,
            id: required_i64(fields, "id")?,
            player_id: required_i64(fields, "player_id")?,
            entity_kind,
            python_type: object_type(value)?,
            card_name: card_fields
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_owned(),
            position_x: ExactScalar::from_normalized(
                position_fields
                    .get("x")
                    .ok_or_else(|| PyValueError::new_err("position has no x"))?,
            )?,
            position_y: ExactScalar::from_normalized(
                position_fields
                    .get("y")
                    .ok_or_else(|| PyValueError::new_err("position has no y"))?,
            )?,
            hitpoints: ExactScalar::from_normalized(
                fields
                    .get("hitpoints")
                    .ok_or_else(|| PyValueError::new_err("entity has no hitpoints"))?,
            )?,
            max_hitpoints: ExactScalar::from_normalized(
                fields
                    .get("max_hitpoints")
                    .ok_or_else(|| PyValueError::new_err("entity has no max_hitpoints"))?,
            )?,
            is_alive: required_bool(fields, "is_alive")?,
            target_id,
            deploy_delay_remaining: normalized_f64(fields, "deploy_delay_remaining")?,
            placement_pending: required_bool(fields, "placement_pending")?,
            spawn_hook_pending: fields
                .get("_spawn_hook_pending")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            spawn_hook_fired: fields
                .get("_spawn_hook_fired")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            death_spawn_target_immunity_elapsed_ms: required_i64(
                fields,
                "_death_spawn_target_immunity_elapsed_ms",
            )?,
            mechanics,
            modifier_state,
            modifier_supported,
            direct_combat_unsupported,
            locked_combat,
        })
    }

    fn diagnostic_value(&self) -> Value {
        json!({
            "card_name": self.card_name,
            "encounter_index": self.encounter_index,
            "entity_kind": self.entity_kind,
            "hitpoints": self.hitpoints.diagnostic_value(),
            "id": self.id,
            "is_alive": self.is_alive,
            "max_hitpoints": self.max_hitpoints.diagnostic_value(),
            "mechanics": self.mechanics,
            "player_id": self.player_id,
            "position_x": self.position_x.diagnostic_value(),
            "position_y": self.position_y.diagnostic_value(),
            "python_type": self.python_type,
            "target_id": self.target_id,
        })
    }

    fn modifier_diagnostic_value(&self) -> Option<Value> {
        self.modifier_state
            .as_ref()
            .map(|state| state.diagnostic_value(self.id, self.encounter_index))
    }

    fn supports_character_object_phase(&self) -> bool {
        matches!(self.entity_kind, 0 | 1) && self.mechanics.is_empty()
    }

    fn advance_character_object_phase(&mut self, dt: f64) {
        const GLOBAL_ATTACK_FINISH_TIME_MS: i64 = 250;
        if !self.is_alive {
            return;
        }
        if self.death_spawn_target_immunity_elapsed_ms >= 0 {
            // The resident whole-tick boundary advances on the same fixed
            // 50 ms grid as Python's logic_time_milliseconds(). Keeping the
            // conversion explicit pins the causal immunity zero-crossing.
            let elapsed_ms = (dt * 1000.0).round_ties_even() as i64;
            self.death_spawn_target_immunity_elapsed_ms += elapsed_ms.max(0);
            if GLOBAL_ATTACK_FINISH_TIME_MS < self.death_spawn_target_immunity_elapsed_ms {
                self.death_spawn_target_immunity_elapsed_ms = -1;
            }
        }
        if self.deploy_delay_remaining > 0.0 {
            self.deploy_delay_remaining = (self.deploy_delay_remaining - dt).max(0.0);
            if self.deploy_delay_remaining > 1e-9 {
                return;
            }
            self.deploy_delay_remaining = 0.0;
            self.placement_pending = false;
            if self.spawn_hook_pending {
                self.spawn_hook_pending = false;
                self.spawn_hook_fired = true;
            }
            return;
        }
        if self.spawn_hook_pending {
            self.spawn_hook_pending = false;
            self.spawn_hook_fired = true;
        }
    }

    fn character_object_diagnostic_value(&self) -> Option<Value> {
        matches!(self.entity_kind, 0 | 1).then(|| {
            json!({
                "death_spawn_target_immunity_elapsed_ms": self.death_spawn_target_immunity_elapsed_ms,
                "deploy_delay_remaining": exact_f64_value(self.deploy_delay_remaining),
                "encounter_index": self.encounter_index,
                "id": self.id,
                "placement_pending": self.placement_pending,
                "spawn_hook_fired": self.spawn_hook_fired,
                "spawn_hook_pending": self.spawn_hook_pending,
            })
        })
    }

    fn direct_combat_capability_value(&self) -> Value {
        json!({
            "encounter_index": self.encounter_index,
            "id": self.id,
            "reasons": self.direct_combat_unsupported,
        })
    }

    fn locked_combat_diagnostic_value(&self) -> Option<Value> {
        self.locked_combat
            .as_ref()
            .map(|state| state.diagnostic_value(self))
    }
}

fn parse_resident_entities(payload: &[u8]) -> PyResult<Vec<ResidentEntity>> {
    let root: Value = serde_json::from_slice(payload)
        .map_err(|error| PyValueError::new_err(format!("invalid battle checkpoint: {error}")))?;
    let entities = root
        .get("entities")
        .and_then(Value::as_array)
        .ok_or_else(|| PyValueError::new_err("battle checkpoint has no entity list"))?;
    let iteration_order = root
        .get("entity_iteration_order")
        .and_then(Value::as_array)
        .ok_or_else(|| PyValueError::new_err("battle checkpoint has no entity iteration order"))?;
    if entities.len() != iteration_order.len() {
        return Err(PyValueError::new_err(
            "entity list and iteration order have different lengths",
        ));
    }
    let parsed = entities
        .iter()
        .enumerate()
        .map(|(index, entity)| ResidentEntity::from_normalized(index, entity))
        .collect::<PyResult<Vec<_>>>()?;
    for (index, (entity, expected_id)) in parsed.iter().zip(iteration_order).enumerate() {
        let expected_id = expected_id.as_i64().ok_or_else(|| {
            PyValueError::new_err("entity iteration order contains a non-integer ID")
        })?;
        if entity.id != expected_id {
            return Err(PyValueError::new_err(format!(
                "entity iteration order mismatch at {index}: entity={} order={expected_id}",
                entity.id
            )));
        }
    }
    Ok(parsed)
}

#[derive(Clone)]
struct PythonMt19937 {
    version: i64,
    state: [u32; 624],
    index: usize,
    gauss_next: Option<ExactScalar>,
}

impl PythonMt19937 {
    fn from_checkpoint(payload: &[u8]) -> PyResult<Self> {
        let root: Value = serde_json::from_slice(payload).map_err(|error| {
            PyValueError::new_err(format!("invalid battle checkpoint: {error}"))
        })?;
        let outer = root
            .get("rng_state")
            .and_then(|value| value.get("$tuple"))
            .and_then(Value::as_array)
            .ok_or_else(|| PyValueError::new_err("checkpoint has no Python RNG tuple"))?;
        if outer.len() != 3 {
            return Err(PyValueError::new_err(
                "Python RNG outer state must have 3 items",
            ));
        }
        let version = outer[0]
            .as_i64()
            .ok_or_else(|| PyValueError::new_err("Python RNG version is not an integer"))?;
        if version != 3 {
            return Err(PyValueError::new_err(format!(
                "unsupported Python RNG version {version}; expected 3"
            )));
        }
        let inner = outer[1]
            .get("$tuple")
            .and_then(Value::as_array)
            .ok_or_else(|| PyValueError::new_err("Python RNG inner state is not a tuple"))?;
        if inner.len() != 625 {
            return Err(PyValueError::new_err(format!(
                "Python RNG inner state has {} items; expected 625",
                inner.len()
            )));
        }
        let mut state = [0_u32; 624];
        for (target, source) in state.iter_mut().zip(&inner[..624]) {
            let word = source
                .as_u64()
                .ok_or_else(|| PyValueError::new_err("Python RNG word is not an unsigned int"))?;
            *target = u32::try_from(word)
                .map_err(|_| PyValueError::new_err("Python RNG word exceeds u32"))?;
        }
        let index_u64 = inner[624]
            .as_u64()
            .ok_or_else(|| PyValueError::new_err("Python RNG index is not unsigned"))?;
        let index = usize::try_from(index_u64)
            .map_err(|_| PyValueError::new_err("Python RNG index exceeds usize"))?;
        if index > 624 {
            return Err(PyValueError::new_err(format!(
                "Python RNG index {index} exceeds 624"
            )));
        }
        let gauss_next = if outer[2].is_null() {
            None
        } else {
            Some(ExactScalar::from_normalized(&outer[2])?)
        };
        Ok(Self {
            version,
            state,
            index,
            gauss_next,
        })
    }

    fn next_u32(&mut self) -> u32 {
        const N: usize = 624;
        const M: usize = 397;
        const MATRIX_A: u32 = 0x9908_b0df;
        const UPPER_MASK: u32 = 0x8000_0000;
        const LOWER_MASK: u32 = 0x7fff_ffff;
        if self.index >= N {
            for index in 0..(N - M) {
                let value = (self.state[index] & UPPER_MASK) | (self.state[index + 1] & LOWER_MASK);
                self.state[index] = self.state[index + M]
                    ^ (value >> 1)
                    ^ if value & 1 == 0 { 0 } else { MATRIX_A };
            }
            for index in (N - M)..(N - 1) {
                let value = (self.state[index] & UPPER_MASK) | (self.state[index + 1] & LOWER_MASK);
                self.state[index] = self.state[index + M - N]
                    ^ (value >> 1)
                    ^ if value & 1 == 0 { 0 } else { MATRIX_A };
            }
            let value = (self.state[N - 1] & UPPER_MASK) | (self.state[0] & LOWER_MASK);
            self.state[N - 1] =
                self.state[M - 1] ^ (value >> 1) ^ if value & 1 == 0 { 0 } else { MATRIX_A };
            self.index = 0;
        }
        let mut value = self.state[self.index];
        self.index += 1;
        value ^= value >> 11;
        value ^= (value << 7) & 0x9d2c_5680;
        value ^= (value << 15) & 0xefc6_0000;
        value ^= value >> 18;
        value
    }

    fn random(&mut self) -> f64 {
        let first = u64::from(self.next_u32() >> 5);
        let second = u64::from(self.next_u32() >> 6);
        ((first << 26) + second) as f64 * (1.0 / 9_007_199_254_740_992.0)
    }

    fn getrandbits_u64(&mut self, bits: u32) -> u64 {
        match bits {
            0 => 0,
            1..=32 => u64::from(self.next_u32() >> (32 - bits)),
            33..=64 => {
                let low = u64::from(self.next_u32());
                let high_bits = bits - 32;
                let high = u64::from(self.next_u32() >> (32 - high_bits));
                low | (high << 32)
            }
            _ => unreachable!("u64 bit width"),
        }
    }

    fn randbelow(&mut self, stop: u64) -> PyResult<u64> {
        if stop == 0 {
            return Err(PyValueError::new_err("randrange stop must be positive"));
        }
        let bits = 64 - stop.leading_zeros();
        loop {
            let value = self.getrandbits_u64(bits);
            if value < stop {
                return Ok(value);
            }
        }
    }

    fn choice_index(&mut self, length: usize) -> PyResult<usize> {
        if length == 0 {
            return Err(PyIndexError::new_err(
                "cannot choose from an empty sequence",
            ));
        }
        let length = u64::try_from(length)
            .map_err(|_| PyValueError::new_err("sequence length exceeds u64"))?;
        usize::try_from(self.randbelow(length)?)
            .map_err(|_| PyValueError::new_err("chosen index exceeds usize"))
    }

    fn shuffle_indices(&mut self, length: usize) -> PyResult<Vec<usize>> {
        let mut indices = (0..length).collect::<Vec<_>>();
        // This is the exact reverse Fisher-Yates loop used by
        // random.Random.shuffle in CPython. In particular, a two-element
        // action order consumes _randbelow(2) once per environment decision.
        for index in (1..length).rev() {
            let other = self.choice_index(index + 1)?;
            indices.swap(index, other);
        }
        Ok(indices)
    }

    fn diagnostic_value(&self) -> Value {
        json!({
            "gauss_next": self.gauss_next.as_ref().map(ExactScalar::diagnostic_value),
            "index": self.index,
            "state": self.state.as_slice(),
            "version": self.version,
        })
    }
}

type PlayerInit = (
    i64,
    f64,
    f64,
    i64,
    Vec<Option<String>>,
    Vec<String>,
    f64,
    f64,
    f64,
);
type PlayerStateTuple = PlayerInit;
type TowerInit = (i64, i64, String, f64, i64, bool, bool, f64);
type TowerStateTuple = TowerInit;

#[derive(Clone)]
struct ResidentPlayer {
    player_id: i64,
    elixir: f64,
    max_elixir: f64,
    next_card_refill_cooldown_ms: i64,
    hand: Vec<Option<String>>,
    cycle_queue: VecDeque<String>,
    king_tower_hp: f64,
    left_tower_hp: f64,
    right_tower_hp: f64,
}

impl ResidentPlayer {
    fn from_init(value: PlayerInit) -> PyResult<Self> {
        let (
            player_id,
            elixir,
            max_elixir,
            cooldown_ms,
            hand,
            cycle_queue,
            king_tower_hp,
            left_tower_hp,
            right_tower_hp,
        ) = value;
        if !elixir.is_finite()
            || !max_elixir.is_finite()
            || !king_tower_hp.is_finite()
            || !left_tower_hp.is_finite()
            || !right_tower_hp.is_finite()
        {
            return Err(PyValueError::new_err(
                "player elixir and tower hitpoints must be finite",
            ));
        }
        Ok(Self {
            player_id,
            elixir,
            max_elixir,
            next_card_refill_cooldown_ms: cooldown_ms,
            hand,
            cycle_queue: cycle_queue.into(),
            king_tower_hp,
            left_tower_hp,
            right_tower_hp,
        })
    }

    fn state_tuple(&self) -> PlayerStateTuple {
        (
            self.player_id,
            self.elixir,
            self.max_elixir,
            self.next_card_refill_cooldown_ms,
            self.hand.clone(),
            self.cycle_queue.iter().cloned().collect(),
            self.king_tower_hp,
            self.left_tower_hp,
            self.right_tower_hp,
        )
    }

    fn advance(&mut self, dt: f64, base_regen_time: f64, refill_ms: i64, tick_ms: i64) {
        if self.elixir < self.max_elixir {
            let elixir_per_second = 1.0 / base_regen_time;
            self.elixir = self.max_elixir.min(self.elixir + elixir_per_second * dt);
        }

        if self.next_card_refill_cooldown_ms > 0 {
            self.next_card_refill_cooldown_ms = 0.max(self.next_card_refill_cooldown_ms - tick_ms);
        }
        if self.next_card_refill_cooldown_ms != 0 || self.cycle_queue.is_empty() {
            return;
        }
        let Some(slot) = self.hand.iter().position(Option::is_none) else {
            return;
        };
        self.hand[slot] = self.cycle_queue.pop_front();
        self.next_card_refill_cooldown_ms = refill_ms;
    }

    fn append_hash_payload(&self, payload: &mut Vec<u8>) {
        payload.extend_from_slice(&self.player_id.to_le_bytes());
        payload.extend_from_slice(&self.elixir.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.max_elixir.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.next_card_refill_cooldown_ms.to_le_bytes());
        payload.extend_from_slice(&(self.hand.len() as u64).to_le_bytes());
        for card in &self.hand {
            match card {
                None => payload.push(0),
                Some(name) => {
                    payload.push(1);
                    append_string(payload, name);
                }
            }
        }
        payload.extend_from_slice(&(self.cycle_queue.len() as u64).to_le_bytes());
        for card in &self.cycle_queue {
            append_string(payload, card);
        }
        payload.extend_from_slice(&self.king_tower_hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.left_tower_hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.right_tower_hp.to_bits().to_le_bytes());
    }

    fn towers_lost(&self) -> i64 {
        if self.king_tower_hp <= 0.0 {
            return 3;
        }
        i64::from(self.left_tower_hp <= 0.0) + i64::from(self.right_tower_hp <= 0.0)
    }

    fn lowest_tower_hp_milli(&self, towers: &[ResidentTower]) -> i64 {
        towers
            .iter()
            .filter(|tower| tower.player_id == self.player_id && tower.hp > 0.0)
            .map(|tower| tower.hp_milli)
            .min()
            .unwrap_or(0)
    }
}

#[derive(Clone)]
struct ResidentTower {
    id: i64,
    player_id: i64,
    slot: String,
    hp: f64,
    hp_milli: i64,
    is_alive: bool,
    is_active: bool,
    last_attack_time: f64,
}

impl ResidentTower {
    fn from_init(value: TowerInit) -> PyResult<Self> {
        let (id, player_id, slot, hp, hp_milli, is_alive, is_active, last_attack_time) = value;
        if !matches!(slot.as_str(), "left" | "right" | "king") {
            return Err(PyValueError::new_err(format!(
                "unsupported Crown Tower slot {slot:?}"
            )));
        }
        if !hp.is_finite() || !last_attack_time.is_finite() {
            return Err(PyValueError::new_err(
                "tower hitpoints and last_attack_time must be finite",
            ));
        }
        Ok(Self {
            id,
            player_id,
            slot,
            hp,
            hp_milli,
            is_alive,
            is_active,
            last_attack_time,
        })
    }

    fn state_tuple(&self) -> TowerStateTuple {
        (
            self.id,
            self.player_id,
            self.slot.clone(),
            self.hp,
            self.hp_milli,
            self.is_alive,
            self.is_active,
            self.last_attack_time,
        )
    }

    fn append_hash_payload(&self, payload: &mut Vec<u8>) {
        payload.extend_from_slice(&self.id.to_le_bytes());
        payload.extend_from_slice(&self.player_id.to_le_bytes());
        append_string(payload, &self.slot);
        payload.extend_from_slice(&self.hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.hp_milli.to_le_bytes());
        payload.push(u8::from(self.is_alive));
        payload.push(u8::from(self.is_active));
        payload.extend_from_slice(&self.last_attack_time.to_bits().to_le_bytes());
    }
}

fn append_string(payload: &mut Vec<u8>, value: &str) {
    payload.extend_from_slice(&(value.len() as u64).to_le_bytes());
    payload.extend_from_slice(value.as_bytes());
}

/// Long-lived native battle allocation.
///
/// Initialization and explicit checkpoint replacement may cross the FFI as a
/// complete canonical payload. Ordinary phase/tick methods mutate the fields
/// below directly and never serialize or reparse that payload.
#[pyclass(module = "_clasher_rust")]
#[derive(Clone)]
struct ResidentBattle {
    checkpoint: Vec<u8>,
    checkpoint_sha256: String,
    checkpoint_current: bool,
    schema_version: u64,
    checkpoint_generation: u64,
    tick: i64,
    time: f64,
    dt: f64,
    double_elixir: bool,
    triple_elixir: bool,
    overtime: bool,
    game_over: bool,
    double_elixir_start_time: f64,
    overtime_start_time: f64,
    triple_elixir_start_time: f64,
    player_tick_ms: i64,
    refill_schedule: Vec<(f64, i64)>,
    players: Vec<ResidentPlayer>,
    towers: Vec<ResidentTower>,
    idle_eligible: bool,
    sparse_idle_win_checks: bool,
    sudden_death: bool,
    sudden_death_crowns: (i64, i64),
    tiebreaker_time: f64,
    winner: Option<i64>,
    entities: Vec<ResidentEntity>,
    rng: PythonMt19937,
}

#[pymethods]
impl ResidentBattle {
    #[new]
    #[pyo3(signature = (
        checkpoint,
        *,
        tick,
        time,
        dt,
        double_elixir,
        triple_elixir,
        overtime,
        game_over,
        double_elixir_start_time,
        overtime_start_time,
        triple_elixir_start_time,
        player_tick_ms,
        refill_schedule,
        players,
        towers,
        idle_eligible,
        sparse_idle_win_checks,
        sudden_death,
        sudden_death_crowns,
        tiebreaker_time,
        winner
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        checkpoint: &[u8],
        tick: i64,
        time: f64,
        dt: f64,
        double_elixir: bool,
        triple_elixir: bool,
        overtime: bool,
        game_over: bool,
        double_elixir_start_time: f64,
        overtime_start_time: f64,
        triple_elixir_start_time: f64,
        player_tick_ms: i64,
        refill_schedule: Vec<(f64, i64)>,
        players: Vec<PlayerInit>,
        towers: Vec<TowerInit>,
        idle_eligible: bool,
        sparse_idle_win_checks: bool,
        sudden_death: bool,
        sudden_death_crowns: (i64, i64),
        tiebreaker_time: f64,
        winner: Option<i64>,
    ) -> PyResult<Self> {
        if !time.is_finite() || !dt.is_finite() || dt < 0.0 {
            return Err(PyValueError::new_err(
                "battle time and non-negative dt must be finite",
            ));
        }
        let schema_version = validate_checkpoint(checkpoint)?;
        let entities = parse_resident_entities(checkpoint)?;
        let rng = PythonMt19937::from_checkpoint(checkpoint)?;
        if refill_schedule.is_empty() {
            return Err(PyValueError::new_err("refill schedule cannot be empty"));
        }
        let players = players
            .into_iter()
            .map(ResidentPlayer::from_init)
            .collect::<PyResult<Vec<_>>>()?;
        let towers = towers
            .into_iter()
            .map(ResidentTower::from_init)
            .collect::<PyResult<Vec<_>>>()?;
        Ok(Self {
            checkpoint: checkpoint.to_vec(),
            checkpoint_sha256: sha256_hex(checkpoint),
            checkpoint_current: true,
            schema_version,
            checkpoint_generation: 0,
            tick,
            time,
            dt,
            double_elixir,
            triple_elixir,
            overtime,
            game_over,
            double_elixir_start_time,
            overtime_start_time,
            triple_elixir_start_time,
            player_tick_ms,
            refill_schedule,
            players,
            towers,
            idle_eligible,
            sparse_idle_win_checks,
            sudden_death,
            sudden_death_crowns,
            tiebreaker_time,
            winner,
            entities,
            rng,
        })
    }

    /// Advance only the resident clock/timer phase of one native logic tick.
    /// Later milestones will append the remaining phases before complete-tick
    /// capability can be enabled.
    fn advance_clock_phase(&mut self) -> bool {
        if self.game_over {
            return false;
        }
        self.checkpoint_current = false;
        self.time += self.dt;
        self.tick += 1;
        if self.time >= self.double_elixir_start_time {
            self.double_elixir = true;
        }
        if self.time >= self.overtime_start_time {
            self.overtime = true;
        }
        if self.time >= self.triple_elixir_start_time {
            self.triple_elixir = true;
        }
        true
    }

    fn clock_state(&self) -> (i64, f64, f64, bool, bool, bool, bool) {
        (
            self.tick,
            self.time,
            self.dt,
            self.double_elixir,
            self.triple_elixir,
            self.overtime,
            self.game_over,
        )
    }

    fn clock_sha256(&self) -> String {
        let mut payload = Vec::with_capacity(28);
        payload.extend_from_slice(&self.tick.to_le_bytes());
        payload.extend_from_slice(&self.time.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.dt.to_bits().to_le_bytes());
        payload.extend_from_slice(&[
            u8::from(self.double_elixir),
            u8::from(self.triple_elixir),
            u8::from(self.overtime),
            u8::from(self.game_over),
        ]);
        sha256_hex(&payload)
    }

    /// Advance the resident player phase after the clock phase of this tick.
    fn advance_player_phase(&mut self) {
        self.checkpoint_current = false;
        self.advance_players();
    }

    fn advance_players(&mut self) {
        let base_regen_time = if self.triple_elixir {
            0.93
        } else if self.double_elixir {
            1.4
        } else {
            2.8
        };
        let refill_ms = self
            .refill_schedule
            .iter()
            .find(|(segment_end, _)| self.time < *segment_end - 1e-9)
            .map(|(_, cooldown_ms)| *cooldown_ms)
            .unwrap_or_else(|| self.refill_schedule.last().expect("nonempty schedule").1);
        for player in &mut self.players {
            player.advance(self.dt, base_regen_time, refill_ms, self.player_tick_ms);
        }
    }

    fn player_states(&self) -> Vec<PlayerStateTuple> {
        self.players
            .iter()
            .map(ResidentPlayer::state_tuple)
            .collect()
    }

    fn player_sha256(&self) -> String {
        let mut payload = Vec::new();
        payload.extend_from_slice(&(self.players.len() as u64).to_le_bytes());
        for player in &self.players {
            player.append_hash_payload(&mut payload);
        }
        sha256_hex(&payload)
    }

    fn supports_idle_ticks(&self) -> bool {
        self.idle_eligible
    }

    fn advance_idle_ticks(&mut self, ticks: i64) -> PyResult<i64> {
        if ticks <= 0 {
            return Ok(0);
        }
        if !self.idle_eligible {
            return Err(PyRuntimeError::new_err(
                "resident battle did not pass the Python idle preflight",
            ));
        }
        let mut advanced = 0;
        for _ in 0..ticks {
            if self.game_over {
                break;
            }
            self.advance_clock_phase();
            self.advance_players();
            for tower in &mut self.towers {
                if tower.is_alive && tower.is_active {
                    tower.last_attack_time += self.dt;
                }
            }
            advanced += 1;
            if !self.sparse_idle_win_checks
                || (!self.sudden_death && self.time >= self.overtime_start_time)
                || (self.sudden_death && self.time >= self.tiebreaker_time)
            {
                self.check_win_conditions();
            }
            if self.game_over {
                break;
            }
        }
        Ok(advanced)
    }

    fn check_win_conditions(&mut self) {
        let king_alive = (
            self.players[0].king_tower_hp > 0.0,
            self.players[1].king_tower_hp > 0.0,
        );
        if !king_alive.0 || !king_alive.1 {
            self.game_over = true;
            self.winner = match king_alive {
                (false, false) => None,
                (true, false) => Some(0),
                (false, true) => Some(1),
                (true, true) => unreachable!(),
            };
            return;
        }
        let player0_crowns = self.players[1].towers_lost();
        let player1_crowns = self.players[0].towers_lost();
        if self.time >= self.overtime_start_time && !self.sudden_death {
            if player0_crowns != player1_crowns {
                self.game_over = true;
                self.winner = Some(if player0_crowns > player1_crowns {
                    0
                } else {
                    1
                });
                return;
            }
            self.sudden_death = true;
            self.sudden_death_crowns = (player0_crowns, player1_crowns);
        }
        if self.sudden_death {
            if player0_crowns != player1_crowns {
                self.game_over = true;
                self.winner = Some(if player0_crowns > player1_crowns {
                    0
                } else {
                    1
                });
                return;
            }
            if self.time >= self.tiebreaker_time {
                let player0_lowest = self.players[0].lowest_tower_hp_milli(&self.towers);
                let player1_lowest = self.players[1].lowest_tower_hp_milli(&self.towers);
                self.winner = if player0_lowest > player1_lowest {
                    Some(0)
                } else if player1_lowest > player0_lowest {
                    Some(1)
                } else {
                    None
                };
                self.game_over = true;
            }
        }
    }

    fn tower_states(&self) -> Vec<TowerStateTuple> {
        self.towers.iter().map(ResidentTower::state_tuple).collect()
    }

    fn outcome_state(&self) -> (bool, bool, Option<i64>, (i64, i64)) {
        (
            self.sudden_death,
            self.game_over,
            self.winner,
            self.sudden_death_crowns,
        )
    }

    fn idle_sha256(&self) -> String {
        let mut payload = Vec::new();
        payload.extend_from_slice(&self.tick.to_le_bytes());
        payload.extend_from_slice(&self.time.to_bits().to_le_bytes());
        payload.push(u8::from(self.double_elixir));
        payload.push(u8::from(self.triple_elixir));
        payload.push(u8::from(self.overtime));
        payload.push(u8::from(self.sudden_death));
        payload.push(u8::from(self.game_over));
        match self.winner {
            None => payload.push(0),
            Some(winner) => {
                payload.push(1);
                payload.extend_from_slice(&winner.to_le_bytes());
            }
        }
        payload.extend_from_slice(&self.sudden_death_crowns.0.to_le_bytes());
        payload.extend_from_slice(&self.sudden_death_crowns.1.to_le_bytes());
        payload.extend_from_slice(&(self.players.len() as u64).to_le_bytes());
        for player in &self.players {
            player.append_hash_payload(&mut payload);
        }
        payload.extend_from_slice(&(self.towers.len() as u64).to_le_bytes());
        for tower in &self.towers {
            tower.append_hash_payload(&mut payload);
        }
        sha256_hex(&payload)
    }

    fn entity_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .map(ResidentEntity::diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize resident entities: {error}"))
        })
    }

    fn entity_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.entity_state_bytes()?))
    }

    fn supports_modifier_phase(&self) -> bool {
        self.entities.iter().all(|entity| entity.modifier_supported)
    }

    fn advance_modifier_phase(&mut self) -> PyResult<()> {
        if !self.supports_modifier_phase() {
            return Err(PyRuntimeError::new_err(
                "resident modifier phase contains periodic damage or callback-owned temporary buffs",
            ));
        }
        self.checkpoint_current = false;
        for entity in &mut self.entities {
            if !entity.is_alive {
                continue;
            }
            if let Some(state) = &mut entity.modifier_state {
                state.advance(self.dt);
            }
        }
        Ok(())
    }

    fn modifier_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter_map(ResidentEntity::modifier_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize modifier state: {error}"))
        })
    }

    fn modifier_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.modifier_state_bytes()?))
    }

    fn supports_character_object_phase(&self) -> bool {
        self.entities
            .iter()
            .all(ResidentEntity::supports_character_object_phase)
    }

    fn advance_character_object_phase(&mut self) -> PyResult<()> {
        if !self.supports_character_object_phase() {
            return Err(PyRuntimeError::new_err(
                "resident character object phase contains non-character entities or executable mechanics",
            ));
        }
        self.checkpoint_current = false;
        for entity in &mut self.entities {
            entity.advance_character_object_phase(self.dt);
        }
        Ok(())
    }

    fn character_object_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter_map(ResidentEntity::character_object_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize resident character object state: {error}"
            ))
        })
    }

    fn character_object_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.character_object_state_bytes()?))
    }

    fn supports_direct_combat_phase(&self) -> bool {
        self.entities
            .iter()
            .all(|entity| entity.direct_combat_unsupported.is_empty())
    }

    fn direct_combat_capability_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .map(ResidentEntity::direct_combat_capability_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize resident direct-combat capability: {error}"
            ))
        })
    }

    fn supports_locked_direct_combat_phase(&self) -> bool {
        if !self.supports_direct_combat_phase() {
            return false;
        }
        let now_ms = (self.time * 1000.0).round_ties_even() as i64;
        for actor in &self.entities {
            if !actor.is_alive {
                continue;
            }
            if actor.deploy_delay_remaining > 0.0 {
                return false;
            }
            let Some(actor_state) = actor.locked_combat.as_ref() else {
                return false;
            };
            let Some(target_id) = actor.target_id else {
                return false;
            };
            if actor_state.last_combat_target_id != Some(target_id) {
                return false;
            }
            let Some(target) = self.entities.iter().find(|entity| entity.id == target_id) else {
                return false;
            };
            let Some(target_state) = target.locked_combat.as_ref() else {
                return false;
            };
            if !target.is_alive
                || target.player_id == actor.player_id
                || target_state.hidden_building
                || target_state.stealth_until_ms > now_ms
                || target.death_spawn_target_immunity_elapsed_ms >= 0
            {
                return false;
            }
            if (target_state.is_air_unit && !actor_state.can_attack_air)
                || (!target_state.is_air_unit && !actor_state.can_attack_ground)
            {
                return false;
            }
            let dx = target.position_x.as_f64() - actor.position_x.as_f64();
            let dy = target.position_y.as_f64() - actor.position_y.as_f64();
            let discount =
                target_state.native_target_distance_discount_sq_units.max(0) as f64 / 1_000_000.0;
            let distance = (dx * dx + dy * dy - discount).max(0.0).sqrt();
            let reach = actor_state.range + target_state.collision_radius + 1e-8;
            if distance > reach {
                return false;
            }
            let hits_this_phase = actor_state.stun_timer <= 0.0
                && (actor_state.attack_cooldown <= 0.0
                    || actor_state.attack_cooldown - self.dt * actor_state.attack_rate() <= 1e-9);
            if hits_this_phase && actor_state.damage >= target.hitpoints.as_f64() {
                // Lethal ordered damage requires retarget/death/cache behavior
                // that belongs to the next combat capability expansion.
                return false;
            }
        }
        true
    }

    fn advance_locked_direct_combat_phase(&mut self) -> PyResult<()> {
        if !self.supports_locked_direct_combat_phase() {
            return Err(PyRuntimeError::new_err(
                "resident locked direct-combat preflight rejected battle state",
            ));
        }
        self.checkpoint_current = false;
        for actor_index in 0..self.entities.len() {
            if !self.entities[actor_index].is_alive {
                continue;
            }
            let target_id = self.entities[actor_index]
                .target_id
                .expect("locked preflight requires target");
            let target_index = self
                .entities
                .iter()
                .position(|entity| entity.id == target_id)
                .expect("locked preflight requires resident target");
            let target_x = self.entities[target_index].position_x.as_f64();
            let target_y = self.entities[target_index].position_y.as_f64();
            let (actor_x, actor_y) = (
                self.entities[actor_index].position_x.as_f64(),
                self.entities[actor_index].position_y.as_f64(),
            );
            let damage = {
                let actor = &mut self.entities[actor_index];
                let state = actor
                    .locked_combat
                    .as_mut()
                    .expect("locked preflight requires combat state");
                state.movement_target_id = None;
                state.initial_position.get_or_insert((actor_x, actor_y));
                state.last_attack_time += self.dt;
                let facing_x = ((target_x - actor_x) * 1000.0).round_ties_even() as i64;
                let facing_y = ((target_y - actor_y) * 1000.0).round_ties_even() as i64;
                if facing_x != 0 || facing_y != 0 {
                    state.facing_x_units = facing_x;
                    state.facing_y_units = facing_y;
                }
                if state.stun_timer > 0.0 {
                    None
                } else {
                    if state.attack_cooldown > 0.0 {
                        state.attack_cooldown -= self.dt * state.attack_rate();
                        if state.attack_cooldown <= 1e-9 {
                            state.attack_cooldown = 0.0;
                        }
                    }
                    if !state.attack_windup_active
                        && state.attack_cooldown <= state.first_hit_ms as f64 / 1000.0 + 1e-12
                    {
                        state.attack_windup_active = true;
                    }
                    if state.attack_cooldown <= 0.0 {
                        state.attack_cooldown = state.base_attack_interval();
                        state.attack_windup_active = false;
                        state.has_attacked_once = true;
                        state.attack_preload_blocked = false;
                        state.last_attack_time = 0.0;
                        Some(state.damage)
                    } else {
                        None
                    }
                }
            };
            if let Some(damage) = damage {
                let target = &mut self.entities[target_index];
                target
                    .hitpoints
                    .set_f64((target.hitpoints.as_f64() - damage).max(0.0));
            }
        }
        Ok(())
    }

    fn locked_direct_combat_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter_map(ResidentEntity::locked_combat_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize resident locked direct-combat state: {error}"
            ))
        })
    }

    fn locked_direct_combat_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.locked_direct_combat_state_bytes()?))
    }

    fn rng_random(&mut self) -> f64 {
        self.checkpoint_current = false;
        self.rng.random()
    }

    fn rng_randrange(&mut self, stop: u64) -> PyResult<u64> {
        let value = self.rng.randbelow(stop)?;
        self.checkpoint_current = false;
        Ok(value)
    }

    fn rng_choice_index(&mut self, length: usize) -> PyResult<usize> {
        let value = self.rng.choice_index(length)?;
        self.checkpoint_current = false;
        Ok(value)
    }

    fn rng_shuffle_indices(&mut self, length: usize) -> PyResult<Vec<usize>> {
        let value = self.rng.shuffle_indices(length)?;
        if length >= 2 {
            self.checkpoint_current = false;
        }
        Ok(value)
    }

    fn rng_state_parts(&self) -> (i64, Vec<u32>, usize, Option<f64>) {
        (
            self.rng.version,
            self.rng.state.to_vec(),
            self.rng.index,
            self.rng.gauss_next.as_ref().map(ExactScalar::as_f64),
        )
    }

    fn rng_state_bytes(&self) -> PyResult<Vec<u8>> {
        serde_json::to_vec(&self.rng.diagnostic_value()).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize resident RNG: {error}"))
        })
    }

    fn rng_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.rng_state_bytes()?))
    }

    fn checkpoint_bytes(&self) -> PyResult<Vec<u8>> {
        if !self.checkpoint_current {
            return Err(PyRuntimeError::new_err(
                "resident checkpoint is stale after native mutation; exact current-state export is not implemented yet",
            ));
        }
        Ok(self.checkpoint.clone())
    }

    fn checkpoint_sha256(&self) -> PyResult<&str> {
        if !self.checkpoint_current {
            return Err(PyRuntimeError::new_err(
                "resident checkpoint is stale after native mutation; exact current-state export is not implemented yet",
            ));
        }
        Ok(&self.checkpoint_sha256)
    }

    fn checkpoint_size(&self) -> usize {
        self.checkpoint.len()
    }

    fn checkpoint_generation(&self) -> u64 {
        self.checkpoint_generation
    }

    fn checkpoint_is_current(&self) -> bool {
        self.checkpoint_current
    }

    fn schema_version(&self) -> u64 {
        self.schema_version
    }

    fn replace_checkpoint(&mut self, checkpoint: &[u8]) -> PyResult<()> {
        let schema_version = validate_checkpoint(checkpoint)?;
        let replacement_sha256 = sha256_hex(checkpoint);
        if !self.checkpoint_current || replacement_sha256 != self.checkpoint_sha256 {
            return Err(PyRuntimeError::new_err(
                "installing a different resident checkpoint requires exact full-state rehydration, which is not implemented yet",
            ));
        }
        self.schema_version = schema_version;
        self.checkpoint_generation = self
            .checkpoint_generation
            .checked_add(1)
            .ok_or_else(|| PyRuntimeError::new_err("checkpoint generation overflow"))?;
        Ok(())
    }

    fn supports_complete_tick(&self) -> bool {
        false
    }

    fn fork(&self) -> Self {
        self.clone()
    }
}

#[pymodule]
fn _clasher_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(noop_ticks, module)?)?;
    module.add_function(wrap_pyfunction!(consume_state_bytes, module)?)?;
    module.add_class::<ResidentBattle>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fnv_is_stable() {
        assert_eq!(fnv1a(b""), 0xcbf29ce484222325);
        assert_eq!(fnv1a(b"clasher"), 0xf8c3eade13d5df8d);
    }

    #[test]
    fn sha256_is_stable() {
        assert_eq!(
            sha256_hex(b"clasher"),
            "2c69056d0b19b570ec219f88f78d9e3cb73ebb7c0496c1f50b59e3585f1f615d"
        );
    }

    #[test]
    fn python_float_hex_round_trips_binary64_bits() {
        let cases = [
            ("0x0.0p+0", 0.0_f64),
            ("-0x0.0p+0", -0.0_f64),
            ("0x0.0000000000001p-1022", f64::from_bits(1)),
            ("0x1.0000000000000p-1022", f64::MIN_POSITIVE),
            ("0x1.8000000000000p+1", 3.0_f64),
            ("-0x1.921fb54442d18p+1", -std::f64::consts::PI),
            ("0x1.fffffffffffffp+1023", f64::MAX),
        ];
        for (encoded, expected) in cases {
            assert_eq!(
                parse_python_float_hex(encoded).expect("valid float.hex"),
                expected.to_bits(),
                "{encoded}"
            );
        }
    }
}
