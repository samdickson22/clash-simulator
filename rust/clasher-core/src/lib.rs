use pyo3::exceptions::{PyIndexError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::collections::VecDeque;
use std::sync::Arc;

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

const STANDARD_PATH_WIDTH: i64 = 36;
const STANDARD_PATH_HEIGHT: i64 = 64;
const STANDARD_PATH_ROWS: [&str; 64] = [
    "000000000000000000000000000000000000",
    "000000000000000000000000000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111100001111222200002222200000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000000110000000000000000000022000000",
    "000000110000000000000000000022000000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000001111100001111222200002222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000000000000000000000000000",
    "000000000000000000000000000000000000",
];

fn standard_path_tile_cost(cell_x: i64, cell_y: i64, lane_id: i64, jump_height: bool) -> i64 {
    let blocked_river =
        (30..34).contains(&cell_y) && !((5..=8).contains(&cell_x) || (27..=30).contains(&cell_x));
    if blocked_river {
        return if jump_height { 20 } else { 800 };
    }
    let lane = i64::from(STANDARD_PATH_ROWS[cell_y as usize].as_bytes()[cell_x as usize] - b'0');
    if lane <= 0 {
        20
    } else if lane == lane_id {
        1
    } else {
        5
    }
}

fn native_path_heap_push(heap: &mut Vec<usize>, priorities: &[i64], cell: usize) {
    heap.push(cell);
    let mut index = heap.len() - 1;
    while index > 0 {
        let parent_index = (index - 1) / 2;
        let parent = heap[parent_index];
        if priorities[parent] <= priorities[cell] {
            break;
        }
        heap[index] = parent;
        index = parent_index;
    }
    heap[index] = cell;
}

fn native_path_heap_pop(heap: &mut Vec<usize>, priorities: &[i64]) -> usize {
    let root = heap[0];
    let last = heap.pop().expect("nonempty native path heap");
    if heap.is_empty() {
        return root;
    }
    heap[0] = last;
    let mut index = 0;
    loop {
        let mut chosen = index;
        let right = index * 2 + 2;
        if right < heap.len() && priorities[heap[right]] < priorities[heap[chosen]] {
            chosen = right;
        }
        let left = index * 2 + 1;
        if left < heap.len() && priorities[heap[left]] < priorities[heap[chosen]] {
            chosen = left;
        }
        if chosen == index {
            break;
        }
        heap.swap(index, chosen);
        index = chosen;
    }
    root
}

fn exact_standard_grid_route(
    start: (i64, i64),
    goal: (i64, i64),
    lane_id: i64,
    jump_height: bool,
) -> Option<Vec<(i64, i64)>> {
    if !(0..STANDARD_PATH_WIDTH).contains(&start.0)
        || !(0..STANDARD_PATH_HEIGHT).contains(&start.1)
        || !(0..STANDARD_PATH_WIDTH).contains(&goal.0)
        || !(0..STANDARD_PATH_HEIGHT).contains(&goal.1)
    {
        return None;
    }
    let cell_count = (STANDARD_PATH_WIDTH * STANDARD_PATH_HEIGHT) as usize;
    let start_index = (start.1 * STANDARD_PATH_WIDTH + start.0) as usize;
    let goal_index = (goal.1 * STANDARD_PATH_WIDTH + goal.0) as usize;
    let mut parents = vec![usize::MAX; cell_count];
    let mut priorities = vec![0_i64; cell_count];
    let mut discovered = vec![false; cell_count];
    let mut heap = Vec::with_capacity(cell_count);
    discovered[start_index] = true;
    heap.push(start_index);

    const NEIGHBORS: [(i64, i64, i64); 8] = [
        (0, -1, 10),
        (0, 1, 10),
        (-1, 0, 10),
        (1, 0, 10),
        (-1, -1, 14),
        (-1, 1, 14),
        (1, 1, 14),
        (1, -1, 14),
    ];
    let mut found = false;
    while !heap.is_empty() {
        let current = native_path_heap_pop(&mut heap, &priorities);
        if current == goal_index {
            found = true;
            break;
        }
        let current_x = current as i64 % STANDARD_PATH_WIDTH;
        let current_y = current as i64 / STANDARD_PATH_WIDTH;
        for (delta_x, delta_y, step_cost) in NEIGHBORS {
            let neighbor_x = current_x + delta_x;
            let neighbor_y = current_y + delta_y;
            if !(0..STANDARD_PATH_WIDTH).contains(&neighbor_x)
                || !(0..STANDARD_PATH_HEIGHT).contains(&neighbor_y)
            {
                continue;
            }
            let neighbor = (neighbor_y * STANDARD_PATH_WIDTH + neighbor_x) as usize;
            if discovered[neighbor] {
                continue;
            }
            discovered[neighbor] = true;
            parents[neighbor] = current;
            let heuristic = 10 * (goal.0 - neighbor_x).abs().max((goal.1 - neighbor_y).abs());
            priorities[neighbor] = priorities[current]
                + step_cost * standard_path_tile_cost(neighbor_x, neighbor_y, lane_id, jump_height)
                + heuristic;
            native_path_heap_push(&mut heap, &priorities, neighbor);
        }
    }
    if !found {
        return None;
    }
    let mut route = Vec::new();
    let mut current = goal_index;
    loop {
        route.push((
            current as i64 % STANDARD_PATH_WIDTH,
            current as i64 / STANDARD_PATH_WIDTH,
        ));
        if current == start_index {
            break;
        }
        current = parents[current];
        if current == usize::MAX {
            return None;
        }
    }
    route.reverse();
    Some(route)
}

#[pyfunction]
fn standard_grid_route(
    start: (i64, i64),
    goal: (i64, i64),
    lane_id: i64,
    jump_height: bool,
) -> Option<Vec<(i64, i64)>> {
    exact_standard_grid_route(start, goal, lane_id, jump_height)
}

fn sha256_hex(payload: &[u8]) -> String {
    format!("{:x}", Sha256::digest(payload))
}

fn integer_sqrt(value: u128) -> i64 {
    if value < 2 {
        return value as i64;
    }
    let mut low = 1_u128;
    let mut high = value.min(i64::MAX as u128);
    while low <= high {
        let middle = (low + high) / 2;
        if middle <= value / middle {
            low = middle + 1;
        } else {
            high = middle - 1;
        }
    }
    high as i64
}

fn logic_units(value: f64) -> i64 {
    (value * 1000.0).round_ties_even() as i64
}

fn truncating_div(numerator: i128, denominator: i64) -> i64 {
    debug_assert!(denominator > 0);
    (numerator / i128::from(denominator)) as i64
}

fn vector_towards_logic_units(dx: i64, dy: i64, distance: i64) -> (i64, i64) {
    if distance <= 0 || (dx == 0 && dy == 0) {
        return (0, 0);
    }
    let squared = (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128;
    let remaining = integer_sqrt(squared).max(1);
    if distance >= remaining {
        return (dx, dy);
    }
    (
        truncating_div(i128::from(dx) * i128::from(distance), remaining),
        truncating_div(i128::from(dy) * i128::from(distance), remaining),
    )
}

fn normalized_vector_logic_units(dx: i64, dy: i64, magnitude: i64) -> (i64, i64) {
    if magnitude <= 0 || (dx == 0 && dy == 0) {
        return (0, 0);
    }
    let squared = (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128;
    let remaining = integer_sqrt(squared).max(1);
    (
        truncating_div(i128::from(dx) * i128::from(magnitude), remaining),
        truncating_div(i128::from(dy) * i128::from(magnitude), remaining),
    )
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

fn parse_next_entity_id(payload: &[u8]) -> PyResult<i64> {
    let root: Value = serde_json::from_slice(payload)
        .map_err(|error| PyValueError::new_err(format!("invalid battle checkpoint: {error}")))?;
    root.get("battle_fields")
        .and_then(|fields| fields.get("next_entity_id"))
        .and_then(Value::as_i64)
        .ok_or_else(|| PyValueError::new_err("battle checkpoint has no next_entity_id"))
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

fn optional_entity_ref_id(fields: &Map<String, Value>, name: &str) -> PyResult<Option<i64>> {
    let Some(value) = fields.get(name) else {
        return Ok(None);
    };
    if value.is_null() {
        return Ok(None);
    }
    value
        .get("$entity_ref")
        .and_then(Value::as_i64)
        .map(Some)
        .ok_or_else(|| {
            PyValueError::new_err(format!(
                "checkpoint field {name:?} is not an entity reference"
            ))
        })
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

    fn subtract_whole_hp(&mut self, loss: i64) {
        *self = match self {
            Self::Int(value) => {
                let remaining = *value - loss;
                if remaining > 0 {
                    Self::Int(remaining)
                } else {
                    // Building lifetime uses max(0.0, hp - loss), so the
                    // zero-crossing preserves Python's float sentinel.
                    Self::Float(0.0_f64.to_bits())
                }
            }
            Self::Float(bits) => {
                Self::Float((f64::from_bits(*bits) - loss as f64).max(0.0).to_bits())
            }
        };
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

fn normalized_path_cell(value: &Value) -> PyResult<(i64, i64)> {
    let values = value
        .get("$tuple")
        .and_then(Value::as_array)
        .ok_or_else(|| PyValueError::new_err("path cell is not a tuple"))?;
    if values.len() != 2 {
        return Err(PyValueError::new_err("path cell must have two values"));
    }
    let x = values[0]
        .as_i64()
        .ok_or_else(|| PyValueError::new_err("path cell x is not an integer"))?;
    let y = values[1]
        .as_i64()
        .ok_or_else(|| PyValueError::new_err("path cell y is not an integer"))?;
    Ok((x, y))
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum RouteCacheKind {
    Absent,
    Single,
    Ground,
    Unsupported,
}

struct RouteCacheInit {
    supported: bool,
    kind: RouteCacheKind,
    goal: Option<(i64, i64)>,
    cells: Vec<(i64, i64)>,
    backwards: bool,
    lane_id: i64,
    jump_height: bool,
}

fn normalized_route_cache(fields: &Map<String, Value>) -> PyResult<RouteCacheInit> {
    let cache_key = fields.get("_ground_path_cache_key");
    let route_cells = fields.get("_native_ground_route_cells");
    if cache_key.is_none() && route_cells.is_none() {
        return Ok(RouteCacheInit {
            supported: true,
            kind: RouteCacheKind::Absent,
            goal: None,
            cells: Vec::new(),
            backwards: false,
            lane_id: 0,
            jump_height: false,
        });
    }
    let Some(cache_key) = cache_key else {
        return Ok(RouteCacheInit {
            supported: false,
            kind: RouteCacheKind::Unsupported,
            goal: None,
            cells: Vec::new(),
            backwards: false,
            lane_id: 0,
            jump_height: false,
        });
    };
    if cache_key.is_null() {
        return Ok(RouteCacheInit {
            supported: route_cells.is_none(),
            kind: if route_cells.is_none() {
                RouteCacheKind::Absent
            } else {
                RouteCacheKind::Unsupported
            },
            goal: None,
            cells: Vec::new(),
            backwards: false,
            lane_id: 0,
            jump_height: false,
        });
    }
    let Some(key_values) = cache_key.get("$tuple").and_then(Value::as_array) else {
        return Ok(RouteCacheInit {
            supported: false,
            kind: RouteCacheKind::Unsupported,
            goal: None,
            cells: Vec::new(),
            backwards: false,
            lane_id: 0,
            jump_height: false,
        });
    };
    let (kind, goal, lane_id, jump_height) =
        if key_values.len() == 2 && key_values[0].as_str() == Some("single") {
            (
                RouteCacheKind::Single,
                normalized_path_cell(&key_values[1])?,
                0,
                false,
            )
        } else if key_values.len() == 3 {
            let Some(lane_id) = key_values[1].as_i64() else {
                return Ok(RouteCacheInit {
                    supported: false,
                    kind: RouteCacheKind::Unsupported,
                    goal: None,
                    cells: Vec::new(),
                    backwards: false,
                    lane_id: 0,
                    jump_height: false,
                });
            };
            let Some(jump_height) = key_values[2].as_bool() else {
                return Ok(RouteCacheInit {
                    supported: false,
                    kind: RouteCacheKind::Unsupported,
                    goal: None,
                    cells: Vec::new(),
                    backwards: false,
                    lane_id: 0,
                    jump_height: false,
                });
            };
            (
                RouteCacheKind::Ground,
                normalized_path_cell(&key_values[0])?,
                lane_id,
                jump_height,
            )
        } else {
            return Ok(RouteCacheInit {
                supported: false,
                kind: RouteCacheKind::Unsupported,
                goal: None,
                cells: Vec::new(),
                backwards: false,
                lane_id: 0,
                jump_height: false,
            });
        };
    let Some(route_values) = route_cells.and_then(Value::as_array) else {
        return Ok(RouteCacheInit {
            supported: false,
            kind: RouteCacheKind::Unsupported,
            goal: None,
            cells: Vec::new(),
            backwards: false,
            lane_id: 0,
            jump_height: false,
        });
    };
    let cells = route_values
        .iter()
        .map(normalized_path_cell)
        .collect::<PyResult<Vec<_>>>()?;
    let backwards = fields
        .get("_ground_path_cache_backwards")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let goal_in_bounds = (0..36).contains(&goal.0) && (0..64).contains(&goal.1);
    let cells_in_bounds = cells
        .iter()
        .all(|cell| (0..36).contains(&cell.0) && (0..64).contains(&cell.1));
    let shape_supported = match kind {
        RouteCacheKind::Single => !backwards && (cells.is_empty() || cells.as_slice() == [goal]),
        RouteCacheKind::Ground => true,
        RouteCacheKind::Absent | RouteCacheKind::Unsupported => false,
    };
    let supported = goal_in_bounds && cells_in_bounds && shape_supported;
    Ok(RouteCacheInit {
        supported,
        kind,
        goal: Some(goal),
        cells,
        backwards,
        lane_id,
        jump_height,
    })
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

fn absent_optional_normalized_f64(
    fields: &Map<String, Value>,
    name: &str,
) -> PyResult<Option<f64>> {
    let Some(value) = fields.get(name) else {
        return Ok(None);
    };
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

fn normalized_mapping_get<'a>(value: &'a Value, key: &str) -> Option<&'a Value> {
    value
        .get("$mapping")
        .and_then(Value::as_array)?
        .iter()
        .filter_map(Value::as_array)
        .find_map(|pair| (pair.len() == 2 && pair[0].as_str() == Some(key)).then_some(&pair[1]))
}

fn normalized_mapping_nonzero(value: &Value, key: &str) -> PyResult<bool> {
    let Some(candidate) = normalized_mapping_get(value, key) else {
        return Ok(false);
    };
    if candidate.is_null() {
        return Ok(false);
    }
    Ok(ExactScalar::from_normalized(candidate)?.as_f64() != 0.0)
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

    fn apply_slow(&mut self, duration: f64, multiplier: f64) {
        let movement = multiplier.max(0.0);
        let signature = (movement, movement, movement);
        if self.original_speed.is_none() {
            let debuff = self
                .slow_multiplier
                .max(0.0)
                .min(self.movement_mode_multiplier.max(0.0));
            self.original_speed = Some(if debuff > 1e-9 {
                self.speed.as_f64() / debuff
            } else {
                self.speed.as_f64()
            });
        }
        if let Some(effect) = self
            .slow_effects
            .iter_mut()
            .find(|effect| (effect.movement, effect.attack, effect.spawn) == signature)
        {
            effect.remaining = effect.remaining.max(duration);
        } else {
            self.slow_effects.push(ModifierEffect {
                remaining: duration,
                movement,
                attack: movement,
                spawn: movement,
            });
        }
        self.slow_timer = self
            .slow_effects
            .iter()
            .map(|effect| effect.remaining)
            .fold(0.0, f64::max);
        self.slow_multiplier = self
            .slow_effects
            .iter()
            .map(|effect| effect.movement)
            .fold(1.0, f64::min);
        self.attack_speed_debuff_multiplier = self
            .slow_effects
            .iter()
            .map(|effect| effect.attack)
            .fold(1.0, f64::min);
        self.spawn_speed_debuff_multiplier = self
            .slow_effects
            .iter()
            .map(|effect| effect.spawn)
            .fold(1.0, f64::min);
        if let Some(original_speed) = self.original_speed {
            self.speed.set_f64(
                original_speed
                    * self
                        .slow_multiplier
                        .max(0.0)
                        .min(self.movement_mode_multiplier.max(0.0)),
            );
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
    active: bool,
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
    damage: ExactScalar,
    is_alive: bool,
    target_id: Option<i64>,
    deploy_delay_remaining: f64,
    placement_pending: bool,
    spawn_hook_pending: bool,
    spawn_hook_fired: bool,
    death_spawn_target_immunity_elapsed_ms: i64,
    pending_projectile_max_duration_ms: i64,
    mechanics: Vec<String>,
    shields: Vec<ShieldState>,
    modifier_state: Option<ModifierState>,
    movement: Option<ResidentMovementState>,
    modifier_supported: bool,
    direct_combat_unsupported: Vec<String>,
    locked_combat: Option<LockedDirectCombatState>,
    building_lifetime: Option<BuildingLifetimeState>,
    building_impact: Option<BuildingImpactState>,
    point_projectile: Option<PointProjectileState>,
    object_base_movement_noop: bool,
}

#[derive(Clone)]
struct ResidentMovementState {
    vector_x_units: i64,
    vector_y_units: i64,
    vector_count: i64,
    vector_bypasses_cap: bool,
    pending_x: f64,
    pending_y: f64,
    pending_consumed: bool,
    unit_mass: f64,
    collision_radius: f64,
    building_pathing_radius: f64,
    is_hover: bool,
    native_avoidance: i64,
    native_natural_movement_active: bool,
    stop_movement_after_ms: f64,
    wait_ms: f64,
    serialized_speed: f64,
    charge_range_present: bool,
    jump_height_present: bool,
    jump_speed: f64,
    kamikaze_primed: bool,
    route_cache_supported: bool,
    route_cache_kind: RouteCacheKind,
    route_goal: Option<(i64, i64)>,
    route_cells: Vec<(i64, i64)>,
    route_backwards: bool,
    route_lane_id: i64,
    route_jump_height: bool,
    native_lane_id: i64,
    death_spawn_travel_target: Option<(f64, f64)>,
    death_spawn_travel_ticks: i64,
    knockback_target: Option<(f64, f64)>,
    knockback_velocity_work: i64,
    knockback_interrupts_combat: bool,
    river_jump_active: bool,
    river_jump_origin: Option<(f64, f64)>,
    river_jump_target: Option<(f64, f64)>,
    river_jump_elapsed: f64,
    river_jump_duration: f64,
    river_jump_blocked: bool,
    stun_interrupt_deferred_until_landing: bool,
    special_move_active: bool,
    special_move_consumed_tick: bool,
    forced_movement_active: bool,
}

impl ResidentMovementState {
    fn from_fields(
        fields: &Map<String, Value>,
        card_fields: &Map<String, Value>,
        entity_kind: i64,
    ) -> PyResult<Self> {
        let serialized_radius = optional_normalized_f64(card_fields, "collision_radius")?;
        let collision_radius = match entity_kind {
            0 => serialized_radius
                .filter(|radius| *radius != 0.0)
                .unwrap_or(0.5),
            1 => serialized_radius
                .filter(|radius| *radius != 0.0)
                .unwrap_or(0.0),
            _ => 0.0,
        };
        let building_pathing_radius = if entity_kind == 1 {
            serialized_radius
                .filter(|radius| *radius != 0.0)
                .unwrap_or(1.0)
        } else {
            0.0
        };
        let route_cache = normalized_route_cache(fields)?;
        Ok(Self {
            vector_x_units: required_i64(fields, "_movement_vector_x_units")?,
            vector_y_units: required_i64(fields, "_movement_vector_y_units")?,
            vector_count: required_i64(fields, "_movement_vector_count")?,
            vector_bypasses_cap: required_bool(fields, "_movement_vector_bypasses_cap")?,
            pending_x: normalized_f64(fields, "_pending_movement_x")?,
            pending_y: normalized_f64(fields, "_pending_movement_y")?,
            pending_consumed: required_bool(fields, "_pending_movement_consumed")?,
            unit_mass: normalized_f64(fields, "_unit_mass")?,
            collision_radius,
            building_pathing_radius,
            is_hover: required_bool(fields, "_is_hover_unit")?,
            native_avoidance: fields
                .get("_native_avoidance")
                .and_then(Value::as_i64)
                .unwrap_or(0),
            native_natural_movement_active: normalized_optional_bool(
                fields,
                "_native_natural_movement_active",
            ),
            stop_movement_after_ms: optional_normalized_f64(card_fields, "stop_movement_after_ms")?
                .unwrap_or(0.0),
            wait_ms: optional_normalized_f64(card_fields, "wait_ms")?.unwrap_or(0.0),
            serialized_speed: optional_normalized_f64(card_fields, "speed")?.unwrap_or(0.0),
            charge_range_present: optional_normalized_f64(card_fields, "charge_range")?
                .is_some_and(|value| value != 0.0),
            jump_height_present: optional_normalized_f64(card_fields, "jump_height")?
                .is_some_and(|value| value != 0.0),
            jump_speed: optional_normalized_f64(card_fields, "jump_speed")?.unwrap_or(0.0),
            kamikaze_primed: normalized_optional_bool(fields, "kamikaze_primed"),
            route_cache_supported: route_cache.supported,
            route_cache_kind: route_cache.kind,
            route_goal: route_cache.goal,
            route_cells: route_cache.cells,
            route_backwards: route_cache.backwards,
            route_lane_id: route_cache.lane_id,
            route_jump_height: route_cache.jump_height,
            native_lane_id: required_i64(fields, "_native_lane_id")?,
            death_spawn_travel_target: optional_position(fields, "_death_spawn_travel_target")?,
            death_spawn_travel_ticks: required_i64(fields, "_death_spawn_travel_ticks_remaining")?,
            knockback_target: optional_position(fields, "_knockback_target")?,
            knockback_velocity_work: required_i64(fields, "_knockback_velocity_work")?,
            knockback_interrupts_combat: fields
                .get("_knockback_interrupts_combat")
                .and_then(Value::as_bool)
                .unwrap_or(true),
            river_jump_active: normalized_optional_bool(fields, "_river_jump_active"),
            river_jump_origin: optional_position(fields, "_river_jump_origin")?,
            river_jump_target: optional_position(fields, "_river_jump_target")?,
            river_jump_elapsed: absent_optional_normalized_f64(fields, "_river_jump_elapsed")?
                .unwrap_or(0.0),
            river_jump_duration: absent_optional_normalized_f64(fields, "_river_jump_duration")?
                .unwrap_or(0.0),
            river_jump_blocked: normalized_optional_bool(fields, "_river_jump_blocked"),
            stun_interrupt_deferred_until_landing: normalized_optional_bool(
                fields,
                "_stun_interrupt_deferred_until_landing",
            ),
            special_move_active: normalized_optional_bool(fields, "_special_move_active"),
            special_move_consumed_tick: normalized_optional_bool(
                fields,
                "_special_move_consumed_tick",
            ),
            forced_movement_active: required_bool(fields, "forced_movement_active")?,
        })
    }
}

#[derive(Clone)]
struct ShieldState {
    current: ExactScalar,
    maximum: ExactScalar,
}

impl ShieldState {
    fn from_normalized(value: &Value) -> PyResult<Self> {
        let fields = object_fields(value)?;
        Ok(Self {
            current: ExactScalar::from_normalized(
                fields
                    .get("current_shield")
                    .ok_or_else(|| PyValueError::new_err("Shield has no current_shield"))?,
            )?,
            maximum: ExactScalar::from_normalized(
                fields
                    .get("max_shield")
                    .ok_or_else(|| PyValueError::new_err("Shield has no max_shield"))?,
            )?,
        })
    }

    fn diagnostic_value(&self) -> Value {
        json!({
            "current_shield": self.current.diagnostic_value(),
            "max_shield": self.maximum.diagnostic_value(),
        })
    }
}

#[derive(Clone)]
struct BuildingImpactState {
    collision_radius: f64,
    crown_slot: Option<String>,
    requires_activation: bool,
    tower_active: bool,
    activation_delay_seconds: f64,
    activation_delay_remaining: f64,
    activation_first_hit_delay_seconds: f64,
    activation_first_hit_delay_remaining: f64,
    stealth_until_ms: i64,
    allow_area_damage_when_invisible: bool,
}

impl BuildingImpactState {
    fn from_fields(
        fields: &Map<String, Value>,
        card_fields: &Map<String, Value>,
    ) -> PyResult<Self> {
        Ok(Self {
            collision_radius: normalized_f64(fields, "_collision_radius")?,
            crown_slot: fields
                .get("_crown_tower_slot")
                .and_then(Value::as_str)
                .map(str::to_owned),
            requires_activation: required_bool(fields, "requires_activation")?,
            tower_active: fields
                .get("_tower_active")
                .and_then(Value::as_bool)
                .unwrap_or(true),
            activation_delay_seconds: normalized_f64(fields, "activation_delay_seconds")?,
            activation_delay_remaining: normalized_f64(fields, "activation_delay_remaining")?,
            activation_first_hit_delay_seconds: normalized_f64(
                fields,
                "activation_first_hit_delay_seconds",
            )?,
            activation_first_hit_delay_remaining: normalized_f64(
                fields,
                "activation_first_hit_delay_remaining",
            )?,
            stealth_until_ms: fields
                .get("_stealth_until")
                .and_then(Value::as_i64)
                .unwrap_or(0),
            allow_area_damage_when_invisible: normalized_optional_bool(
                card_fields,
                "allow_area_damage_when_invisible",
            ),
        })
    }
}

#[derive(Clone)]
struct PointProjectileState {
    target_x: f64,
    target_y: f64,
    travel_speed: f64,
    splash_radius: f64,
    hits_air: bool,
    hits_ground: bool,
    ignore_buildings: bool,
    crown_tower_damage: Option<f64>,
    crown_tower_damage_multiplier: f64,
    stun_duration: f64,
    slow_duration: f64,
    slow_multiplier: f64,
    launch_delay: f64,
    primary_target_id: Option<i64>,
    source_entity_id: Option<i64>,
    tracks_target: bool,
    temporary_homing_remaining_ms: i64,
    temporary_homing_target_id: Option<i64>,
    permanent_homing_disabled_by_temporary: bool,
    start_collision_resolved: bool,
    unsupported: Vec<String>,
}

impl PointProjectileState {
    fn from_fields(fields: &Map<String, Value>) -> PyResult<Self> {
        let target = object_fields(
            fields
                .get("target_position")
                .ok_or_else(|| PyValueError::new_err("projectile has no target_position"))?,
        )?;
        let mut unsupported = Vec::new();
        let splash_radius = normalized_f64(fields, "splash_radius")?;
        let stun_duration = normalized_f64(fields, "stun_duration")?;
        let slow_duration = normalized_f64(fields, "slow_duration")?;
        let slow_multiplier = normalized_f64(fields, "slow_multiplier")?;
        let knockback_distance = normalized_f64(fields, "knockback_distance")?;
        let damage_waves = required_i64(fields, "damage_waves")?;
        let damage_wave_interval = normalized_f64(fields, "damage_wave_interval")?;
        let pierces = required_bool(fields, "pierces")?;
        let projectile_range = normalized_f64(fields, "projectile_range")?;
        required_i64(fields, "homing_time_ms")?;
        let start_extra_radius = normalized_f64(fields, "start_extra_radius")?;
        if knockback_distance != 0.0 {
            unsupported.push("knockback_payload".to_owned());
        }
        if damage_waves != 1 || damage_wave_interval != 0.0 {
            unsupported.push("damage_waves".to_owned());
        }
        if pierces || projectile_range != 0.0 || start_extra_radius != 0.0 {
            unsupported.push("piercing_payload".to_owned());
        }
        let spawn_projectile_data_present = fields
            .get("spawn_projectile_data")
            .is_some_and(|value| !value.is_null());
        if spawn_projectile_data_present {
            unsupported.push("child_projectiles".to_owned());
        }
        for (name, value) in [
            ("target_x", normalized_f64(target, "x")?),
            ("target_y", normalized_f64(target, "y")?),
            ("travel_speed", normalized_f64(fields, "travel_speed")?),
            ("launch_delay", normalized_f64(fields, "launch_delay")?),
        ] {
            if !value.is_finite() {
                unsupported.push(format!("nonfinite_{name}"));
            }
        }
        Ok(Self {
            target_x: normalized_f64(target, "x")?,
            target_y: normalized_f64(target, "y")?,
            travel_speed: normalized_f64(fields, "travel_speed")?,
            splash_radius,
            hits_air: required_bool(fields, "hits_air")?,
            hits_ground: required_bool(fields, "hits_ground")?,
            ignore_buildings: required_bool(fields, "ignore_buildings")?,
            crown_tower_damage: optional_normalized_f64(fields, "crown_tower_damage")?,
            crown_tower_damage_multiplier: normalized_f64(fields, "crown_tower_damage_multiplier")?,
            stun_duration,
            slow_duration,
            slow_multiplier,
            launch_delay: normalized_f64(fields, "launch_delay")?,
            primary_target_id: optional_entity_ref_id(fields, "primary_target")?,
            source_entity_id: optional_entity_ref_id(fields, "source_entity")?,
            tracks_target: required_bool(fields, "tracks_target")?,
            temporary_homing_remaining_ms: fields
                .get("_temporary_homing_remaining_ms")
                .and_then(Value::as_i64)
                .unwrap_or(0),
            temporary_homing_target_id: optional_entity_ref_id(fields, "_temporary_homing_target")?,
            permanent_homing_disabled_by_temporary: fields
                .get("_permanent_homing_disabled_by_temporary")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            start_collision_resolved: required_bool(fields, "start_collision_resolved")?,
            unsupported,
        })
    }

    fn diagnostic_value(&self, entity: &ResidentEntity) -> Value {
        json!({
            "encounter_index": entity.encounter_index,
            "crown_tower_damage": self.crown_tower_damage.map(exact_f64_value),
            "crown_tower_damage_multiplier": exact_f64_value(self.crown_tower_damage_multiplier),
            "hitpoints": entity.hitpoints.diagnostic_value(),
            "id": entity.id,
            "ignore_buildings": self.ignore_buildings,
            "is_alive": entity.is_alive,
            "launch_delay": exact_f64_value(self.launch_delay),
            "permanent_homing_disabled_by_temporary": self.permanent_homing_disabled_by_temporary,
            "position_x": entity.position_x.diagnostic_value(),
            "position_y": entity.position_y.diagnostic_value(),
            "splash_radius": exact_f64_value(self.splash_radius),
            "slow_duration": exact_f64_value(self.slow_duration),
            "slow_multiplier": exact_f64_value(self.slow_multiplier),
            "stun_duration": exact_f64_value(self.stun_duration),
            "target_position_x": exact_f64_value(self.target_x),
            "target_position_y": exact_f64_value(self.target_y),
            "start_collision_resolved": self.start_collision_resolved,
            "temporary_homing_remaining_ms": self.temporary_homing_remaining_ms,
            "temporary_homing_target_id": self.temporary_homing_target_id,
        })
    }
}

#[derive(Clone)]
struct BuildingLifetimeState {
    lifetime_ms: Option<i64>,
    lifetime_elapsed: f64,
    decay_work: i64,
    tick_carry_ms: f64,
}

impl BuildingLifetimeState {
    fn from_fields(
        fields: &Map<String, Value>,
        card_fields: &Map<String, Value>,
    ) -> PyResult<Self> {
        Ok(Self {
            lifetime_ms: card_fields.get("lifetime_ms").and_then(Value::as_i64),
            lifetime_elapsed: normalized_f64(fields, "lifetime_elapsed")?,
            decay_work: required_i64(fields, "lifetime_decay_work")?,
            tick_carry_ms: normalized_f64(fields, "lifetime_tick_carry_ms")?,
        })
    }

    fn diagnostic_value(&self, entity: &ResidentEntity) -> Value {
        let impact = entity
            .building_impact
            .as_ref()
            .expect("building lifetime requires impact state");
        json!({
            "activation_delay_remaining": exact_f64_value(impact.activation_delay_remaining),
            "activation_first_hit_delay_remaining": exact_f64_value(impact.activation_first_hit_delay_remaining),
            "crown_slot": impact.crown_slot,
            "encounter_index": entity.encounter_index,
            "hitpoints": entity.hitpoints.diagnostic_value(),
            "id": entity.id,
            "is_alive": entity.is_alive,
            "lifetime_decay_work": self.decay_work,
            "lifetime_elapsed": exact_f64_value(self.lifetime_elapsed),
            "lifetime_tick_carry_ms": exact_f64_value(self.tick_carry_ms),
            "tower_active": impact.tower_active,
        })
    }
}

#[derive(Clone)]
struct LockedDirectCombatState {
    damage: f64,
    range: f64,
    sight_range: f64,
    attack_cooldown: f64,
    attack_windup_active: bool,
    attack_preload_blocked: bool,
    last_attack_time: f64,
    stun_timer: f64,
    collision_radius: f64,
    native_target_distance_discount_sq_units: i64,
    is_air_unit: bool,
    is_airborne_for_projectile: bool,
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
    retarget_ms: i64,
    targets_only_buildings: bool,
    native_building_target: bool,
    ground_path_backwards: bool,
    sight_clip: f64,
    sight_clip_side: f64,
    hidden_building: bool,
    stealth_until_ms: i64,
    allow_area_damage_when_invisible: bool,
    point_weapon: Option<PointWeapon>,
}

#[derive(Clone)]
struct PointWeapon {
    travel_speed: f64,
    tracks_target: bool,
    start_radius: f64,
    y_offset: f64,
    splash_radius: f64,
    hit_planes: Option<(bool, bool)>,
    crown_tower_damage_multiplier: f64,
    stun_duration: f64,
    slow_duration: f64,
    slow_multiplier: f64,
}

enum CombatPayload {
    DirectDamage(f64),
    PointProjectile(PointWeapon),
}

impl PointWeapon {
    fn from_card_fields(
        card_fields: &Map<String, Value>,
        unsupported: &mut Vec<String>,
    ) -> PyResult<Option<Self>> {
        let Some(projectile_data) = card_fields.get("projectile_data") else {
            return Ok(None);
        };
        if projectile_data.is_null() {
            return Ok(None);
        }
        for (field, reason) in [
            ("pushback", "projectile_pushback"),
            ("projectileRange", "projectile_range"),
            ("homingTime", "temporary_homing"),
            ("projectileStartExtraRadius", "projectile_start_collision"),
        ] {
            if normalized_mapping_nonzero(projectile_data, field)? {
                unsupported.push(reason.to_owned());
            }
        }
        for (field, reason) in [("spawnProjectileData", "child_projectiles")] {
            if normalized_mapping_get(projectile_data, field).is_some_and(|value| !value.is_null())
            {
                unsupported.push(reason.to_owned());
            }
        }
        let Some(speed_value) = normalized_mapping_get(projectile_data, "speed") else {
            unsupported.push("missing_projectile_speed".to_owned());
            return Ok(None);
        };
        let speed = ExactScalar::from_normalized(speed_value)?.as_f64();
        if !speed.is_finite() || speed <= 0.0 {
            unsupported.push("invalid_projectile_speed".to_owned());
        }
        let tracks_target = match normalized_mapping_get(projectile_data, "homing") {
            None => true,
            Some(value) => match value.as_bool() {
                Some(value) => value,
                None => {
                    unsupported.push("invalid_projectile_homing".to_owned());
                    true
                }
            },
        };
        let start_radius =
            optional_normalized_f64(card_fields, "projectile_start_radius")?.unwrap_or(0.0);
        let y_offset = optional_normalized_f64(card_fields, "projectile_y_offset")?.unwrap_or(0.0);
        let splash_radius = normalized_mapping_get(projectile_data, "radius")
            .map(ExactScalar::from_normalized)
            .transpose()?
            .map_or(0.0, |value| value.as_f64() / 1000.0);
        for field in ["hitsAir", "hitsGround"] {
            if normalized_mapping_get(projectile_data, field)
                .is_some_and(|value| !value.is_boolean())
            {
                unsupported.push("invalid_projectile_plane_override".to_owned());
            }
        }
        if normalized_mapping_get(projectile_data, "tidTarget")
            .is_some_and(|value| !value.is_string())
        {
            unsupported.push("invalid_projectile_plane_override".to_owned());
        }
        let hit_planes = if normalized_mapping_get(projectile_data, "hitsAir").is_some()
            || normalized_mapping_get(projectile_data, "hitsGround").is_some()
        {
            Some((
                normalized_mapping_get(projectile_data, "hitsAir")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
                normalized_mapping_get(projectile_data, "hitsGround")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
            ))
        } else {
            normalized_mapping_get(projectile_data, "tidTarget")
                .and_then(Value::as_str)
                .filter(|value| !value.is_empty())
                .map(|target_type| {
                    (
                        target_type.contains("AIR"),
                        target_type.contains("GROUND") || target_type.contains("BUILDINGS"),
                    )
                })
        };
        let crown_percent = normalized_mapping_get(projectile_data, "crownTowerDamagePercent")
            .map(ExactScalar::from_normalized)
            .transpose()?
            .map_or(0.0, |value| value.as_f64());
        let crown_tower_damage_multiplier = (1.0 + crown_percent / 100.0).max(0.0);
        let target_buff_data = normalized_mapping_get(projectile_data, "targetBuffData");
        if target_buff_data
            .is_some_and(|value| value.get("$mapping").and_then(Value::as_array).is_none())
        {
            unsupported.push("invalid_projectile_status".to_owned());
        }
        let buff_time_ms = normalized_mapping_get(projectile_data, "buffTime")
            .map(ExactScalar::from_normalized)
            .transpose()?
            .map_or(0.0, |value| value.as_f64());
        let speed_percent = target_buff_data
            .and_then(|value| normalized_mapping_get(value, "speedMultiplier"))
            .map(ExactScalar::from_normalized)
            .transpose()?
            .map_or(0.0, |value| value.as_f64());
        let hit_speed_percent = target_buff_data
            .and_then(|value| normalized_mapping_get(value, "hitSpeedMultiplier"))
            .map(ExactScalar::from_normalized)
            .transpose()?
            .map_or(0.0, |value| value.as_f64());
        let mut stun_duration = 0.0;
        let mut slow_duration = buff_time_ms / 1000.0;
        let mut slow_multiplier = (1.0 + speed_percent / 100.0).max(0.0);
        if speed_percent == -100.0 && hit_speed_percent == -100.0 && slow_duration > 0.0 {
            stun_duration = slow_duration;
            slow_duration = 0.0;
            slow_multiplier = 1.0;
        }
        if !start_radius.is_finite()
            || !y_offset.is_finite()
            || !splash_radius.is_finite()
            || !crown_tower_damage_multiplier.is_finite()
            || !stun_duration.is_finite()
            || !slow_duration.is_finite()
            || !slow_multiplier.is_finite()
        {
            unsupported.push("nonfinite_projectile_launch_geometry".to_owned());
        }
        Ok(Some(Self {
            travel_speed: speed / 1000.0 / 0.05,
            tracks_target,
            start_radius,
            y_offset,
            splash_radius,
            hit_planes,
            crown_tower_damage_multiplier,
            stun_duration,
            slow_duration,
            slow_multiplier,
        }))
    }
}

impl LockedDirectCombatState {
    fn from_fields(
        fields: &Map<String, Value>,
        card_fields: &Map<String, Value>,
        direct_combat_unsupported: &mut Vec<String>,
    ) -> PyResult<Self> {
        let projectile_reason_count = direct_combat_unsupported.len();
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
        let retarget_ms = if load_time_ms > hit_speed_ms {
            load_time_ms - hit_speed_ms
        } else {
            (hit_speed_ms - load_time_ms).max(0)
        };
        let point_weapon = PointWeapon::from_card_fields(card_fields, direct_combat_unsupported)?;
        if direct_combat_unsupported.len() > projectile_reason_count {
            direct_combat_unsupported.push("projectile_payload".to_owned());
        }
        Ok(Self {
            damage: normalized_f64(fields, "damage")?,
            range: normalized_f64(fields, "range")?,
            sight_range: normalized_f64(fields, "sight_range")?,
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
            is_airborne_for_projectile: required_bool(fields, "is_air_unit")?
                || normalized_optional_bool(fields, "_river_jump_active"),
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
            retarget_ms,
            targets_only_buildings: normalized_optional_bool(card_fields, "targets_only_buildings"),
            native_building_target: normalized_optional_bool(card_fields, "building_target")
                || card_fields
                    .get("summon_character_data")
                    .and_then(|value| normalized_mapping_get(value, "buildingTarget"))
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
            ground_path_backwards: normalized_optional_bool(fields, "_ground_path_backwards"),
            sight_clip: optional_normalized_f64(card_fields, "sight_clip")?.unwrap_or(0.0),
            sight_clip_side: optional_normalized_f64(card_fields, "sight_clip_side")?
                .unwrap_or(0.0),
            hidden_building: normalized_optional_bool(fields, "_hidden_building"),
            stealth_until_ms: fields
                .get("_stealth_until")
                .and_then(Value::as_i64)
                .unwrap_or(0),
            allow_area_damage_when_invisible: normalized_optional_bool(
                card_fields,
                "allow_area_damage_when_invisible",
            ),
            point_weapon,
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
    fn has_only_shield_mechanics(&self) -> bool {
        self.mechanics.len() == self.shields.len()
    }

    fn apply_incoming_damage(&mut self, mut amount: f64) -> f64 {
        for shield in &mut self.shields {
            if amount <= 0.0 {
                return 0.0;
            }
            let current = shield.current.as_f64();
            if current <= 0.0 {
                continue;
            }
            shield.current.set_f64((current - amount).max(0.0));
            amount = 0.0;
        }
        amount
    }

    fn apply_projectile_status(
        &mut self,
        stun_duration: f64,
        slow_duration: f64,
        slow_multiplier: f64,
    ) {
        if stun_duration > 0.0 {
            if let Some(modifiers) = self.modifier_state.as_mut() {
                modifiers.stun_timer = modifiers.stun_timer.max(stun_duration);
            }
            if let Some(combat) = self.locked_combat.as_mut() {
                combat.stun_timer = combat.stun_timer.max(stun_duration);
                combat.last_combat_target_id = None;
                combat.attack_cooldown = combat.base_attack_interval();
                combat.attack_windup_active = false;
                combat.has_attacked_once = false;
            }
            self.target_id = None;
        }
        if slow_duration > 0.0
            && slow_multiplier < 1.0
            && let Some(modifiers) = self.modifier_state.as_mut()
        {
            modifiers.apply_slow(slow_duration, slow_multiplier);
            if let Some(combat) = self.locked_combat.as_mut() {
                combat.attack_speed_debuff_multiplier = modifiers.attack_speed_debuff_multiplier;
            }
        }
    }

    fn projectile_target_traits(&self) -> Option<(bool, f64, i64, bool)> {
        match self.entity_kind {
            0 => self.locked_combat.as_ref().map(|state| {
                (
                    state.is_airborne_for_projectile,
                    state.collision_radius,
                    state.stealth_until_ms,
                    state.allow_area_damage_when_invisible,
                )
            }),
            1 => self.building_impact.as_ref().map(|state| {
                (
                    false,
                    state.collision_radius,
                    state.stealth_until_ms,
                    state.allow_area_damage_when_invisible,
                )
            }),
            _ => None,
        }
    }

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
        let mechanic_values = fields
            .get("mechanics")
            .and_then(Value::as_array)
            .ok_or_else(|| PyValueError::new_err("entity mechanics is not a list"))?;
        let mechanics = mechanic_values
            .iter()
            .map(object_type)
            .collect::<PyResult<Vec<_>>>()?;
        let shields = mechanic_values
            .iter()
            .filter_map(|mechanic| {
                (object_type(mechanic).ok()?.as_str() == "clasher.mechanics.shared.shield.Shield")
                    .then_some(ShieldState::from_normalized(mechanic))
            })
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
        let movement = if is_character {
            Some(ResidentMovementState::from_fields(
                fields,
                card_fields,
                entity_kind,
            )?)
        } else {
            None
        };
        let mut direct_combat_unsupported = Vec::new();
        let locked_combat = if is_character {
            Some(LockedDirectCombatState::from_fields(
                fields,
                card_fields,
                &mut direct_combat_unsupported,
            )?)
        } else {
            None
        };
        let building_lifetime = if entity_kind == 1 {
            Some(BuildingLifetimeState::from_fields(fields, card_fields)?)
        } else {
            None
        };
        let building_impact = if entity_kind == 1 {
            Some(BuildingImpactState::from_fields(fields, card_fields)?)
        } else {
            None
        };
        let point_projectile = if object_type(value)? == "clasher.entities.Projectile" {
            Some(PointProjectileState::from_fields(fields)?)
        } else {
            None
        };
        let pending_movement_x = normalized_f64(fields, "_pending_movement_x")?;
        let pending_movement_y = normalized_f64(fields, "_pending_movement_y")?;
        let object_base_movement_noop = required_i64(fields, "_movement_vector_x_units")? == 0
            && required_i64(fields, "_movement_vector_y_units")? == 0
            && required_i64(fields, "_movement_vector_count")? == 0
            && !required_bool(fields, "_movement_vector_bypasses_cap")?
            && pending_movement_x.to_bits() == 0.0_f64.to_bits()
            && pending_movement_y.to_bits() == 0.0_f64.to_bits()
            && required_bool(fields, "_pending_movement_consumed")?;
        if !is_character {
            direct_combat_unsupported.push("non_character_entity".to_owned());
        }
        if shields.len() != mechanics.len() {
            direct_combat_unsupported.push("executable_mechanics".to_owned());
        }
        let uses_projectile_weapon = locked_combat
            .as_ref()
            .is_some_and(|state| state.point_weapon.is_some());
        for (field, reason) in [
            ("attack_pushback", "attack_pushback"),
            ("charge_range", "charge_payload"),
        ] {
            if normalized_optional_number_is_nonzero(card_fields, field)? {
                direct_combat_unsupported.push(reason.to_owned());
            }
        }
        if !uses_projectile_weapon {
            for (field, reason) in [
                ("area_damage_radius", "area_damage"),
                ("projectile_splash_radius", "projectile_splash"),
            ] {
                if normalized_optional_number_is_nonzero(card_fields, field)? {
                    direct_combat_unsupported.push(reason.to_owned());
                }
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
            active: true,
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
            damage: ExactScalar::from_normalized(
                fields
                    .get("damage")
                    .ok_or_else(|| PyValueError::new_err("entity has no damage"))?,
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
            pending_projectile_max_duration_ms: required_i64(
                fields,
                "_pending_projectile_max_duration_ms",
            )?,
            mechanics,
            shields,
            modifier_state,
            movement,
            modifier_supported,
            direct_combat_unsupported,
            locked_combat,
            building_lifetime,
            building_impact,
            point_projectile,
            object_base_movement_noop,
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
            "pending_projectile_max_duration_ms": self.pending_projectile_max_duration_ms,
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
        matches!(self.entity_kind, 0 | 1) && self.has_only_shield_mechanics()
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

    fn building_lifetime_diagnostic_value(&self) -> Option<Value> {
        self.building_lifetime
            .as_ref()
            .map(|state| state.diagnostic_value(self))
    }

    fn point_projectile_diagnostic_value(&self) -> Option<Value> {
        self.point_projectile
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
    king_tower_hp: ExactScalar,
    left_tower_hp: ExactScalar,
    right_tower_hp: ExactScalar,
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
            king_tower_hp: ExactScalar::Float(king_tower_hp.to_bits()),
            left_tower_hp: ExactScalar::Float(left_tower_hp.to_bits()),
            right_tower_hp: ExactScalar::Float(right_tower_hp.to_bits()),
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
            self.king_tower_hp.as_f64(),
            self.left_tower_hp.as_f64(),
            self.right_tower_hp.as_f64(),
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
        payload.extend_from_slice(&self.king_tower_hp.as_f64().to_bits().to_le_bytes());
        payload.extend_from_slice(&self.left_tower_hp.as_f64().to_bits().to_le_bytes());
        payload.extend_from_slice(&self.right_tower_hp.as_f64().to_bits().to_le_bytes());
    }

    fn towers_lost(&self) -> i64 {
        if self.king_tower_hp.as_f64() <= 0.0 {
            return 3;
        }
        i64::from(self.left_tower_hp.as_f64() <= 0.0)
            + i64::from(self.right_tower_hp.as_f64() <= 0.0)
    }

    fn lowest_tower_hp_milli(&self, towers: &[ResidentTower]) -> i64 {
        towers
            .iter()
            .filter(|tower| {
                tower.active && tower.player_id == self.player_id && tower.hp.as_f64() > 0.0
            })
            .map(|tower| tower.hp_milli)
            .min()
            .unwrap_or(0)
    }
}

#[derive(Clone)]
struct ResidentTower {
    active: bool,
    id: i64,
    player_id: i64,
    slot: String,
    hp: ExactScalar,
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
            active: true,
            id,
            player_id,
            slot,
            hp: ExactScalar::Float(hp.to_bits()),
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
            self.hp.as_f64(),
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
        payload.extend_from_slice(&self.hp.as_f64().to_bits().to_le_bytes());
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
    checkpoint: Arc<[u8]>,
    checkpoint_sha256: String,
    checkpoint_current: bool,
    schema_version: u64,
    checkpoint_generation: u64,
    tick: i64,
    time: f64,
    dt: f64,
    arena_width_tiles: i64,
    arena_height_tiles: i64,
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
    win_conditions_dirty: bool,
    sudden_death: bool,
    sudden_death_crowns: (i64, i64),
    tiebreaker_time: f64,
    winner: Option<i64>,
    entities: Vec<ResidentEntity>,
    next_entity_id: i64,
    lethal_projectile_reservation_ids: Vec<i64>,
    pending_spell_casts_empty: bool,
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
        arena_width_tiles,
        arena_height_tiles,
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
        win_conditions_dirty,
        sudden_death,
        sudden_death_crowns,
        tiebreaker_time,
        winner,
        pending_spell_casts_empty
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        checkpoint: &[u8],
        tick: i64,
        time: f64,
        dt: f64,
        arena_width_tiles: i64,
        arena_height_tiles: i64,
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
        win_conditions_dirty: bool,
        sudden_death: bool,
        sudden_death_crowns: (i64, i64),
        tiebreaker_time: f64,
        winner: Option<i64>,
        pending_spell_casts_empty: bool,
    ) -> PyResult<Self> {
        if !time.is_finite() || !dt.is_finite() || dt < 0.0 {
            return Err(PyValueError::new_err(
                "battle time and non-negative dt must be finite",
            ));
        }
        if arena_width_tiles < 1 || arena_height_tiles < 1 {
            return Err(PyValueError::new_err(
                "resident arena dimensions must be positive",
            ));
        }
        let schema_version = validate_checkpoint(checkpoint)?;
        let entities = parse_resident_entities(checkpoint)?;
        let next_entity_id = parse_next_entity_id(checkpoint)?;
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
            checkpoint: Arc::from(checkpoint),
            checkpoint_sha256: sha256_hex(checkpoint),
            checkpoint_current: true,
            schema_version,
            checkpoint_generation: 0,
            tick,
            time,
            dt,
            arena_width_tiles,
            arena_height_tiles,
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
            win_conditions_dirty,
            sudden_death,
            sudden_death_crowns,
            tiebreaker_time,
            winner,
            entities,
            next_entity_id,
            lethal_projectile_reservation_ids: Vec::new(),
            pending_spell_casts_empty,
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
        self.sync_player_crown_hitpoints();
        self.win_conditions_dirty = false;
        let king_alive = (
            self.players[0].king_tower_hp.as_f64() > 0.0,
            self.players[1].king_tower_hp.as_f64() > 0.0,
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
        self.towers
            .iter()
            .filter(|tower| tower.active)
            .map(ResidentTower::state_tuple)
            .collect()
    }

    fn outcome_state(&self) -> (bool, bool, Option<i64>, (i64, i64)) {
        (
            self.sudden_death,
            self.game_over,
            self.winner,
            self.sudden_death_crowns,
        )
    }

    fn win_conditions_dirty(&self) -> bool {
        self.win_conditions_dirty
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
        payload.extend_from_slice(
            &(self.towers.iter().filter(|tower| tower.active).count() as u64).to_le_bytes(),
        );
        for tower in self.towers.iter().filter(|tower| tower.active) {
            tower.append_hash_payload(&mut payload);
        }
        sha256_hex(&payload)
    }

    fn entity_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active)
            .map(ResidentEntity::diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize resident entities: {error}"))
        })
    }

    fn entity_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.entity_state_bytes()?))
    }

    fn next_entity_id(&self) -> i64 {
        self.next_entity_id
    }

    fn supports_modifier_phase(&self) -> bool {
        self.entities
            .iter()
            .all(|entity| !entity.active || entity.modifier_supported)
    }

    fn advance_modifier_phase(&mut self) -> PyResult<()> {
        if !self.supports_modifier_phase() {
            return Err(PyRuntimeError::new_err(
                "resident modifier phase contains periodic damage or callback-owned temporary buffs",
            ));
        }
        self.checkpoint_current = false;
        for entity in &mut self.entities {
            if !entity.active {
                continue;
            }
            if !entity.is_alive {
                continue;
            }
            if let Some(state) = &mut entity.modifier_state {
                state.advance(self.dt);
                let stun_timer = state.stun_timer;
                let attack_speed_debuff_multiplier = state.attack_speed_debuff_multiplier;
                let attack_speed_buff_multiplier = state.attack_speed_buff_multiplier;
                if let Some(combat) = entity.locked_combat.as_mut() {
                    combat.stun_timer = stun_timer;
                    combat.attack_speed_debuff_multiplier = attack_speed_debuff_multiplier;
                    combat.attack_speed_buff_multiplier = attack_speed_buff_multiplier;
                }
            }
        }
        Ok(())
    }

    fn modifier_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active)
            .filter_map(ResidentEntity::modifier_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize modifier state: {error}"))
        })
    }

    fn modifier_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.modifier_state_bytes()?))
    }

    fn shield_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active && !entity.shields.is_empty())
            .map(|entity| {
                json!({
                    "encounter_index": entity.encounter_index,
                    "id": entity.id,
                    "shields": entity
                        .shields
                        .iter()
                        .map(ShieldState::diagnostic_value)
                        .collect::<Vec<_>>(),
                })
            })
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!("failed to serialize shield state: {error}"))
        })
    }

    fn shield_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.shield_state_bytes()?))
    }

    fn supports_character_object_phase(&self) -> bool {
        self.entities
            .iter()
            .all(|entity| !entity.active || entity.supports_character_object_phase())
    }

    fn advance_character_object_phase(&mut self) -> PyResult<()> {
        if !self.supports_character_object_phase() {
            return Err(PyRuntimeError::new_err(
                "resident character object phase contains non-character entities or executable mechanics",
            ));
        }
        self.checkpoint_current = false;
        for entity in &mut self.entities {
            if !entity.active {
                continue;
            }
            entity.advance_character_object_phase(self.dt);
        }
        Ok(())
    }

    fn character_object_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active)
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

    fn supports_resident_object_phase(&self) -> bool {
        self.resident_id_invariants_hold()
            && self.supports_point_projectile_phase()
            && self.entities.iter().all(|entity| {
                !entity.active
                    || (entity.entity_kind == 2 && entity.object_base_movement_noop)
                    || entity.supports_character_object_phase()
            })
    }

    fn advance_resident_object_phase(&mut self) -> PyResult<()> {
        if !self.supports_resident_object_phase() {
            return Err(PyRuntimeError::new_err(
                "resident object phase rejected unsupported object or character callback",
            ));
        }
        self.checkpoint_current = false;
        let mut processed_ids = Vec::<i64>::new();
        loop {
            let mut pending = self
                .entities
                .iter()
                .enumerate()
                .filter_map(|(index, entity)| {
                    (entity.active && !processed_ids.contains(&entity.id)).then_some(index)
                })
                .collect::<Vec<_>>();
            if pending.is_empty() {
                break;
            }
            pending.sort_unstable_by_key(|index| self.entities[*index].id);
            for entity_index in pending {
                let entity_id = self.entities[entity_index].id;
                processed_ids.push(entity_id);
                if !self.entities[entity_index].is_alive {
                    continue;
                }
                match self.entities[entity_index].entity_kind {
                    0 | 1 => self.entities[entity_index].advance_character_object_phase(self.dt),
                    2 => self.advance_point_projectile(entity_index),
                    _ => unreachable!("resident object preflight validates object kinds"),
                }
                self.quantize_resident_position(entity_index);
            }
        }
        Ok(())
    }

    fn quantize_resident_position(&mut self, entity_index: usize) {
        let quantized_x = logic_units(self.entities[entity_index].position_x.as_f64());
        let quantized_y = logic_units(self.entities[entity_index].position_y.as_f64());
        self.entities[entity_index]
            .position_x
            .set_f64(quantized_x as f64 / 1000.0);
        self.entities[entity_index]
            .position_y
            .set_f64(quantized_y as f64 / 1000.0);
    }

    fn supports_stationary_movement_phase(&self) -> bool {
        self.entities.iter().all(|entity| {
            if !entity.active || !matches!(entity.entity_kind, 0 | 1) || !entity.is_alive {
                return true;
            }
            let (Some(movement), Some(combat)) =
                (entity.movement.as_ref(), entity.locked_combat.as_ref())
            else {
                return false;
            };
            entity.deploy_delay_remaining <= 0.0
                && entity.has_only_shield_mechanics()
                && movement.vector_count >= 0
                && movement.unit_mass.is_finite()
                && movement.unit_mass > 0.0
                && movement.collision_radius.is_finite()
                && movement.building_pathing_radius.is_finite()
                && entity.position_x.as_f64().is_finite()
                && entity.position_y.as_f64().is_finite()
                && movement.pending_x.is_finite()
                && movement.pending_y.is_finite()
                && movement.death_spawn_travel_ticks == 0
                && movement.death_spawn_travel_target.is_none()
                && movement.knockback_target.is_none()
                && movement.knockback_velocity_work == 0
                && !movement.river_jump_active
                && !movement.special_move_active
                && !movement.special_move_consumed_tick
                && !movement.forced_movement_active
                && (entity.entity_kind == 1 || combat.movement_target_id.is_none())
        })
    }

    fn advance_stationary_movement_phase(&mut self) -> PyResult<()> {
        if !self.supports_stationary_movement_phase() {
            return Err(PyRuntimeError::new_err(
                "resident stationary movement preflight rejected active transport or natural movement",
            ));
        }
        self.checkpoint_current = false;
        let movement_indices = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(index, entity)| {
                (entity.active && entity.is_alive && matches!(entity.entity_kind, 0 | 1))
                    .then_some(index)
            })
            .collect::<Vec<_>>();
        for entity_index in movement_indices {
            if self.entities[entity_index].entity_kind == 0 {
                self.accumulate_stationary_collision_for(entity_index);
            }
            self.begin_resident_movement(entity_index);
            if self.entities[entity_index].entity_kind == 0 {
                let movement = self.entities[entity_index]
                    .movement
                    .as_mut()
                    .expect("stationary troop requires movement state");
                if movement.native_avoidance < 0 {
                    movement.native_avoidance = (movement.native_avoidance + 10).min(0);
                } else if movement.native_avoidance > 0 {
                    movement.native_avoidance = (movement.native_avoidance - 10).max(0);
                }
                movement.native_natural_movement_active = false;
            }
            self.finish_resident_movement(entity_index);
        }
        Ok(())
    }

    fn stationary_movement_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active && matches!(entity.entity_kind, 0 | 1))
            .map(|entity| {
                let movement = entity
                    .movement
                    .as_ref()
                    .expect("character movement state parsed at initialization");
                json!({
                    "collision_radius": exact_f64_value(movement.collision_radius),
                    "encounter_index": entity.encounter_index,
                    "id": entity.id,
                    "native_avoidance": movement.native_avoidance,
                    "native_natural_movement_active": movement.native_natural_movement_active,
                    "pending_consumed": movement.pending_consumed,
                    "pending_x": exact_f64_value(movement.pending_x),
                    "pending_y": exact_f64_value(movement.pending_y),
                    "position_x": entity.position_x.diagnostic_value(),
                    "position_y": entity.position_y.diagnostic_value(),
                    "unit_mass": exact_f64_value(movement.unit_mass),
                    "vector_bypasses_cap": movement.vector_bypasses_cap,
                    "vector_count": movement.vector_count,
                    "vector_x_units": movement.vector_x_units,
                    "vector_y_units": movement.vector_y_units,
                })
            })
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize stationary movement state: {error}"
            ))
        })
    }

    fn stationary_movement_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.stationary_movement_state_bytes()?))
    }

    fn supports_flying_movement_phase(&self) -> bool {
        self.supports_restricted_movement_phase(false)
    }

    fn advance_flying_movement_phase(&mut self) -> PyResult<()> {
        if !self.supports_flying_movement_phase() {
            return Err(PyRuntimeError::new_err(
                "resident flying movement preflight rejected unsupported natural movement",
            ));
        }
        self.advance_restricted_movement_phase(true);
        Ok(())
    }

    fn flying_movement_state_bytes(&self) -> PyResult<Vec<u8>> {
        self.resident_natural_movement_state_bytes()
    }

    fn flying_movement_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.resident_natural_movement_state_bytes()?))
    }

    fn supports_ground_movement_phase(&self) -> bool {
        self.supports_restricted_movement_phase(true)
    }

    fn advance_ground_movement_phase(&mut self) -> PyResult<()> {
        if !self.supports_ground_movement_phase() {
            return Err(PyRuntimeError::new_err(
                "resident ground movement preflight rejected unsupported natural movement",
            ));
        }
        self.advance_restricted_movement_phase(true);
        Ok(())
    }

    fn ground_movement_state_bytes(&self) -> PyResult<Vec<u8>> {
        self.resident_natural_movement_state_bytes()
    }

    fn ground_movement_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.resident_natural_movement_state_bytes()?))
    }

    fn supports_direct_combat_phase(&self) -> bool {
        self.entities.iter().all(|entity| {
            !entity.active
                || match entity.entity_kind {
                    0 | 1 => {
                        entity.direct_combat_unsupported.is_empty()
                            && !entity.movement.as_ref().is_some_and(|movement| {
                                movement.river_jump_active
                                    || movement.special_move_active
                                    || movement.special_move_consumed_tick
                            })
                    }
                    2 => entity
                        .point_projectile
                        .as_ref()
                        .is_some_and(|projectile| projectile.unsupported.is_empty()),
                    _ => false,
                }
        })
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
            if actor_state.point_weapon.is_some() {
                return false;
            }
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
            .filter(|entity| entity.active)
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

    fn supports_direct_troop_combat_phase(&self) -> bool {
        if !self.resident_id_invariants_hold() || !self.supports_direct_combat_phase() {
            return false;
        }
        self.entities.iter().all(|entity| {
            !entity.active
                || !entity.is_alive
                || !matches!(entity.entity_kind, 0 | 1)
                || (Self::resident_deploy_state_supported(entity) && entity.locked_combat.is_some())
        })
    }

    fn advance_direct_troop_combat_phase(&mut self) -> PyResult<()> {
        if !self.supports_direct_troop_combat_phase() {
            return Err(PyRuntimeError::new_err(
                "resident direct-troop combat preflight rejected battle state",
            ));
        }
        self.checkpoint_current = false;
        self.refresh_lethal_projectile_reservations();
        let combat_actor_count = self.entities.len();
        for actor_index in 0..combat_actor_count {
            if !self.entities[actor_index].active
                || !self.entities[actor_index].is_alive
                || !matches!(self.entities[actor_index].entity_kind, 0 | 1)
            {
                continue;
            }
            if self.entities[actor_index].entity_kind == 0 {
                self.entities[actor_index]
                    .locked_combat
                    .as_mut()
                    .expect("direct preflight requires combat state")
                    .movement_target_id = None;
            }
            if self.entities[actor_index].deploy_delay_remaining > 0.0 {
                continue;
            }
            if self.entities[actor_index].spawn_hook_pending {
                self.entities[actor_index].spawn_hook_pending = false;
                self.entities[actor_index].spawn_hook_fired = true;
            }
            let actor_kind = self.entities[actor_index].entity_kind;
            let Some(step_dt) = self.prepare_direct_combat_actor(actor_index) else {
                continue;
            };
            let target_index = if actor_kind == 1 {
                self.direct_building_target_index(actor_index)
            } else {
                self.direct_troop_target_index(actor_index)
            };
            let target_id = target_index.map(|index| self.entities[index].id);
            let target_position = target_index.map(|index| {
                (
                    self.entities[index].position_x.as_f64(),
                    self.entities[index].position_y.as_f64(),
                )
            });
            let target_in_range =
                target_index.is_some_and(|index| self.direct_attack_reach(actor_index, index));
            let (actor_x, actor_y) = (
                self.entities[actor_index].position_x.as_f64(),
                self.entities[actor_index].position_y.as_f64(),
            );
            let payload = {
                let actor = &mut self.entities[actor_index];
                actor.target_id = target_id;
                let state = actor
                    .locked_combat
                    .as_mut()
                    .expect("direct preflight requires combat state");
                if actor_kind == 0 {
                    state.movement_target_id = None;
                    state.initial_position.get_or_insert((actor_x, actor_y));
                }
                state.last_attack_time += step_dt;
                if actor_kind == 0
                    && let Some((target_x, target_y)) = target_position
                {
                    let facing_x = ((target_x - actor_x) * 1000.0).round_ties_even() as i64;
                    let facing_y = ((target_y - actor_y) * 1000.0).round_ties_even() as i64;
                    if facing_x != 0 || facing_y != 0 {
                        state.facing_x_units = facing_x;
                        state.facing_y_units = facing_y;
                    }
                }
                if state.last_combat_target_id.is_some() && state.last_combat_target_id != target_id
                {
                    state.attack_cooldown =
                        state.attack_cooldown.max(state.retarget_ms as f64 / 1000.0);
                    state.has_attacked_once = false;
                }
                state.last_combat_target_id = target_id;
                if state.stun_timer > 0.0 {
                    None
                } else {
                    if state.attack_cooldown > 0.0 {
                        if target_in_range {
                            state.attack_cooldown -= step_dt * state.attack_rate();
                            if state.attack_cooldown <= 1e-9 {
                                state.attack_cooldown = 0.0;
                            }
                        } else if !state.attack_preload_blocked {
                            state.attack_cooldown = (state.attack_cooldown
                                - step_dt * state.attack_rate())
                            .max(state.first_hit_ms as f64 / 1000.0);
                        }
                    }
                    if !target_in_range {
                        state.attack_windup_active = false;
                    } else if !state.attack_windup_active
                        && state.attack_cooldown <= state.first_hit_ms as f64 / 1000.0 + 1e-12
                    {
                        state.attack_windup_active = true;
                    }
                    if actor_kind == 0
                        && let Some(_) = target_id
                        && !target_in_range
                    {
                        state.movement_target_id = target_id;
                    }
                    if target_id.is_some() && target_in_range && state.attack_cooldown <= 0.0 {
                        state.attack_cooldown = state.base_attack_interval();
                        state.attack_windup_active = false;
                        state.has_attacked_once = true;
                        state.attack_preload_blocked = false;
                        state.last_attack_time = 0.0;
                        Some(state.point_weapon.clone().map_or(
                            CombatPayload::DirectDamage(state.damage),
                            CombatPayload::PointProjectile,
                        ))
                    } else {
                        None
                    }
                }
            };
            if let (Some(target_index), Some(payload)) = (target_index, payload) {
                match payload {
                    CombatPayload::DirectDamage(damage) => {
                        self.apply_direct_combat_damage(target_index, damage);
                    }
                    CombatPayload::PointProjectile(weapon) => {
                        self.launch_point_projectile(actor_index, target_index, weapon);
                    }
                }
            }
            if actor_kind == 1 {
                self.sync_resident_tower(actor_index);
            }
        }
        Ok(())
    }

    fn supports_building_lifetime_phase(&self) -> bool {
        self.entities.iter().all(|entity| {
            !entity.active
                || entity.entity_kind != 1
                || (entity.building_lifetime.is_some() && entity.has_only_shield_mechanics())
        })
    }

    fn advance_building_lifetime_phase(&mut self) -> PyResult<()> {
        if !self.supports_building_lifetime_phase() {
            return Err(PyRuntimeError::new_err(
                "resident building lifetime phase contains executable death mechanics",
            ));
        }
        self.checkpoint_current = false;
        let mut changed_crown_indices = Vec::new();
        for (entity_index, entity) in self.entities.iter_mut().enumerate() {
            if !entity.active || !entity.is_alive || entity.entity_kind != 1 {
                continue;
            }
            let state = entity
                .building_lifetime
                .as_mut()
                .expect("building preflight requires lifetime state");
            let Some(lifetime_ms) = state.lifetime_ms.filter(|value| *value > 0) else {
                continue;
            };
            state.lifetime_elapsed += self.dt;
            let total_tick_ms = state.tick_carry_ms + (self.dt * 1000.0).max(0.0);
            let native_ticks = ((total_tick_ms + 1e-9) / 50.0).floor() as i64;
            state.tick_carry_ms = total_tick_ms - native_ticks as f64 * 50.0;
            let rounded_max_hp = entity.max_hitpoints.as_f64().round_ties_even() as i64;
            let decay_rate = 5000 * rounded_max_hp / lifetime_ms;
            state.decay_work += decay_rate * native_ticks;
            let whole_hp_loss = state.decay_work / 100;
            state.decay_work %= 100;
            if whole_hp_loss > 0 {
                entity.hitpoints.subtract_whole_hp(whole_hp_loss);
                if entity
                    .building_impact
                    .as_ref()
                    .is_some_and(|building| building.crown_slot.is_some())
                {
                    changed_crown_indices.push(entity_index);
                }
            }
            if entity.hitpoints.as_f64() <= 0.0 && entity.is_alive {
                entity.is_alive = false;
            }
        }
        for entity_index in changed_crown_indices {
            self.win_conditions_dirty = true;
            self.sync_resident_tower(entity_index);
        }
        Ok(())
    }

    fn building_lifetime_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active)
            .filter_map(ResidentEntity::building_lifetime_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize resident building lifetime state: {error}"
            ))
        })
    }

    fn building_lifetime_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.building_lifetime_state_bytes()?))
    }

    fn supports_point_projectile_phase(&self) -> bool {
        let has_splash = self.entities.iter().any(|entity| {
            entity.active
                && entity
                    .point_projectile
                    .as_ref()
                    .is_some_and(|projectile| projectile.splash_radius > 0.0)
        });
        let has_status = self.entities.iter().any(|entity| {
            entity.active
                && entity.point_projectile.as_ref().is_some_and(|projectile| {
                    projectile.stun_duration > 0.0
                        || (projectile.slow_duration > 0.0 && projectile.slow_multiplier < 1.0)
                })
        });
        if has_splash
            && self.entities.iter().any(|entity| {
                entity.active
                    && matches!(entity.entity_kind, 0 | 1)
                    && !entity.has_only_shield_mechanics()
            })
        {
            return false;
        }
        if has_status
            && self.entities.iter().any(|entity| {
                entity.active
                    && (entity.entity_kind == 1
                        || (entity.entity_kind == 0
                            && !entity.direct_combat_unsupported.is_empty())
                        || entity.locked_combat.as_ref().is_some_and(|state| {
                            state.is_airborne_for_projectile && !state.is_air_unit
                        }))
            })
        {
            return false;
        }
        self.entities.iter().all(|entity| {
            if !entity.active {
                return true;
            }
            if entity.entity_kind != 2 {
                return matches!(entity.entity_kind, 0 | 1);
            }
            let Some(projectile) = entity.point_projectile.as_ref() else {
                return false;
            };
            if !entity.mechanics.is_empty() || !projectile.unsupported.is_empty() {
                return false;
            }
            if !entity.damage.as_f64().is_finite()
                || !entity.hitpoints.as_f64().is_finite()
                || !entity.position_x.as_f64().is_finite()
                || !entity.position_y.as_f64().is_finite()
                || !projectile.splash_radius.is_finite()
                || !projectile.crown_tower_damage_multiplier.is_finite()
                || projectile
                    .crown_tower_damage
                    .is_some_and(|damage| !damage.is_finite())
                || !projectile.stun_duration.is_finite()
                || !projectile.slow_duration.is_finite()
                || !projectile.slow_multiplier.is_finite()
            {
                return false;
            }
            let Some(target_id) = projectile.primary_target_id else {
                return false;
            };
            let Some(target) = self
                .entities
                .iter()
                .find(|candidate| candidate.id == target_id)
            else {
                return false;
            };
            if !matches!(target.entity_kind, 0 | 1) || !target.has_only_shield_mechanics() {
                return false;
            }
            if target.entity_kind == 1 && target.building_impact.is_none() {
                return false;
            }
            if !target.hitpoints.as_f64().is_finite() {
                return false;
            }
            if let Some(source_id) = projectile.source_entity_id {
                let Some(source) = self
                    .entities
                    .iter()
                    .find(|candidate| candidate.id == source_id)
                else {
                    return false;
                };
                if !source.has_only_shield_mechanics() {
                    return false;
                }
            }
            if projectile.temporary_homing_remaining_ms > 0 {
                let Some(homing_target_id) = projectile.temporary_homing_target_id else {
                    return false;
                };
                if !self
                    .entities
                    .iter()
                    .any(|candidate| candidate.id == homing_target_id)
                {
                    return false;
                }
            }
            true
        })
    }

    fn advance_point_projectile_phase(&mut self) -> PyResult<()> {
        if !self.supports_point_projectile_phase() {
            return Err(PyRuntimeError::new_err(
                "resident point-projectile preflight rejected unsupported object or payload",
            ));
        }
        self.checkpoint_current = false;
        let mut projectile_indices = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(index, entity)| (entity.entity_kind == 2).then_some(index))
            .filter(|index| self.entities[*index].active)
            .collect::<Vec<_>>();
        projectile_indices.sort_unstable_by_key(|index| self.entities[*index].id);
        for projectile_index in projectile_indices {
            self.advance_point_projectile(projectile_index);
        }
        Ok(())
    }

    fn point_projectile_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active)
            .filter_map(ResidentEntity::point_projectile_diagnostic_value)
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize resident point-projectile state: {error}"
            ))
        })
    }

    fn point_projectile_sha256(&self) -> PyResult<String> {
        Ok(sha256_hex(&self.point_projectile_state_bytes()?))
    }

    fn supports_cleanup_phase(&self) -> bool {
        self.entities.iter().all(|entity| {
            !entity.active
                || entity.is_alive
                || (entity.has_only_shield_mechanics()
                    && match entity.entity_kind {
                        0 | 1 => !entity
                            .direct_combat_unsupported
                            .iter()
                            .any(|reason| reason == "death_spawn_payload"),
                        2 => entity.point_projectile.is_some(),
                        _ => false,
                    })
        })
    }

    fn advance_cleanup_phase(&mut self) -> PyResult<()> {
        if !self.supports_cleanup_phase() {
            return Err(PyRuntimeError::new_err(
                "resident cleanup preflight rejected death callbacks or payloads",
            ));
        }
        self.checkpoint_current = false;
        let dead_indices = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(index, entity)| (entity.active && !entity.is_alive).then_some(index))
            .collect::<Vec<_>>();
        for &dead_index in &dead_indices {
            let dead = &self.entities[dead_index];
            let Some(building) = dead.building_impact.as_ref() else {
                continue;
            };
            let Some(slot) = building.crown_slot.as_deref() else {
                continue;
            };
            self.win_conditions_dirty = true;
            if let Some(player) = self
                .players
                .iter_mut()
                .find(|player| player.player_id == dead.player_id)
            {
                match slot {
                    "left" => player.left_tower_hp = ExactScalar::Int(0),
                    "right" => player.right_tower_hp = ExactScalar::Int(0),
                    "king" => player.king_tower_hp = ExactScalar::Int(0),
                    _ => unreachable!("Crown slot validated at resident initialization"),
                }
            }
            if slot != "king"
                && let Some(king_index) = self.entities.iter().position(|candidate| {
                    candidate.active
                        && candidate.is_alive
                        && candidate.player_id == dead.player_id
                        && candidate
                            .building_impact
                            .as_ref()
                            .is_some_and(|state| state.crown_slot.as_deref() == Some("king"))
                })
            {
                let king = self.entities[king_index]
                    .building_impact
                    .as_mut()
                    .expect("King Crown slot requires building state");
                if king.requires_activation && !king.tower_active {
                    king.tower_active = true;
                    king.activation_delay_remaining = king
                        .activation_delay_remaining
                        .max(king.activation_delay_seconds);
                    king.activation_first_hit_delay_remaining = king
                        .activation_first_hit_delay_remaining
                        .max(king.activation_first_hit_delay_seconds);
                }
                self.sync_resident_tower(king_index);
            }
        }
        for dead_index in dead_indices {
            self.entities[dead_index].active = false;
            if let Some(tower) = self
                .towers
                .iter_mut()
                .find(|tower| tower.id == self.entities[dead_index].id)
            {
                tower.active = false;
            }
        }
        let mut encounter_index = 0;
        for entity in &mut self.entities {
            if entity.active {
                entity.encounter_index = encounter_index;
                encounter_index += 1;
            }
        }
        Ok(())
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
        Ok(self.checkpoint.as_ref().to_vec())
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
        let mut candidate = self.clone();
        candidate.advance_complete_tick_transaction().is_ok()
    }

    fn advance_complete_tick(&mut self) -> PyResult<bool> {
        let mut candidate = self.clone();
        let advanced = candidate.advance_complete_tick_transaction()?;
        *self = candidate;
        Ok(advanced)
    }

    fn fork(&self) -> Self {
        self.clone()
    }
}

impl ResidentBattle {
    fn advance_complete_tick_transaction(&mut self) -> PyResult<bool> {
        if self.game_over {
            return Ok(false);
        }
        if !self.pending_spell_casts_empty {
            return Err(PyRuntimeError::new_err(
                "resident complete tick has unsupported pending spell commands",
            ));
        }
        if !self.resident_id_invariants_hold() {
            return Err(PyRuntimeError::new_err(
                "resident complete tick rejected invalid entity-ID allocation state",
            ));
        }
        if !self.supports_direct_troop_combat_phase() {
            return Err(PyRuntimeError::new_err(
                "resident complete tick rejected combat capability",
            ));
        }
        self.advance_clock_phase();
        self.advance_player_phase();
        self.advance_direct_troop_combat_phase()?;
        if !self.supports_ground_movement_phase() {
            return Err(PyRuntimeError::new_err(
                "resident complete tick rejected post-combat movement capability",
            ));
        }
        self.advance_restricted_movement_phase(false);
        self.advance_building_lifetime_phase()?;
        self.advance_modifier_phase()?;
        self.advance_resident_object_phase()?;
        self.advance_cleanup_phase()?;
        if !self.sparse_idle_win_checks
            || self.win_conditions_dirty
            || (!self.sudden_death && self.time >= self.overtime_start_time)
            || (self.sudden_death && self.time >= self.tiebreaker_time)
        {
            self.check_win_conditions();
        }
        Ok(true)
    }

    fn resident_id_invariants_hold(&self) -> bool {
        if !(0..i64::MAX).contains(&self.next_entity_id) {
            return false;
        }
        let mut ids = self
            .entities
            .iter()
            .map(|entity| entity.id)
            .collect::<Vec<_>>();
        ids.sort_unstable();
        ids.windows(2).all(|pair| pair[0] != pair[1])
            && ids.last().is_none_or(|id| self.next_entity_id > *id)
    }

    fn sync_player_crown_hitpoints(&mut self) {
        for entity in self.entities.iter().filter(|entity| entity.active) {
            let Some(slot) = entity
                .building_impact
                .as_ref()
                .and_then(|building| building.crown_slot.as_deref())
            else {
                continue;
            };
            let Some(player) = self
                .players
                .iter_mut()
                .find(|player| player.player_id == entity.player_id)
            else {
                continue;
            };
            match slot {
                "left" => player.left_tower_hp = entity.hitpoints.clone(),
                "right" => player.right_tower_hp = entity.hitpoints.clone(),
                "king" => player.king_tower_hp = entity.hitpoints.clone(),
                _ => unreachable!("Crown slot validated at resident initialization"),
            }
        }
    }

    fn resident_deploy_state_supported(entity: &ResidentEntity) -> bool {
        let remaining = entity.deploy_delay_remaining;
        if !remaining.is_finite() || remaining < 0.0 {
            return false;
        }
        let deferred =
            entity.placement_pending && entity.spawn_hook_pending && !entity.spawn_hook_fired;
        let completed =
            !entity.placement_pending && !entity.spawn_hook_pending && entity.spawn_hook_fired;
        if remaining > 1e-9 {
            deferred
        } else {
            deferred || completed
        }
    }

    fn resident_death_spawn_travel_supported(&self, entity: &ResidentEntity) -> bool {
        let Some(movement) = entity.movement.as_ref() else {
            return false;
        };
        match movement.death_spawn_travel_target {
            Some((target_x, target_y)) => {
                let max_dx = self.arena_width_tiles * 1000 - 500;
                let max_dy = self.arena_height_tiles * 1000 - 500;
                let max_ticks = integer_sqrt(
                    (i128::from(max_dx) * i128::from(max_dx)
                        + i128::from(max_dy) * i128::from(max_dy)) as u128,
                ) / 250;
                entity.entity_kind == 0
                    && target_x.is_finite()
                    && target_y.is_finite()
                    && (0.25..=self.arena_width_tiles as f64 - 0.25).contains(&target_x)
                    && (0.25..=self.arena_height_tiles as f64 - 0.25).contains(&target_y)
                    && logic_units(target_x) as f64 / 1000.0 == target_x
                    && logic_units(target_y) as f64 / 1000.0 == target_y
                    && (1..=max_ticks).contains(&movement.death_spawn_travel_ticks)
            }
            None => movement.death_spawn_travel_ticks == 0,
        }
    }

    fn resident_knockback_state_supported(&self, entity: &ResidentEntity) -> bool {
        let Some(movement) = entity.movement.as_ref() else {
            return false;
        };
        match movement.knockback_target {
            Some((target_x, target_y)) => {
                if entity.entity_kind != 0
                    || !target_x.is_finite()
                    || !target_y.is_finite()
                    || !(0..=700).contains(&movement.knockback_velocity_work)
                    || movement.knockback_velocity_work % 25 != 0
                    || !movement.forced_movement_active
                {
                    return false;
                }
                let dx = target_x - entity.position_x.as_f64();
                let dy = target_y - entity.position_y.as_f64();
                dx.is_finite()
                    && dy.is_finite()
                    && (-9.75..=self.arena_width_tiles as f64 + 9.75).contains(&target_x)
                    && (-9.75..=self.arena_height_tiles as f64 + 9.75).contains(&target_y)
            }
            None => {
                movement.knockback_velocity_work == 0
                    && movement.knockback_interrupts_combat
                    && !movement.forced_movement_active
            }
        }
    }

    fn supports_restricted_movement_phase(&self, allow_ground: bool) -> bool {
        let needs_live_projectile_reservations = self.entities.iter().any(|entity| {
            entity.active
                && entity.is_alive
                && entity.locked_combat.as_ref().is_some_and(|combat| {
                    combat.movement_target_id.is_some() && combat.point_weapon.is_some()
                })
        });
        if needs_live_projectile_reservations
            && self.entities.iter().any(|entity| {
                entity.active
                    && entity.is_alive
                    && entity.entity_kind == 2
                    && !entity
                        .point_projectile
                        .as_ref()
                        .is_some_and(|projectile| projectile.unsupported.is_empty())
            })
        {
            return false;
        }
        self.entities.iter().all(|entity| {
            if !entity.active || !matches!(entity.entity_kind, 0 | 1) || !entity.is_alive {
                return true;
            }
            let (Some(movement), Some(combat), Some(modifiers)) = (
                entity.movement.as_ref(),
                entity.locked_combat.as_ref(),
                entity.modifier_state.as_ref(),
            ) else {
                return false;
            };
            let river_state_supported = if movement.river_jump_active {
                allow_ground
                    && self.arena_width_tiles == 18
                    && self.arena_height_tiles == 32
                    && entity.entity_kind == 0
                    && movement.jump_height_present
                    && !movement.charge_range_present
                    && movement.jump_speed.is_finite()
                    && movement.jump_speed.round_ties_even() > 0.0
                    && movement
                        .river_jump_origin
                        .is_some_and(|(x, y)| x.is_finite() && y.is_finite())
                    && movement
                        .river_jump_target
                        .is_some_and(|(x, y)| x.is_finite() && y.is_finite())
                    && movement.river_jump_elapsed.is_finite()
                    && movement.river_jump_elapsed >= 0.0
                    && movement.river_jump_duration.is_finite()
                    && movement.river_jump_duration >= self.dt
                    && movement.special_move_active
                    && !movement.special_move_consumed_tick
                    && !movement.stun_interrupt_deferred_until_landing
                    && combat.stun_timer <= 0.0
            } else {
                !movement.special_move_active
                    && !movement.stun_interrupt_deferred_until_landing
                    && (!movement.special_move_consumed_tick || movement.jump_height_present)
            };
            let death_spawn_travel_active = movement.death_spawn_travel_ticks > 0;
            let knockback_active = movement.knockback_target.is_some();
            let deploying = entity.deploy_delay_remaining > 0.0;
            let common = (death_spawn_travel_active
                || knockback_active
                || Self::resident_deploy_state_supported(entity))
                && entity.has_only_shield_mechanics()
                && movement.route_cache_supported
                && river_state_supported
                && movement.vector_count >= 0
                && movement.unit_mass.is_finite()
                && movement.unit_mass > 0.0
                && movement.collision_radius.is_finite()
                && entity.position_x.as_f64().is_finite()
                && entity.position_y.as_f64().is_finite()
                && movement.pending_x.is_finite()
                && movement.pending_y.is_finite()
                && self.resident_death_spawn_travel_supported(entity)
                && self.resident_knockback_state_supported(entity)
                && !(movement.death_spawn_travel_ticks > 0
                    && (movement.knockback_target.is_some()
                        || movement.river_jump_active
                        || movement.special_move_active
                        || movement.special_move_consumed_tick
                        || movement.forced_movement_active))
                && !(movement.river_jump_active && movement.knockback_target.is_some())
                && !movement.kamikaze_primed
                && (!death_spawn_travel_active || !movement.charge_range_present);
            if !common
                || death_spawn_travel_active
                || knockback_active
                || deploying
                || entity.entity_kind == 1
                || combat.movement_target_id.is_none()
            {
                return common;
            }
            let single_node = combat.is_air_unit || movement.is_hover;
            let route_kind_supported = if single_node {
                matches!(
                    movement.route_cache_kind,
                    RouteCacheKind::Absent | RouteCacheKind::Single
                )
            } else {
                allow_ground
                    && matches!(
                        movement.route_cache_kind,
                        RouteCacheKind::Absent | RouteCacheKind::Ground
                    )
            };
            route_kind_supported
                && movement.route_cache_supported
                && !movement.charge_range_present
                && (!movement.jump_height_present
                    || (allow_ground
                        && self.arena_width_tiles == 18
                        && self.arena_height_tiles == 32
                        && movement.jump_speed.is_finite()
                        && movement.jump_speed.round_ties_even() > 0.0))
                && movement.stop_movement_after_ms == 0.0
                && movement.wait_ms == 0.0
                && movement.serialized_speed.is_finite()
                && modifiers.speed.as_f64().is_finite()
                && modifiers.original_speed.is_none_or(f64::is_finite)
                && modifiers.slow_multiplier.is_finite()
                && modifiers.movement_mode_multiplier.is_finite()
                && modifiers.movement_speed_buff_multiplier.is_finite()
        })
    }

    fn advance_restricted_movement_phase(&mut self, refresh_reservations: bool) {
        self.checkpoint_current = false;
        if refresh_reservations {
            self.refresh_lethal_projectile_reservations();
        }
        let movement_indices = self
            .entities
            .iter()
            .enumerate()
            .filter_map(|(index, entity)| {
                (entity.active && entity.is_alive && matches!(entity.entity_kind, 0 | 1))
                    .then_some(index)
            })
            .collect::<Vec<_>>();
        for entity_index in movement_indices {
            if self.entities[entity_index].entity_kind == 0 {
                let skip_final_knockback_collision = self.entities[entity_index]
                    .movement
                    .as_ref()
                    .is_some_and(|movement| {
                        movement.knockback_target.is_some() && movement.knockback_velocity_work < 1
                    });
                if !skip_final_knockback_collision {
                    self.accumulate_stationary_collision_for(entity_index);
                }
            }
            self.begin_resident_movement(entity_index);
            if self.entities[entity_index].entity_kind == 0 {
                self.update_resident_avoidance(entity_index);
                self.advance_resident_natural_movement(entity_index);
            }
            self.finish_resident_movement(entity_index);
        }
    }

    fn stationary_collision_vector(
        entity: &ResidentEntity,
        other: &ResidentEntity,
        collision_distance: f64,
        other_mass: f64,
        own_mass: f64,
    ) -> Option<(i64, i64)> {
        let mut dx = logic_units(entity.position_x.as_f64() - other.position_x.as_f64());
        let mut dy = logic_units(entity.position_y.as_f64() - other.position_y.as_f64());
        let collision_units = logic_units(collision_distance);
        if dx.abs() > collision_units || dy.abs() > collision_units {
            return None;
        }
        let squared = i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy);
        if squared > i128::from(collision_units) * i128::from(collision_units) {
            return None;
        }
        let distance = if squared == 0 {
            dx = 0;
            dy = if entity.player_id == 0 { 1 } else { -1 };
            1
        } else {
            integer_sqrt(squared as u128).max(1)
        };
        let overlap = (collision_units - distance).clamp(0, 300);
        let own_mass_units = (own_mass.round_ties_even() as i64).max(1);
        let magnitude =
            (((overlap as f64 * other_mass) / own_mass_units as f64).trunc() as i64 + 1).min(300);
        Some((
            truncating_div(i128::from(dx) * i128::from(magnitude), distance),
            truncating_div(i128::from(dy) * i128::from(magnitude), distance),
        ))
    }

    fn accumulate_stationary_collision_for(&mut self, entity_index: usize) {
        let entity = &self.entities[entity_index];
        let combat = entity
            .locked_combat
            .as_ref()
            .expect("stationary troop requires combat state");
        let movement = entity
            .movement
            .as_ref()
            .expect("stationary troop requires movement state");
        if combat.stun_timer > 0.0
            && !movement.river_jump_active
            && movement.death_spawn_travel_ticks <= 0
        {
            return;
        }
        let own_radius = movement.collision_radius.max(0.2);
        let own_mass = movement.unit_mass.max(1e-9);
        let own_air = combat.is_air_unit || movement.is_hover || movement.river_jump_active;
        let static_radius = own_radius.min(0.5);
        let mut contributions = Vec::new();
        for (other_index, other) in self.entities.iter().enumerate() {
            if other_index == entity_index || !other.active || !other.is_alive {
                continue;
            }
            match other.entity_kind {
                0 => {
                    let other_combat = other
                        .locked_combat
                        .as_ref()
                        .expect("troop collision candidate requires combat state");
                    let other_movement = other
                        .movement
                        .as_ref()
                        .expect("troop collision candidate requires movement state");
                    let other_air = other_combat.is_air_unit
                        || other_movement.is_hover
                        || other_movement.river_jump_active;
                    if own_air != other_air {
                        continue;
                    }
                    if let Some(vector) = Self::stationary_collision_vector(
                        entity,
                        other,
                        own_radius + other_movement.collision_radius.max(0.2),
                        other_movement.unit_mass.max(1e-9),
                        own_mass,
                    ) {
                        contributions.push(vector);
                    }
                }
                1 if !own_air => {
                    let other_radius = other
                        .movement
                        .as_ref()
                        .expect("building collision candidate requires movement state")
                        .collision_radius
                        .max(0.0);
                    if let Some(vector) = Self::stationary_collision_vector(
                        entity,
                        other,
                        static_radius + other_radius,
                        20.0,
                        own_mass,
                    ) {
                        contributions.push(vector);
                    }
                }
                _ => {}
            }
        }
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("stationary troop requires movement state");
        for (x, y) in contributions {
            movement.vector_x_units += x;
            movement.vector_y_units += y;
            movement.vector_count += 1;
        }
    }

    fn begin_resident_movement(&mut self, entity_index: usize) {
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("character movement state parsed at initialization");
        if movement.vector_count <= 0 {
            movement.pending_x = 0.0;
            movement.pending_y = 0.0;
            movement.pending_consumed = true;
            return;
        }
        let mut x = movement.vector_x_units / movement.vector_count;
        let mut y = movement.vector_y_units / movement.vector_count;
        let squared = i128::from(x) * i128::from(x) + i128::from(y) * i128::from(y);
        if !movement.vector_bypasses_cap && squared > 150 * 150 {
            let magnitude = integer_sqrt(squared as u128).max(1);
            x = truncating_div(i128::from(x) * 150, magnitude);
            y = truncating_div(i128::from(y) * 150, magnitude);
        }
        movement.pending_x = x as f64 / 1000.0;
        movement.pending_y = y as f64 / 1000.0;
        movement.pending_consumed = false;
        movement.vector_x_units = 0;
        movement.vector_y_units = 0;
        movement.vector_count = 0;
        movement.vector_bypasses_cap = false;
    }

    fn finish_resident_movement(&mut self, entity_index: usize) {
        let (pending_x, pending_y) = {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("character movement state parsed at initialization");
            if movement.pending_consumed {
                (0.0, 0.0)
            } else {
                movement.pending_consumed = true;
                (movement.pending_x, movement.pending_y)
            }
        };
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("character movement state parsed at initialization");
        movement.pending_x = 0.0;
        movement.pending_y = 0.0;
        if pending_x.abs() > 1e-15 || pending_y.abs() > 1e-15 {
            let x = (logic_units(self.entities[entity_index].position_x.as_f64())
                + logic_units(pending_x)) as f64
                / 1000.0;
            let y = (logic_units(self.entities[entity_index].position_y.as_f64())
                + logic_units(pending_y)) as f64
                / 1000.0;
            let max_x = self.arena_width_tiles as f64 - 0.25;
            let max_y = self.arena_height_tiles as f64 - 0.25;
            self.entities[entity_index]
                .position_x
                .set_f64(x.clamp(0.25, max_x));
            self.entities[entity_index]
                .position_y
                .set_f64(y.clamp(0.25, max_y));
        }
        let quantized_x = logic_units(self.entities[entity_index].position_x.as_f64());
        let quantized_y = logic_units(self.entities[entity_index].position_y.as_f64());
        self.entities[entity_index]
            .position_x
            .set_f64(quantized_x as f64 / 1000.0);
        self.entities[entity_index]
            .position_y
            .set_f64(quantized_y as f64 / 1000.0);
    }

    fn movement_component_vector_logic_units(dx: i64, dy: i64, movement_units: i64) -> (i64, i64) {
        if movement_units <= 0 || (dx == 0 && dy == 0) {
            return (0, 0);
        }
        let squared = (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128;
        let remaining = integer_sqrt(squared).max(1);
        let capped = movement_units.min(remaining);
        let direction_x = truncating_div(i128::from(dx) << 8, remaining);
        let direction_y = truncating_div(i128::from(dy) << 8, remaining);
        ((direction_x * capped) >> 8, (direction_y * capped) >> 8)
    }

    fn speed_work_for_duration(speed: i64, dt: f64) -> i64 {
        let tick_count = dt.max(0.0) / 0.05;
        let rounded_tick_count = tick_count.round_ties_even();
        if (tick_count - rounded_tick_count).abs() <= 1e-9 {
            speed.max(0) * rounded_tick_count as i64
        } else {
            (speed.max(0) as f64 * tick_count).round_ties_even() as i64
        }
    }

    fn native_route_goal_cell(
        mover_x: i64,
        mover_y: i64,
        target_x: i64,
        target_y: i64,
        required_range: i64,
    ) -> Option<(i64, i64)> {
        const CELL_SIZE: i64 = 500;
        const PATH_WIDTH: i64 = 36;
        const PATH_HEIGHT: i64 = 64;
        let required_range = required_range.max(0);
        let search_radius = required_range / CELL_SIZE + 1;
        let target_cell_x = (target_x / CELL_SIZE).clamp(0, PATH_WIDTH - 1);
        let target_cell_y = (target_y / CELL_SIZE).clamp(0, PATH_HEIGHT - 1);
        let min_x = (target_cell_x - search_radius).max(0);
        let max_x = (target_cell_x + search_radius).min(PATH_WIDTH - 1);
        let min_y = (target_cell_y - search_radius).max(0);
        let max_y = (target_cell_y + search_radius).min(PATH_HEIGHT - 1);
        let required_range_sq = i128::from(required_range) * i128::from(required_range);
        let mut best = None;
        let mut best_mover_distance_sq = i128::from((1_i64 << 31) - 1);
        for cell_y in min_y..=max_y {
            let candidate_y = cell_y * CELL_SIZE + CELL_SIZE / 2;
            let target_dy = candidate_y - target_y;
            let mover_dy = candidate_y - mover_y;
            for cell_x in min_x..=max_x {
                let candidate_x = cell_x * CELL_SIZE + CELL_SIZE / 2;
                let target_dx = candidate_x - target_x;
                let target_distance_sq = i128::from(target_dx) * i128::from(target_dx)
                    + i128::from(target_dy) * i128::from(target_dy);
                if target_distance_sq > required_range_sq {
                    continue;
                }
                let mover_dx = candidate_x - mover_x;
                let mover_distance_sq = i128::from(mover_dx) * i128::from(mover_dx)
                    + i128::from(mover_dy) * i128::from(mover_dy);
                if mover_distance_sq < best_mover_distance_sq {
                    best = Some((cell_x, cell_y));
                    best_mover_distance_sq = mover_distance_sq;
                }
            }
        }
        best
    }

    fn resident_movement_component_stopped(&self, entity_index: usize) -> bool {
        let entity = &self.entities[entity_index];
        let combat = entity
            .locked_combat
            .as_ref()
            .expect("resident troop requires combat state");
        let movement = entity
            .movement
            .as_ref()
            .expect("resident troop requires movement state");
        if movement.death_spawn_travel_ticks > 0 {
            return false;
        }
        (combat.movement_target_id.is_none() && !movement.river_jump_active)
            || entity.deploy_delay_remaining > 0.0
            || combat.stun_timer > 0.0
            || movement.kamikaze_primed
    }

    fn update_resident_avoidance(&mut self, entity_index: usize) {
        let stopped = self.resident_movement_component_stopped(entity_index);
        let (facing_x, facing_y) = {
            let combat = self.entities[entity_index]
                .locked_combat
                .as_ref()
                .expect("resident troop requires combat state");
            normalized_vector_logic_units(combat.facing_x_units, combat.facing_y_units, 256)
        };
        if stopped || (facing_x == 0 && facing_y == 0) {
            self.decay_resident_avoidance(entity_index);
            return;
        }
        let entity = &self.entities[entity_index];
        let own_x = logic_units(entity.position_x.as_f64());
        let own_y = logic_units(entity.position_y.as_f64());
        let probe_x = own_x + facing_x;
        let probe_y = own_y + facing_y;
        let probe_radius = entity.locked_combat.as_ref().map_or(0, |combat| {
            logic_units(combat.collision_radius).clamp(0, 500)
        });
        let own_air = entity
            .locked_combat
            .as_ref()
            .is_some_and(|combat| combat.is_air_unit)
            || entity
                .movement
                .as_ref()
                .is_some_and(|movement| movement.is_hover || movement.river_jump_active);
        let mut moving_count = 0_i64;
        let mut static_count = 0_i64;
        let mut moving_side = 1_i64;
        let mut static_side = 1_i64;
        let mut static_candidates = Vec::new();
        for (other_index, other) in self.entities.iter().enumerate() {
            if other_index == entity_index
                || !other.active
                || !other.is_alive
                || !matches!(other.entity_kind, 0 | 1)
            {
                continue;
            }
            let other_air = other
                .locked_combat
                .as_ref()
                .is_some_and(|combat| combat.is_air_unit)
                || other
                    .movement
                    .as_ref()
                    .is_some_and(|movement| movement.is_hover || movement.river_jump_active);
            if own_air != other_air {
                continue;
            }
            let other_x = logic_units(other.position_x.as_f64());
            let other_y = logic_units(other.position_y.as_f64());
            let other_radius = other
                .locked_combat
                .as_ref()
                .map_or(0, |combat| logic_units(combat.collision_radius).max(0));
            let query_radius = probe_radius + other_radius;
            let probe_dx = other_x - probe_x;
            let probe_dy = other_y - probe_y;
            if i128::from(probe_dx) * i128::from(probe_dx)
                + i128::from(probe_dy) * i128::from(probe_dy)
                > i128::from(query_radius) * i128::from(query_radius)
            {
                continue;
            }
            let relative_x = other_x - own_x;
            let relative_y = other_y - own_y;
            let cross = facing_y * relative_x - facing_x * relative_y;
            let geometric_side = i64::from(cross < 0);
            if other.entity_kind == 1 {
                static_count += 1;
                static_side = geometric_side;
                static_candidates.push((other_x, other_y, other_radius));
                continue;
            }
            let direction_dot = if self.resident_movement_component_stopped(other_index) {
                0
            } else {
                let other_combat = other
                    .locked_combat
                    .as_ref()
                    .expect("resident troop requires combat state");
                let (other_facing_x, other_facing_y) = normalized_vector_logic_units(
                    other_combat.facing_x_units,
                    other_combat.facing_y_units,
                    256,
                );
                other_facing_x * facing_x + other_facing_y * facing_y
            };
            if direction_dot > 0 {
                continue;
            }
            moving_count += 1;
            let other_avoidance = other
                .movement
                .as_ref()
                .map_or(0, |movement| movement.native_avoidance);
            moving_side = if other_avoidance == 0 {
                geometric_side
            } else {
                i64::from(other_avoidance > 0)
            };
        }
        {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            for (static_x, static_y, static_radius) in static_candidates {
                if movement.route_cells.len() < 2 {
                    break;
                }
                let (cell_x, cell_y) = movement.route_cells[0];
                let waypoint_x = cell_x * 500 + 250;
                let waypoint_y = cell_y * 500 + 250;
                let dx = waypoint_x - static_x;
                let dy = waypoint_y - static_y;
                if i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)
                    < i128::from(static_radius) * i128::from(static_radius)
                {
                    movement.route_cells.remove(0);
                }
            }
            let selected_side = if static_count > 0 {
                static_side
            } else {
                moving_side
            };
            if moving_count + static_count > 0 {
                if movement.native_avoidance == 0 {
                    movement.native_avoidance = if selected_side != 0 { 200 } else { -200 };
                } else if static_count > 0 {
                    movement.native_avoidance += if selected_side != 0 { 20 } else { -20 };
                    movement.native_avoidance = movement.native_avoidance.clamp(-200, 200);
                }
            }
        }
        self.decay_resident_avoidance(entity_index);
    }

    fn decay_resident_avoidance(&mut self, entity_index: usize) {
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        if movement.native_avoidance < 0 {
            movement.native_avoidance = (movement.native_avoidance + 10).min(0);
        } else if movement.native_avoidance > 0 {
            movement.native_avoidance = (movement.native_avoidance - 10).max(0);
        }
    }

    fn resident_movement_target_valid(&self, actor_index: usize, target_index: usize) -> bool {
        if actor_index == target_index {
            return false;
        }
        let actor = &self.entities[actor_index];
        let target = &self.entities[target_index];
        let (Some(actor_state), Some(target_state)) =
            (actor.locked_combat.as_ref(), target.locked_combat.as_ref())
        else {
            return false;
        };
        let now_ms = (self.time * 1000.0).round_ties_even() as i64;
        target.active
            && target.is_alive
            && target.player_id != actor.player_id
            && !target_state.hidden_building
            && target_state.stealth_until_ms <= now_ms
            && target.death_spawn_target_immunity_elapsed_ms < 0
            && !(actor_state.point_weapon.is_some()
                && self.lethal_projectile_reservation_ids.contains(&target.id))
    }

    fn advance_resident_natural_movement(&mut self, entity_index: usize) {
        let (
            death_spawn_travel_active,
            knockback_active,
            river_jump_active,
            special_move_consumed_tick,
        ) = {
            let movement = self.entities[entity_index]
                .movement
                .as_ref()
                .expect("resident troop requires movement state");
            (
                movement.death_spawn_travel_ticks > 0,
                movement.knockback_target.is_some(),
                movement.river_jump_active,
                movement.special_move_consumed_tick,
            )
        };
        if death_spawn_travel_active {
            self.update_resident_death_spawn_travel(entity_index);
            return;
        }
        if knockback_active {
            self.update_resident_knockback(entity_index);
            return;
        }
        if self.entities[entity_index].deploy_delay_remaining > 0.0 {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .native_natural_movement_active = false;
            return;
        }
        if river_jump_active {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .native_natural_movement_active = false;
            self.update_resident_river_jump(entity_index);
            return;
        }
        if special_move_consumed_tick {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            movement.native_natural_movement_active = false;
            movement.special_move_consumed_tick = false;
            return;
        }
        let target_id = self.entities[entity_index]
            .locked_combat
            .as_ref()
            .and_then(|combat| combat.movement_target_id);
        let Some(target_id) = target_id else {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .native_natural_movement_active = false;
            return;
        };
        let target_index = self
            .entities
            .iter()
            .position(|entity| entity.id == target_id && entity.active);
        let Some(target_index) = target_index else {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .native_natural_movement_active = false;
            return;
        };
        let stunned = self.entities[entity_index]
            .locked_combat
            .as_ref()
            .is_some_and(|combat| combat.stun_timer > 0.0);
        if !self.resident_movement_target_valid(entity_index, target_index) || stunned {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .native_natural_movement_active = false;
            return;
        }
        self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state")
            .native_natural_movement_active = true;
        self.move_resident_towards_target(entity_index, target_index);
    }

    fn update_resident_death_spawn_travel(&mut self, entity_index: usize) {
        let (target_x, target_y, avoidance, external_x, external_y) = {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            let (target_x, target_y) = movement
                .death_spawn_travel_target
                .expect("death-spawn travel preflight requires target");
            let (external_x, external_y) = if movement.pending_consumed {
                (0.0, 0.0)
            } else {
                movement.pending_consumed = true;
                (movement.pending_x, movement.pending_y)
            };
            (
                target_x,
                target_y,
                movement.native_avoidance,
                external_x,
                external_y,
            )
        };
        let current_x = self.entities[entity_index].position_x.as_f64();
        let current_y = self.entities[entity_index].position_y.as_f64();
        let dx = logic_units(target_x - current_x);
        let dy = logic_units(target_y - current_y);
        let remaining = integer_sqrt(
            (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128,
        )
        .max(1);
        let movement_units = remaining.min(250);
        let direction_x = truncating_div(i128::from(dx) * 256, remaining);
        let direction_y = truncating_div(i128::from(dy) * 256, remaining);
        let mut move_x = truncating_div(i128::from(direction_x) * i128::from(movement_units), 256);
        let mut move_y = truncating_div(i128::from(direction_y) * i128::from(movement_units), 256);
        if avoidance != 0 {
            let avoidance = avoidance.clamp(-256, 256);
            let retained = 256 - avoidance.abs();
            let rotated_x = ((retained * move_x) >> 8) + ((avoidance * move_y) >> 8);
            let rotated_y = ((retained * move_y) >> 8) + ((-move_x * avoidance) >> 8);
            (move_x, move_y) = normalized_vector_logic_units(rotated_x, rotated_y, movement_units);
        }
        let combined_x = move_x + logic_units(external_x);
        let combined_y = move_y + logic_units(external_y);
        if combined_x != 0 || combined_y != 0 {
            let new_x = (logic_units(current_x) + combined_x) as f64 / 1000.0;
            let new_y = (logic_units(current_y) + combined_y) as f64 / 1000.0;
            self.entities[entity_index]
                .position_x
                .set_f64(new_x.clamp(0.25, self.arena_width_tiles as f64 - 0.25));
            self.entities[entity_index]
                .position_y
                .set_f64(new_y.clamp(0.25, self.arena_height_tiles as f64 - 0.25));
        }
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        movement.death_spawn_travel_ticks -= 1;
        if movement.death_spawn_travel_ticks == 0 {
            movement.death_spawn_travel_target = None;
        }
    }

    fn update_resident_knockback(&mut self, entity_index: usize) {
        let (target_x, target_y, velocity_work, external_x, external_y) = {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            let (target_x, target_y) = movement
                .knockback_target
                .expect("knockback preflight requires target");
            movement.knockback_velocity_work -= 25;
            let (external_x, external_y) = if movement.pending_consumed {
                (0.0, 0.0)
            } else {
                movement.pending_consumed = true;
                (movement.pending_x, movement.pending_y)
            };
            (
                target_x,
                target_y,
                movement.knockback_velocity_work,
                external_x,
                external_y,
            )
        };
        let current_x = self.entities[entity_index].position_x.as_f64();
        let current_y = self.entities[entity_index].position_y.as_f64();
        let dx = logic_units(target_x - current_x);
        let dy = logic_units(target_y - current_y);
        let remaining = integer_sqrt(
            (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128,
        );
        let movement_units = velocity_work.clamp(0, 250).min(remaining);
        let (move_x, move_y) = Self::movement_component_vector_logic_units(dx, dy, movement_units);
        let combined_x = move_x + logic_units(external_x);
        let combined_y = move_y + logic_units(external_y);
        if combined_x != 0 || combined_y != 0 {
            let new_x = (logic_units(current_x) + combined_x) as f64 / 1000.0;
            let new_y = (logic_units(current_y) + combined_y) as f64 / 1000.0;
            self.entities[entity_index]
                .position_x
                .set_f64(new_x.clamp(0.25, self.arena_width_tiles as f64 - 0.25));
            self.entities[entity_index]
                .position_y
                .set_f64(new_y.clamp(0.25, self.arena_height_tiles as f64 - 0.25));
        }
        if velocity_work < 0 {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            movement.knockback_target = None;
            movement.knockback_velocity_work = 0;
            movement.knockback_interrupts_combat = true;
            movement.forced_movement_active = false;
        }
    }

    fn update_resident_river_jump(&mut self, entity_index: usize) {
        let (target_x, target_y, jump_speed) = {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            movement.river_jump_elapsed += self.dt;
            let (target_x, target_y) = movement
                .river_jump_target
                .expect("active river jump requires a landing target");
            (
                target_x,
                target_y,
                movement.jump_speed.round_ties_even().max(0.0) as i64,
            )
        };
        let current_x = self.entities[entity_index].position_x.as_f64();
        let current_y = self.entities[entity_index].position_y.as_f64();
        let dx_units = logic_units(target_x - current_x);
        let dy_units = logic_units(target_y - current_y);
        if dx_units != 0 || dy_units != 0 {
            let combat = self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state");
            combat.facing_x_units = dx_units;
            combat.facing_y_units = dy_units;
        }
        let remaining = integer_sqrt(
            (i128::from(dx_units) * i128::from(dx_units)
                + i128::from(dy_units) * i128::from(dy_units)) as u128,
        );
        let work = Self::speed_work_for_duration(jump_speed, self.dt);
        let (mut move_x, mut move_y) =
            Self::movement_component_vector_logic_units(dx_units, dy_units, work);
        let avoidance = self.entities[entity_index]
            .movement
            .as_ref()
            .expect("resident troop requires movement state")
            .native_avoidance;
        if avoidance != 0 {
            let avoidance = avoidance.clamp(-256, 256);
            let retained = 256 - avoidance.abs();
            let rotated_x = ((retained * move_x) >> 8) + ((avoidance * move_y) >> 8);
            let rotated_y = ((retained * move_y) >> 8) + ((-move_x * avoidance) >> 8);
            (move_x, move_y) =
                normalized_vector_logic_units(rotated_x, rotated_y, work.min(remaining));
        }
        self.entities[entity_index]
            .position_x
            .set_f64((logic_units(current_x) + move_x) as f64 / 1000.0);
        self.entities[entity_index]
            .position_y
            .set_f64((logic_units(current_y) + move_y) as f64 / 1000.0);
        if remaining > work {
            return;
        }
        self.entities[entity_index].position_x.set_f64(target_x);
        self.entities[entity_index].position_y.set_f64(target_y);
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        movement.river_jump_active = false;
        movement.special_move_active = false;
        movement.special_move_consumed_tick = true;
        movement.river_jump_blocked = false;
        self.entities[entity_index]
            .locked_combat
            .as_mut()
            .expect("resident troop requires combat state")
            .is_airborne_for_projectile = self.entities[entity_index]
            .locked_combat
            .as_ref()
            .is_some_and(|combat| combat.is_air_unit);
    }

    fn move_resident_towards_target(&mut self, entity_index: usize, target_index: usize) {
        let previous_x = self.entities[entity_index].position_x.as_f64();
        let previous_y = self.entities[entity_index].position_y.as_f64();
        let target_x = self.entities[target_index].position_x.as_f64();
        let target_y = self.entities[target_index].position_y.as_f64();
        let required_range = self.entities[entity_index]
            .locked_combat
            .as_ref()
            .map_or(0, |combat| logic_units(combat.range).max(0));
        let goal = Self::native_route_goal_cell(
            logic_units(previous_x),
            logic_units(previous_y),
            logic_units(target_x),
            logic_units(target_y),
            required_range,
        );
        let single_node = self.entities[entity_index]
            .locked_combat
            .as_ref()
            .is_some_and(|combat| combat.is_air_unit)
            || self.entities[entity_index]
                .movement
                .as_ref()
                .is_some_and(|movement| movement.is_hover);
        let (waypoint_x, waypoint_y) = if single_node {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            if let Some(goal) = goal {
                if movement.route_cache_kind != RouteCacheKind::Single
                    || movement.route_goal != Some(goal)
                {
                    movement.route_cache_kind = RouteCacheKind::Single;
                    movement.route_goal = Some(goal);
                    movement.route_cells = vec![goal];
                    movement.route_backwards = false;
                    movement.route_lane_id = 0;
                    movement.route_jump_height = false;
                }
                movement
                    .route_cells
                    .first()
                    .map_or((target_x, target_y), |(cell_x, cell_y)| {
                        (
                            (*cell_x * 500 + 250) as f64 / 1000.0,
                            (*cell_y * 500 + 250) as f64 / 1000.0,
                        )
                    })
            } else {
                (target_x, target_y)
            }
        } else {
            self.resident_ground_waypoint(
                entity_index,
                goal,
                previous_x,
                previous_y,
                target_x,
                target_y,
            )
        };
        if self.entities[entity_index]
            .movement
            .as_ref()
            .is_some_and(|movement| movement.is_hover)
        {
            let origin_dx = logic_units(previous_x - target_x);
            let origin_dy = logic_units(previous_y - target_y);
            let waypoint_dx = logic_units(waypoint_x - target_x);
            let waypoint_dy = logic_units(waypoint_y - target_y);
            let origin_distance = integer_sqrt(
                (i128::from(origin_dx) * i128::from(origin_dx)
                    + i128::from(origin_dy) * i128::from(origin_dy)) as u128,
            );
            let waypoint_distance = integer_sqrt(
                (i128::from(waypoint_dx) * i128::from(waypoint_dx)
                    + i128::from(waypoint_dy) * i128::from(waypoint_dy)) as u128,
            );
            self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state")
                .ground_path_backwards = waypoint_distance > origin_distance;
        }
        let dx = waypoint_x - previous_x;
        let dy = waypoint_y - previous_y;
        let dx_units = logic_units(dx);
        let dy_units = logic_units(dy);
        if dx_units != 0 || dy_units != 0 {
            let combat = self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state");
            combat.facing_x_units = dx_units;
            combat.facing_y_units = dy_units;
        }
        let distance = (dx * dx + dy * dy).sqrt();
        let (external_x, external_y) = {
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            if movement.pending_consumed {
                (0.0, 0.0)
            } else {
                movement.pending_consumed = true;
                (movement.pending_x, movement.pending_y)
            }
        };
        let external_x_units = logic_units(external_x);
        let external_y_units = logic_units(external_y);
        if distance > 0.0 {
            let (effective_speed, avoidance) = {
                let movement = self.entities[entity_index]
                    .movement
                    .as_ref()
                    .expect("resident troop requires movement state");
                let modifiers = self.entities[entity_index]
                    .modifier_state
                    .as_ref()
                    .expect("resident troop requires modifier state");
                let debuff = modifiers
                    .slow_multiplier
                    .max(0.0)
                    .min(modifiers.movement_mode_multiplier.max(0.0));
                let unslowed = modifiers.original_speed.unwrap_or_else(|| {
                    if debuff > 1e-9 {
                        modifiers.speed.as_f64() / debuff
                    } else if movement.serialized_speed != 0.0 {
                        movement.serialized_speed
                    } else {
                        modifiers.speed.as_f64()
                    }
                });
                let base = unslowed.round_ties_even().max(0.0) as i64;
                let debuff_percent = (debuff * 100.0).round_ties_even().max(0.0) as i64;
                let buff_percent = (modifiers.movement_speed_buff_multiplier * 100.0)
                    .round_ties_even()
                    .max(0.0) as i64;
                (
                    (base * buff_percent / 100) * debuff_percent / 100,
                    movement.native_avoidance,
                )
            };
            let movement_work = Self::speed_work_for_duration(effective_speed, self.dt);
            let target_distance = integer_sqrt(
                (i128::from(dx_units) * i128::from(dx_units)
                    + i128::from(dy_units) * i128::from(dy_units)) as u128,
            )
            .max(1);
            let intended = movement_work.min(target_distance);
            let (mut move_x, mut move_y) =
                Self::movement_component_vector_logic_units(dx_units, dy_units, intended);
            if avoidance != 0 {
                let avoidance = avoidance.clamp(-256, 256);
                let retained = 256 - avoidance.abs();
                let rotated_x = ((retained * move_x) >> 8) + ((avoidance * move_y) >> 8);
                let rotated_y = ((retained * move_y) >> 8) + ((-move_x * avoidance) >> 8);
                (move_x, move_y) = normalized_vector_logic_units(rotated_x, rotated_y, intended);
            }
            let new_x = (logic_units(previous_x) + move_x + external_x_units) as f64 / 1000.0;
            let new_y = (logic_units(previous_y) + move_y + external_y_units) as f64 / 1000.0;
            let new_x = new_x.clamp(0.25, self.arena_width_tiles as f64 - 0.25);
            let new_y = new_y.clamp(0.25, self.arena_height_tiles as f64 - 0.25);
            let has_external = external_x.abs() > 1e-15 || external_y.abs() > 1e-15;
            let jump_height = self.entities[entity_index]
                .movement
                .as_ref()
                .is_some_and(|movement| movement.jump_height_present);
            if !single_node
                && jump_height
                && !has_external
                && !self.resident_ground_position_walkable(entity_index, new_x, new_y)
                && self.resident_ground_position_walkable(entity_index, previous_x, previous_y)
                && (15.0..=17.0).contains(&new_y)
                && self.start_resident_river_jump(entity_index)
            {
                return;
            }
            self.entities[entity_index].position_x.set_f64(new_x);
            self.entities[entity_index].position_y.set_f64(new_y);
        } else if external_x.abs() > 1e-15 || external_y.abs() > 1e-15 {
            let new_x = (logic_units(previous_x) + external_x_units) as f64 / 1000.0;
            let new_y = (logic_units(previous_y) + external_y_units) as f64 / 1000.0;
            self.entities[entity_index]
                .position_x
                .set_f64(new_x.clamp(0.25, self.arena_width_tiles as f64 - 0.25));
            self.entities[entity_index]
                .position_y
                .set_f64(new_y.clamp(0.25, self.arena_height_tiles as f64 - 0.25));
        }
        self.advance_resident_route(entity_index, previous_x, previous_y, waypoint_x, waypoint_y);
    }

    fn resident_ground_position_walkable(
        &self,
        entity_index: usize,
        position_x: f64,
        position_y: f64,
    ) -> bool {
        let edge_epsilon = 1e-9;
        if position_x < 0.25 - edge_epsilon
            || position_x > self.arena_width_tiles as f64 - 0.25 + edge_epsilon
            || position_y < 0.25 - edge_epsilon
            || position_y > self.arena_height_tiles as f64 - 0.25 + edge_epsilon
        {
            return false;
        }
        if Self::standard_position_touches_blocked_tile(position_x, position_y) {
            return false;
        }
        let in_river = (15.0..=17.0).contains(&position_y);
        let on_bridge = (2.0..=5.0).contains(&position_x) || (13.0..=16.0).contains(&position_x);
        if in_river && !on_bridge {
            return false;
        }
        let mover_radius = self.entities[entity_index]
            .movement
            .as_ref()
            .expect("resident troop requires movement state")
            .collision_radius
            .min(0.5);
        self.entities.iter().all(|building| {
            if !building.active || !building.is_alive || building.entity_kind != 1 {
                return true;
            }
            let building_radius = building
                .movement
                .as_ref()
                .expect("building requires movement state")
                .building_pathing_radius;
            let collision_units = logic_units(building_radius + mover_radius);
            let dx = logic_units(position_x - building.position_x.as_f64());
            let dy = logic_units(position_y - building.position_y.as_f64());
            i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)
                >= i128::from(collision_units) * i128::from(collision_units)
        })
    }

    fn start_resident_river_jump(&mut self, entity_index: usize) -> bool {
        let landing = {
            let movement = self.entities[entity_index]
                .movement
                .as_ref()
                .expect("resident troop requires movement state");
            let river_start = movement
                .route_cells
                .iter()
                .position(|&(cell_x, cell_y)| Self::standard_path_cell_blocked(cell_x, cell_y));
            river_start.and_then(|river_start| {
                movement.route_cells[river_start + 1..]
                    .iter()
                    .copied()
                    .find(|&(cell_x, cell_y)| !Self::standard_path_cell_blocked(cell_x, cell_y))
            })
        };
        let Some(landing) = landing else {
            self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state")
                .river_jump_blocked = true;
            return false;
        };
        let origin_x = self.entities[entity_index].position_x.as_f64();
        let origin_y = self.entities[entity_index].position_y.as_f64();
        let target_x = (landing.0 * 500 + 250) as f64 / 1000.0;
        let target_y = (landing.1 * 500 + 250) as f64 / 1000.0;
        let dx = logic_units(target_x) - logic_units(origin_x);
        let dy = logic_units(target_y) - logic_units(origin_y);
        let distance = integer_sqrt(
            (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128,
        );
        let jump_speed = self.entities[entity_index]
            .movement
            .as_ref()
            .expect("resident troop requires movement state")
            .jump_speed
            .round_ties_even() as i64;
        if jump_speed <= 0 {
            return false;
        }
        let duration = self.dt.max(distance as f64 / jump_speed as f64 * 0.05);
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        movement.route_cells = vec![landing];
        movement.river_jump_origin = Some((origin_x, origin_y));
        movement.river_jump_target = Some((target_x, target_y));
        movement.river_jump_elapsed = 0.0;
        movement.river_jump_duration = duration;
        movement.river_jump_active = true;
        movement.special_move_active = true;
        self.entities[entity_index]
            .locked_combat
            .as_mut()
            .expect("resident troop requires combat state")
            .is_airborne_for_projectile = true;
        true
    }

    fn standard_path_cell_blocked(cell_x: i64, cell_y: i64) -> bool {
        (30..34).contains(&cell_y) && !((5..=8).contains(&cell_x) || (27..=30).contains(&cell_x))
    }

    fn standard_position_touches_blocked_tile(position_x: f64, position_y: f64) -> bool {
        let touching_tiles = |value: f64, limit: i64| -> Vec<i64> {
            let rounded = value.round_ties_even();
            let tolerance = 1e-9_f64.max(1e-9 * value.abs().max(rounded.abs()));
            if (value - rounded).abs() <= tolerance {
                [rounded as i64 - 1, rounded as i64]
                    .into_iter()
                    .filter(|tile| (0..limit).contains(tile))
                    .collect()
            } else {
                let tile = value.floor() as i64;
                (0..limit)
                    .contains(&tile)
                    .then_some(tile)
                    .into_iter()
                    .collect()
            }
        };
        let x_tiles = touching_tiles(position_x, 18);
        let y_tiles = touching_tiles(position_y, 32);
        x_tiles.iter().any(|&tile_x| {
            y_tiles.iter().any(|&tile_y| {
                matches!(
                    (tile_x, tile_y),
                    (0 | 17, 14 | 17) | (0..=5, 0 | 31) | (12..=17, 0 | 31)
                )
            })
        })
    }

    fn resident_ground_waypoint(
        &mut self,
        entity_index: usize,
        goal: Option<(i64, i64)>,
        previous_x: f64,
        previous_y: f64,
        target_x: f64,
        target_y: f64,
    ) -> (f64, f64) {
        let (lane_id, jump_height) = {
            let movement = self.entities[entity_index]
                .movement
                .as_ref()
                .expect("resident troop requires movement state");
            (movement.native_lane_id, movement.jump_height_present)
        };
        if let Some(goal) = goal {
            let cache_hit = self.entities[entity_index]
                .movement
                .as_ref()
                .is_some_and(|movement| {
                    movement.route_cache_kind == RouteCacheKind::Ground
                        && movement.route_goal == Some(goal)
                        && movement.route_lane_id == lane_id
                        && movement.route_jump_height == jump_height
                });
            if cache_hit {
                let (backwards, waypoint) = {
                    let movement = self.entities[entity_index]
                        .movement
                        .as_ref()
                        .expect("resident troop requires movement state");
                    (
                        movement.route_backwards,
                        movement.route_cells.first().map_or(
                            (target_x, target_y),
                            |(cell_x, cell_y)| {
                                (
                                    (*cell_x * 500 + 250) as f64 / 1000.0,
                                    (*cell_y * 500 + 250) as f64 / 1000.0,
                                )
                            },
                        ),
                    )
                };
                self.entities[entity_index]
                    .locked_combat
                    .as_mut()
                    .expect("resident troop requires combat state")
                    .ground_path_backwards = backwards;
                return waypoint;
            }
        }

        let origin_dx = logic_units(previous_x - target_x);
        let origin_dy = logic_units(previous_y - target_y);
        let origin_distance = integer_sqrt(
            (i128::from(origin_dx) * i128::from(origin_dx)
                + i128::from(origin_dy) * i128::from(origin_dy)) as u128,
        );
        let Some(goal) = goal else {
            self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state")
                .ground_path_backwards = false;
            return (target_x, target_y);
        };
        let start = (
            (logic_units(previous_x) / 500).clamp(0, STANDARD_PATH_WIDTH - 1),
            (logic_units(previous_y) / 500).clamp(0, STANDARD_PATH_HEIGHT - 1),
        );
        let desired_waypoint = (
            (goal.0 * 500 + 250) as f64 / 1000.0,
            (goal.1 * 500 + 250) as f64 / 1000.0,
        );
        if goal == start {
            let backwards = Self::waypoint_is_backwards(
                desired_waypoint.0,
                desired_waypoint.1,
                target_x,
                target_y,
                origin_distance,
            );
            let movement = self.entities[entity_index]
                .movement
                .as_mut()
                .expect("resident troop requires movement state");
            movement.route_cache_supported = true;
            movement.route_cache_kind = RouteCacheKind::Ground;
            movement.route_goal = Some(goal);
            movement.route_cells.clear();
            movement.route_backwards = backwards;
            movement.route_lane_id = lane_id;
            movement.route_jump_height = jump_height;
            self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state")
                .ground_path_backwards = backwards;
            return desired_waypoint;
        }
        let Some(route) = exact_standard_grid_route(start, goal, lane_id, jump_height) else {
            self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state")
                .ground_path_backwards = false;
            return (target_x, target_y);
        };
        if route.len() < 2 {
            self.entities[entity_index]
                .locked_combat
                .as_mut()
                .expect("resident troop requires combat state")
                .ground_path_backwards = false;
            return (target_x, target_y);
        }
        let retained = route[1..].to_vec();
        let backwards = retained.iter().any(|(cell_x, cell_y)| {
            Self::waypoint_is_backwards(
                (*cell_x * 500 + 250) as f64 / 1000.0,
                (*cell_y * 500 + 250) as f64 / 1000.0,
                target_x,
                target_y,
                origin_distance,
            )
        });
        let first = retained[0];
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        movement.route_cache_supported = true;
        movement.route_cache_kind = RouteCacheKind::Ground;
        movement.route_goal = Some(goal);
        movement.route_cells = retained;
        movement.route_backwards = backwards;
        movement.route_lane_id = lane_id;
        movement.route_jump_height = jump_height;
        self.entities[entity_index]
            .locked_combat
            .as_mut()
            .expect("resident troop requires combat state")
            .ground_path_backwards = backwards;
        (
            (first.0 * 500 + 250) as f64 / 1000.0,
            (first.1 * 500 + 250) as f64 / 1000.0,
        )
    }

    fn waypoint_is_backwards(
        waypoint_x: f64,
        waypoint_y: f64,
        reference_x: f64,
        reference_y: f64,
        origin_distance: i64,
    ) -> bool {
        let dx = logic_units(waypoint_x - reference_x);
        let dy = logic_units(waypoint_y - reference_y);
        integer_sqrt((i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128)
            > origin_distance
    }

    fn advance_resident_route(
        &mut self,
        entity_index: usize,
        previous_x: f64,
        previous_y: f64,
        waypoint_x: f64,
        waypoint_y: f64,
    ) {
        let current_x = self.entities[entity_index].position_x.as_f64();
        let current_y = self.entities[entity_index].position_y.as_f64();
        let movement = self.entities[entity_index]
            .movement
            .as_mut()
            .expect("resident troop requires movement state");
        let Some(&(cell_x, cell_y)) = movement.route_cells.first() else {
            return;
        };
        if waypoint_x != (cell_x * 500 + 250) as f64 / 1000.0
            || waypoint_y != (cell_y * 500 + 250) as f64 / 1000.0
        {
            return;
        }
        let (direction_x, direction_y) = normalized_vector_logic_units(
            logic_units(waypoint_x - previous_x),
            logic_units(waypoint_y - previous_y),
            256,
        );
        let remaining_x = logic_units(waypoint_x - current_x);
        let remaining_y = logic_units(waypoint_y - current_y);
        let projected = truncating_div(i128::from(direction_y) * i128::from(remaining_y), 256)
            + truncating_div(i128::from(direction_x) * i128::from(remaining_x), 256);
        if projected < 1001 {
            movement.route_cells.remove(0);
        }
    }

    fn resident_natural_movement_state_bytes(&self) -> PyResult<Vec<u8>> {
        let values = self
            .entities
            .iter()
            .filter(|entity| entity.active && matches!(entity.entity_kind, 0 | 1))
            .map(|entity| {
                let movement = entity
                    .movement
                    .as_ref()
                    .expect("character movement state parsed at initialization");
                let combat = entity
                    .locked_combat
                    .as_ref()
                    .expect("character combat state parsed at initialization");
                json!({
                    "airborne_for_projectile": combat.is_airborne_for_projectile,
                    "building_pathing_radius": exact_f64_value(movement.building_pathing_radius),
                    "death_spawn_travel_target": movement.death_spawn_travel_target.map(|(x, y)| {
                        json!([exact_f64_value(x), exact_f64_value(y)])
                    }),
                    "death_spawn_travel_ticks": movement.death_spawn_travel_ticks,
                    "encounter_index": entity.encounter_index,
                    "facing_x_units": combat.facing_x_units,
                    "facing_y_units": combat.facing_y_units,
                    "ground_path_backwards": combat.ground_path_backwards,
                    "id": entity.id,
                    "jump_speed": exact_f64_value(movement.jump_speed),
                    "knockback_interrupts_combat": movement.knockback_interrupts_combat,
                    "knockback_target": movement.knockback_target.map(|(x, y)| {
                        json!([exact_f64_value(x), exact_f64_value(y)])
                    }),
                    "knockback_velocity_work": movement.knockback_velocity_work,
                    "native_avoidance": movement.native_avoidance,
                    "native_lane_id": movement.native_lane_id,
                    "native_natural_movement_active": movement.native_natural_movement_active,
                    "pending_consumed": movement.pending_consumed,
                    "pending_x": exact_f64_value(movement.pending_x),
                    "pending_y": exact_f64_value(movement.pending_y),
                    "position_x": entity.position_x.diagnostic_value(),
                    "position_y": entity.position_y.diagnostic_value(),
                    "route_backwards": movement.route_backwards,
                    "route_cells": movement.route_cells,
                    "route_goal": movement.route_goal,
                    "route_jump_height": movement.route_jump_height,
                    "route_kind": match movement.route_cache_kind {
                        RouteCacheKind::Absent => "absent",
                        RouteCacheKind::Single => "single",
                        RouteCacheKind::Ground => "ground",
                        RouteCacheKind::Unsupported => "unsupported",
                    },
                    "route_lane_id": movement.route_lane_id,
                    "river_jump_active": movement.river_jump_active,
                    "river_jump_blocked": movement.river_jump_blocked,
                    "river_jump_duration": exact_f64_value(movement.river_jump_duration),
                    "river_jump_elapsed": exact_f64_value(movement.river_jump_elapsed),
                    "river_jump_origin": movement.river_jump_origin.map(|(x, y)| {
                        json!([exact_f64_value(x), exact_f64_value(y)])
                    }),
                    "river_jump_target": movement.river_jump_target.map(|(x, y)| {
                        json!([exact_f64_value(x), exact_f64_value(y)])
                    }),
                    "special_move_active": movement.special_move_active,
                    "special_move_consumed_tick": movement.special_move_consumed_tick,
                    "stun_interrupt_deferred_until_landing": movement.stun_interrupt_deferred_until_landing,
                    "forced_movement_active": movement.forced_movement_active,
                    "vector_bypasses_cap": movement.vector_bypasses_cap,
                    "vector_count": movement.vector_count,
                    "vector_x_units": movement.vector_x_units,
                    "vector_y_units": movement.vector_y_units,
                })
            })
            .collect::<Vec<_>>();
        serde_json::to_vec(&values).map_err(|error| {
            PyRuntimeError::new_err(format!(
                "failed to serialize natural movement state: {error}"
            ))
        })
    }

    fn refresh_lethal_projectile_reservations(&mut self) {
        let mut pending_damage = Vec::<(i64, f64)>::new();
        for projectile_entity in &self.entities {
            if !projectile_entity.active || !projectile_entity.is_alive {
                continue;
            }
            let Some(projectile) = projectile_entity.point_projectile.as_ref() else {
                continue;
            };
            if !projectile.tracks_target {
                continue;
            }
            let Some(target_id) = projectile.primary_target_id else {
                continue;
            };
            let Some(target) = self.entities.iter().find(|candidate| {
                candidate.id == target_id && candidate.active && candidate.is_alive
            }) else {
                continue;
            };
            let damage = if target
                .building_impact
                .as_ref()
                .is_some_and(|building| building.crown_slot.is_some())
            {
                projectile.crown_tower_damage.unwrap_or_else(|| {
                    let base = projectile_entity.damage.as_f64().round_ties_even().max(0.0) as i64;
                    let percentage = (projectile.crown_tower_damage_multiplier * 100.0)
                        .round_ties_even()
                        .max(0.0) as i64;
                    if base == 0 || percentage == 0 {
                        0.0
                    } else {
                        ((base * percentage + 99) / 100) as f64
                    }
                })
            } else {
                projectile_entity.damage.as_f64().max(0.0)
            };
            if damage <= 0.0 {
                continue;
            }
            if let Some((_, total)) = pending_damage
                .iter_mut()
                .find(|(pending_target_id, _)| *pending_target_id == target_id)
            {
                *total += damage;
            } else {
                pending_damage.push((target_id, damage));
            }
        }
        self.lethal_projectile_reservation_ids.clear();
        for (target_id, damage) in pending_damage {
            let target = self
                .entities
                .iter()
                .find(|candidate| candidate.id == target_id)
                .expect("reservation target was collected from resident entities");
            if target.pending_projectile_max_duration_ms <= 600
                && !target
                    .shields
                    .iter()
                    .any(|shield| shield.current.as_f64() > 0.0)
                && damage >= target.hitpoints.as_f64()
            {
                self.lethal_projectile_reservation_ids.push(target_id);
            }
        }
    }

    fn prepare_direct_combat_actor(&mut self, actor_index: usize) -> Option<f64> {
        if self.entities[actor_index].entity_kind != 1 {
            return Some(self.dt);
        }
        let building = self.entities[actor_index]
            .building_impact
            .as_mut()
            .expect("building combat preflight requires impact state");
        if building.crown_slot.as_deref() == Some("king") && !building.tower_active {
            return None;
        }
        let mut step_dt = self.dt;
        if building.activation_delay_remaining > 0.0 {
            let work = step_dt.min(building.activation_delay_remaining);
            building.activation_delay_remaining =
                (building.activation_delay_remaining - work).max(0.0);
            step_dt -= work;
            if step_dt <= 1e-9 {
                return None;
            }
        }
        if building.activation_first_hit_delay_remaining > 0.0 {
            let work = step_dt.min(building.activation_first_hit_delay_remaining);
            building.activation_first_hit_delay_remaining =
                (building.activation_first_hit_delay_remaining - work).max(0.0);
            step_dt -= work;
            if building.activation_first_hit_delay_remaining > 1e-9 {
                return None;
            }
            let combat = self.entities[actor_index]
                .locked_combat
                .as_mut()
                .expect("building combat preflight requires combat state");
            combat.attack_cooldown = 0.0;
            combat.attack_preload_blocked = false;
            step_dt = step_dt.max(0.0);
        }
        Some(step_dt)
    }

    fn apply_direct_combat_damage(&mut self, target_index: usize, damage: f64) {
        let damage = self.entities[target_index].apply_incoming_damage(damage);
        if damage <= 0.0 {
            return;
        }
        if let Some(building) = self.entities[target_index].building_impact.as_mut()
            && damage > 0.0
            && building.requires_activation
            && !building.tower_active
        {
            building.tower_active = true;
            building.activation_delay_remaining = building
                .activation_delay_remaining
                .max(building.activation_delay_seconds);
            building.activation_first_hit_delay_remaining = building
                .activation_first_hit_delay_remaining
                .max(building.activation_first_hit_delay_seconds);
        }
        let remaining = (self.entities[target_index].hitpoints.as_f64() - damage).max(0.0);
        if remaining <= 0.0 {
            self.entities[target_index].hitpoints = ExactScalar::Int(0);
            self.entities[target_index].is_alive = false;
        } else {
            self.entities[target_index].hitpoints.set_f64(remaining);
        }
        if self.entities[target_index].entity_kind == 1 {
            if self.entities[target_index]
                .building_impact
                .as_ref()
                .is_some_and(|building| building.crown_slot.is_some())
            {
                self.win_conditions_dirty = true;
            }
            self.sync_resident_tower(target_index);
        }
    }

    fn sync_resident_tower(&mut self, entity_index: usize) {
        let entity = &self.entities[entity_index];
        let Some(building) = entity.building_impact.as_ref() else {
            return;
        };
        let Some(slot) = building.crown_slot.as_deref() else {
            return;
        };
        let Some(tower) = self.towers.iter_mut().find(|tower| tower.id == entity.id) else {
            return;
        };
        debug_assert_eq!(tower.slot, slot);
        tower.hp = entity.hitpoints.clone();
        tower.hp_milli = (tower.hp.as_f64() * 1000.0).round_ties_even() as i64;
        tower.is_alive = entity.is_alive;
        tower.is_active = building.tower_active;
        tower.last_attack_time = entity
            .locked_combat
            .as_ref()
            .expect("Crown Tower requires combat state")
            .last_attack_time;
    }

    fn launch_point_projectile(
        &mut self,
        source_index: usize,
        target_index: usize,
        weapon: PointWeapon,
    ) {
        let source = &self.entities[source_index];
        let target = &self.entities[target_index];
        let source_x_units = logic_units(source.position_x.as_f64());
        let source_y_units = logic_units(source.position_y.as_f64());
        let dx_units = logic_units(target.position_x.as_f64() - source.position_x.as_f64());
        let dy_units = logic_units(target.position_y.as_f64() - source.position_y.as_f64());
        let (muzzle_x_units, muzzle_y_units) =
            normalized_vector_logic_units(dx_units, dy_units, logic_units(weapon.start_radius));
        let owner_y_offset = weapon.y_offset * if source.player_id == 0 { 1.0 } else { -1.0 };
        let launch_x_units = source_x_units + muzzle_x_units;
        let launch_y_units = source_y_units + muzzle_y_units + logic_units(owner_y_offset);
        let launch_x = launch_x_units as f64 / 1000.0;
        let launch_y = launch_y_units as f64 / 1000.0;
        let target_x = target.position_x.as_f64();
        let target_y = target.position_y.as_f64();
        let source_id = source.id;
        let target_id = target.id;
        let player_id = source.player_id;
        let card_name = source.card_name.clone();
        let damage = source.damage.clone();
        let inherited_hit_planes = {
            let combat = source
                .locked_combat
                .as_ref()
                .expect("point weapon requires combat state");
            (combat.can_attack_air, combat.can_attack_ground)
        };
        let (hits_air, hits_ground) = weapon.hit_planes.unwrap_or(inherited_hit_planes);

        if weapon.tracks_target {
            let pending_dx = logic_units(target_x - launch_x);
            let pending_dy = logic_units(target_y - launch_y);
            let distance = integer_sqrt(
                (i128::from(pending_dx) * i128::from(pending_dx)
                    + i128::from(pending_dy) * i128::from(pending_dy)) as u128,
            );
            let speed_units = (weapon.travel_speed * 1000.0 * 0.05).round_ties_even() as i64;
            let duration_ms = if speed_units <= 0 {
                1000
            } else {
                let raw = distance * 50 / speed_units;
                (((raw + 49) / 50) * 50).min(1000)
            };
            self.entities[target_index].pending_projectile_max_duration_ms = self.entities
                [target_index]
                .pending_projectile_max_duration_ms
                .max(duration_ms);
        }

        let projectile_id = self.next_entity_id;
        self.next_entity_id += 1;
        self.entities.push(ResidentEntity {
            active: true,
            encounter_index: self.entities.iter().filter(|entity| entity.active).count(),
            id: projectile_id,
            player_id,
            entity_kind: 2,
            python_type: "clasher.entities.Projectile".to_owned(),
            card_name,
            position_x: ExactScalar::Float(launch_x.to_bits()),
            position_y: ExactScalar::Float(launch_y.to_bits()),
            hitpoints: ExactScalar::Int(1),
            max_hitpoints: ExactScalar::Int(1),
            damage,
            is_alive: true,
            target_id: None,
            deploy_delay_remaining: 0.0,
            placement_pending: false,
            spawn_hook_pending: false,
            spawn_hook_fired: false,
            death_spawn_target_immunity_elapsed_ms: -1,
            pending_projectile_max_duration_ms: 0,
            mechanics: Vec::new(),
            shields: Vec::new(),
            modifier_state: None,
            movement: None,
            modifier_supported: true,
            direct_combat_unsupported: vec!["non_character_entity".to_owned()],
            locked_combat: None,
            building_lifetime: None,
            building_impact: None,
            point_projectile: Some(PointProjectileState {
                target_x,
                target_y,
                travel_speed: weapon.travel_speed,
                splash_radius: weapon.splash_radius,
                hits_air,
                hits_ground,
                ignore_buildings: false,
                crown_tower_damage: None,
                crown_tower_damage_multiplier: weapon.crown_tower_damage_multiplier,
                stun_duration: weapon.stun_duration,
                slow_duration: weapon.slow_duration,
                slow_multiplier: weapon.slow_multiplier,
                launch_delay: 0.0,
                primary_target_id: Some(target_id),
                source_entity_id: Some(source_id),
                tracks_target: weapon.tracks_target,
                temporary_homing_remaining_ms: 0,
                temporary_homing_target_id: None,
                permanent_homing_disabled_by_temporary: false,
                start_collision_resolved: true,
                unsupported: Vec::new(),
            }),
            object_base_movement_noop: true,
        });
    }

    fn advance_point_projectile(&mut self, projectile_index: usize) {
        if !self.entities[projectile_index].is_alive {
            return;
        }
        let mut step_dt = self.dt;
        {
            let projectile = self.entities[projectile_index]
                .point_projectile
                .as_mut()
                .expect("point-projectile preflight requires state");
            if projectile.launch_delay > 0.0 {
                if step_dt <= projectile.launch_delay + 1e-12 {
                    projectile.launch_delay = (projectile.launch_delay - step_dt).max(0.0);
                    let position_x =
                        logic_units(self.entities[projectile_index].position_x.as_f64());
                    let position_y =
                        logic_units(self.entities[projectile_index].position_y.as_f64());
                    self.entities[projectile_index]
                        .position_x
                        .set_f64(position_x as f64 / 1000.0);
                    self.entities[projectile_index]
                        .position_y
                        .set_f64(position_y as f64 / 1000.0);
                    return;
                }
                step_dt -= projectile.launch_delay;
                projectile.launch_delay = 0.0;
            }
        }

        let (
            temporary_remaining,
            temporary_target_id,
            tracks_target,
            permanent_homing_disabled,
            primary_target_id,
        ) = {
            let projectile = self.entities[projectile_index]
                .point_projectile
                .as_ref()
                .expect("point-projectile preflight requires state");
            (
                projectile.temporary_homing_remaining_ms,
                projectile.temporary_homing_target_id,
                projectile.tracks_target,
                projectile.permanent_homing_disabled_by_temporary,
                projectile.primary_target_id,
            )
        };
        let homing_target_id = if temporary_remaining > 0 {
            temporary_target_id
        } else if tracks_target && !permanent_homing_disabled {
            primary_target_id
        } else {
            None
        };
        if let Some(target_id) = homing_target_id {
            let target = self
                .entities
                .iter()
                .find(|candidate| candidate.id == target_id)
                .expect("point-projectile preflight requires homing target");
            let target_position = (target.position_x.as_f64(), target.position_y.as_f64());
            let projectile = self.entities[projectile_index]
                .point_projectile
                .as_mut()
                .expect("point-projectile preflight requires state");
            projectile.target_x = target_position.0;
            projectile.target_y = target_position.1;
            if temporary_remaining > 0 {
                projectile.temporary_homing_remaining_ms -= 50;
            }
        } else if temporary_remaining > 0 {
            self.entities[projectile_index]
                .point_projectile
                .as_mut()
                .expect("point-projectile preflight requires state")
                .temporary_homing_remaining_ms = 0;
        }

        let (position_x, position_y, target_x, target_y, travel_speed, target_id) = {
            let entity = &self.entities[projectile_index];
            let projectile = entity
                .point_projectile
                .as_ref()
                .expect("point-projectile preflight requires state");
            (
                entity.position_x.as_f64(),
                entity.position_y.as_f64(),
                projectile.target_x,
                projectile.target_y,
                projectile.travel_speed,
                projectile.primary_target_id,
            )
        };
        let dx = logic_units(target_x - position_x);
        let dy = logic_units(target_y - position_y);
        let remaining = integer_sqrt(
            (i128::from(dx) * i128::from(dx) + i128::from(dy) * i128::from(dy)) as u128,
        );
        let serialized_speed = (travel_speed * 1000.0 * 0.05).round_ties_even().max(0.0) as i64;
        let tick_count = step_dt.max(0.0) / 0.05;
        let rounded_tick_count = tick_count.round_ties_even();
        let travel = if (tick_count - rounded_tick_count).abs() <= 1e-9 {
            serialized_speed * rounded_tick_count as i64
        } else {
            (serialized_speed as f64 * tick_count)
                .round_ties_even()
                .max(0.0) as i64
        };
        if remaining <= travel {
            let (
                projectile_player,
                damage,
                hits_air,
                hits_ground,
                splash_radius,
                source_entity_id,
                ignore_buildings,
                crown_tower_damage,
                crown_tower_damage_multiplier,
                stun_duration,
                slow_duration,
                slow_multiplier,
            ) = {
                let entity = &self.entities[projectile_index];
                let projectile = entity
                    .point_projectile
                    .as_ref()
                    .expect("point-projectile preflight requires state");
                (
                    entity.player_id,
                    entity.damage.as_f64(),
                    projectile.hits_air,
                    projectile.hits_ground,
                    projectile.splash_radius,
                    projectile.source_entity_id,
                    projectile.ignore_buildings,
                    projectile.crown_tower_damage,
                    projectile.crown_tower_damage_multiplier,
                    projectile.stun_duration,
                    projectile.slow_duration,
                    projectile.slow_multiplier,
                )
            };
            let source_is_character = source_entity_id.is_some_and(|id| {
                self.entities
                    .iter()
                    .find(|candidate| candidate.id == id)
                    .is_some_and(|source| matches!(source.entity_kind, 0 | 1))
            });
            let now_ms = (self.time * 1000.0).round_ties_even() as i64;
            let can_damage_index = |target_index: usize| {
                let target = &self.entities[target_index];
                let Some((target_is_air, _, _, _)) = target.projectile_target_traits() else {
                    return false;
                };
                target.active
                    && target.is_alive
                    && target.player_id != projectile_player
                    && matches!(target.entity_kind, 0 | 1)
                    && !(ignore_buildings && target.entity_kind == 1)
                    && ((target_is_air && hits_air) || (!target_is_air && hits_ground))
            };
            let hit_targets = if splash_radius <= 0.0 {
                target_id
                    .and_then(|id| {
                        self.entities
                            .iter()
                            .position(|candidate| candidate.id == id)
                    })
                    .filter(|index| can_damage_index(*index))
                    .into_iter()
                    .collect::<Vec<_>>()
            } else {
                let center_x_units = logic_units(target_x);
                let center_y_units = logic_units(target_y);
                let area_radius_units = logic_units(splash_radius).max(0);
                self.entities
                    .iter()
                    .enumerate()
                    .filter_map(|(target_index, target)| {
                        if !can_damage_index(target_index) {
                            return None;
                        }
                        let (_, collision_radius, stealth_until_ms, allow_invisible) = target
                            .projectile_target_traits()
                            .expect("splash preflight requires target traits");
                        if (source_is_character
                            && target.death_spawn_target_immunity_elapsed_ms >= 0)
                            || (stealth_until_ms > now_ms && !allow_invisible)
                        {
                            return None;
                        }
                        let target_x_units = logic_units(target.position_x.as_f64());
                        let target_y_units = logic_units(target.position_y.as_f64());
                        let collision_radius_units = logic_units(collision_radius).max(0);
                        let intersects = if target.entity_kind == 1 {
                            let closest_x = center_x_units.clamp(
                                target_x_units - collision_radius_units,
                                target_x_units + collision_radius_units,
                            );
                            let closest_y = center_y_units.clamp(
                                target_y_units - collision_radius_units,
                                target_y_units + collision_radius_units,
                            );
                            let dx_units = closest_x - center_x_units;
                            let dy_units = closest_y - center_y_units;
                            i128::from(dx_units) * i128::from(dx_units)
                                + i128::from(dy_units) * i128::from(dy_units)
                                < i128::from(area_radius_units) * i128::from(area_radius_units)
                        } else {
                            let dx_units = target_x_units - center_x_units;
                            let dy_units = target_y_units - center_y_units;
                            let combined_radius = area_radius_units + collision_radius_units;
                            i128::from(dx_units) * i128::from(dx_units)
                                + i128::from(dy_units) * i128::from(dy_units)
                                < i128::from(combined_radius) * i128::from(combined_radius)
                        };
                        intersects.then_some(target_index)
                    })
                    .collect::<Vec<_>>()
            };
            let status_targets = hit_targets.clone();
            if damage > 0.0 {
                for &target_index in &hit_targets {
                    let crown_slot = self.entities[target_index]
                        .building_impact
                        .as_ref()
                        .and_then(|state| state.crown_slot.clone());
                    let target_damage = if crown_slot.is_some() {
                        crown_tower_damage.unwrap_or_else(|| {
                            let base = damage.round_ties_even().max(0.0) as i64;
                            let percentage = (crown_tower_damage_multiplier * 100.0)
                                .round_ties_even()
                                .max(0.0) as i64;
                            if base == 0 || percentage == 0 {
                                0.0
                            } else {
                                ((base * percentage + 99) / 100) as f64
                            }
                        })
                    } else {
                        damage
                    };
                    if target_damage <= 0.0 {
                        continue;
                    }
                    let target_damage =
                        self.entities[target_index].apply_incoming_damage(target_damage);
                    if target_damage <= 0.0 {
                        continue;
                    }
                    if let Some(building) = self.entities[target_index].building_impact.as_mut()
                        && building.requires_activation
                        && !building.tower_active
                    {
                        building.tower_active = true;
                        building.activation_delay_remaining = building
                            .activation_delay_remaining
                            .max(building.activation_delay_seconds);
                        building.activation_first_hit_delay_remaining = building
                            .activation_first_hit_delay_remaining
                            .max(building.activation_first_hit_delay_seconds);
                    }
                    let remaining_hp =
                        (self.entities[target_index].hitpoints.as_f64() - target_damage).max(0.0);
                    if remaining_hp <= 0.0 {
                        self.entities[target_index].hitpoints = ExactScalar::Int(0);
                        self.entities[target_index].is_alive = false;
                    } else {
                        self.entities[target_index].hitpoints.set_f64(remaining_hp);
                    }
                    if crown_slot.is_some() {
                        self.win_conditions_dirty = true;
                        self.sync_resident_tower(target_index);
                    }
                }
            }
            for target_index in status_targets {
                if splash_radius > 0.0 && !self.entities[target_index].is_alive {
                    continue;
                }
                self.entities[target_index].apply_projectile_status(
                    stun_duration,
                    slow_duration,
                    slow_multiplier,
                );
            }
            self.entities[projectile_index].is_alive = false;
            self.entities[projectile_index]
                .position_x
                .set_f64(logic_units(position_x) as f64 / 1000.0);
            self.entities[projectile_index]
                .position_y
                .set_f64(logic_units(position_y) as f64 / 1000.0);
        } else {
            let (move_x, move_y) = vector_towards_logic_units(dx, dy, travel);
            self.entities[projectile_index]
                .position_x
                .set_f64((logic_units(position_x) + move_x) as f64 / 1000.0);
            self.entities[projectile_index]
                .position_y
                .set_f64((logic_units(position_y) + move_y) as f64 / 1000.0);
        }
    }

    fn direct_target_valid(&self, actor_index: usize, target_index: usize) -> bool {
        if actor_index == target_index {
            return false;
        }
        let actor = &self.entities[actor_index];
        let target = &self.entities[target_index];
        let (Some(actor_state), Some(target_state)) =
            (actor.locked_combat.as_ref(), target.locked_combat.as_ref())
        else {
            return false;
        };
        let now_ms = (self.time * 1000.0).round_ties_even() as i64;
        actor.active
            && target.active
            && target.is_alive
            && target.player_id != actor.player_id
            && !target_state.hidden_building
            && target_state.stealth_until_ms <= now_ms
            && target.death_spawn_target_immunity_elapsed_ms < 0
            && ((target_state.is_air_unit && actor_state.can_attack_air)
                || (!target_state.is_air_unit && actor_state.can_attack_ground))
            && !(actor_state.point_weapon.is_some()
                && self.lethal_projectile_reservation_ids.contains(&target.id))
    }

    fn direct_target_distance(&self, actor_index: usize, target_index: usize) -> f64 {
        let actor = &self.entities[actor_index];
        let target = &self.entities[target_index];
        let target_state = target
            .locked_combat
            .as_ref()
            .expect("character target has combat state");
        let dx = target.position_x.as_f64() - actor.position_x.as_f64();
        let dy = target.position_y.as_f64() - actor.position_y.as_f64();
        let discount =
            target_state.native_target_distance_discount_sq_units.max(0) as f64 / 1_000_000.0;
        (dx * dx + dy * dy - discount).max(0.0).sqrt()
    }

    fn direct_attack_reach(&self, actor_index: usize, target_index: usize) -> bool {
        let actor_state = self.entities[actor_index]
            .locked_combat
            .as_ref()
            .expect("character actor has combat state");
        let target_state = self.entities[target_index]
            .locked_combat
            .as_ref()
            .expect("character target has combat state");
        let extension = if self.direct_projectile_hit_cycle_started(actor_index) {
            0.5
        } else if actor_state.attack_windup_active {
            0.025
        } else {
            0.0
        };
        self.direct_target_distance(actor_index, target_index)
            <= actor_state.range + target_state.collision_radius + extension + 1e-8
    }

    fn direct_keep_reach(&self, actor_index: usize, target_index: usize) -> bool {
        let actor_state = self.entities[actor_index]
            .locked_combat
            .as_ref()
            .expect("character actor has combat state");
        let target_state = self.entities[target_index]
            .locked_combat
            .as_ref()
            .expect("character target has combat state");
        let extension = if self.direct_projectile_hit_cycle_started(actor_index) {
            0.5
        } else {
            0.025
        };
        self.direct_target_distance(actor_index, target_index)
            <= actor_state.range + target_state.collision_radius + extension + 1e-8
    }

    fn direct_projectile_hit_cycle_started(&self, actor_index: usize) -> bool {
        let Some(state) = self.entities[actor_index].locked_combat.as_ref() else {
            return false;
        };
        if state.point_weapon.is_none() || state.hit_speed_ms <= 0 {
            return false;
        }
        let remaining_ms = (state.attack_cooldown.max(0.0) * 1000.0).round_ties_even() as i64;
        (-remaining_ms).rem_euclid(state.hit_speed_ms) > 50
    }

    fn direct_is_native_building_target(&self, target_index: usize) -> bool {
        let target = &self.entities[target_index];
        target.entity_kind == 1
            || target
                .locked_combat
                .as_ref()
                .is_some_and(|state| state.native_building_target)
    }

    fn direct_crown_slot(&self, target_index: usize) -> Option<&str> {
        self.entities[target_index]
            .building_impact
            .as_ref()
            .and_then(|state| state.crown_slot.as_deref())
    }

    fn direct_target_in_sight(&self, actor_index: usize, target_index: usize) -> bool {
        let actor = &self.entities[actor_index];
        let target = &self.entities[target_index];
        let actor_state = actor
            .locked_combat
            .as_ref()
            .expect("character actor has combat state");
        let target_state = target
            .locked_combat
            .as_ref()
            .expect("character target has combat state");
        let target_is_crown = self.direct_crown_slot(target_index).is_some();
        let actor_is_crown = self.direct_crown_slot(actor_index).is_some();
        let sight_reach = actor_state.sight_range
            + target_state.collision_radius
            + if target_is_crown { 2.0 } else { 0.0 };
        if self.direct_target_distance(actor_index, target_index) > sight_reach + 1e-8 {
            return false;
        }
        if actor_is_crown || target_is_crown {
            return true;
        }
        let dx = target.position_x.as_f64() - actor.position_x.as_f64();
        let dy = target.position_y.as_f64() - actor.position_y.as_f64();
        if actor_state.sight_clip_side > 0.0
            && dx.abs() > (sight_reach - actor_state.sight_clip_side).max(0.0) + 1e-8
        {
            return false;
        }
        if actor_state.sight_clip > 0.0 {
            let forward_delta = if actor.player_id == 0 { dy } else { -dy };
            if forward_delta < -(sight_reach - actor_state.sight_clip).max(0.0) - 1e-8 {
                return false;
            }
        }
        true
    }

    fn direct_troop_target_index(&self, actor_index: usize) -> Option<usize> {
        let actor = &self.entities[actor_index];
        let actor_state = actor.locked_combat.as_ref()?;
        let current = actor.target_id.and_then(|target_id| {
            self.entities
                .iter()
                .position(|entity| entity.id == target_id)
                .filter(|&index| self.direct_target_valid(actor_index, index))
        });
        if current.is_some_and(|index| self.direct_keep_reach(actor_index, index)) {
            return current;
        }
        let best =
            self.direct_acquired_target_index(actor_index, !actor_state.ground_path_backwards);
        match (current, best) {
            (None, best) => best,
            (current, None) => current,
            (Some(current), Some(best)) => {
                if self.direct_crown_slot(current) == Some("king")
                    && matches!(self.direct_crown_slot(best), Some("left" | "right"))
                    && !self.direct_attack_reach(actor_index, best)
                {
                    return Some(current);
                }
                if self.direct_is_native_building_target(current)
                    && self.direct_is_native_building_target(best)
                    && !self.direct_target_in_sight(actor_index, best)
                {
                    return Some(current);
                }
                if self.direct_target_distance(actor_index, best)
                    < self.direct_target_distance(actor_index, current) - 1e-6
                {
                    Some(best)
                } else {
                    Some(current)
                }
            }
        }
    }

    fn direct_building_target_index(&self, actor_index: usize) -> Option<usize> {
        let current = self.entities[actor_index].target_id.and_then(|target_id| {
            self.entities
                .iter()
                .position(|entity| entity.id == target_id)
                .filter(|&index| {
                    self.direct_target_valid(actor_index, index)
                        && self.direct_keep_reach(actor_index, index)
                })
        });
        if current.is_some() {
            return current;
        }
        let actor_state = self.entities[actor_index].locked_combat.as_ref()?;
        let include_crown_fallback = actor_state.range > actor_state.sight_range + 2.0;
        self.direct_acquired_target_index(actor_index, include_crown_fallback)
    }

    fn direct_acquired_target_index(
        &self,
        actor_index: usize,
        include_crown_fallback: bool,
    ) -> Option<usize> {
        let actor = &self.entities[actor_index];
        let actor_state = actor.locked_combat.as_ref()?;
        let mut troop_targets = Vec::new();
        let mut building_targets = Vec::new();
        for (target_index, _) in self.entities.iter().enumerate() {
            if !self.direct_target_valid(actor_index, target_index)
                || !self.direct_target_in_sight(actor_index, target_index)
            {
                continue;
            }
            if self.direct_is_native_building_target(target_index) {
                building_targets.push(target_index);
            } else if !actor_state.targets_only_buildings {
                troop_targets.push(target_index);
            }
        }
        let mut candidates = if actor_state.targets_only_buildings {
            building_targets
        } else {
            troop_targets.extend(building_targets);
            troop_targets
        };
        if candidates.is_empty() && include_crown_fallback {
            let crowns = self
                .entities
                .iter()
                .enumerate()
                .filter_map(|(target_index, _)| {
                    (self.direct_target_valid(actor_index, target_index)
                        && self.direct_crown_slot(target_index).is_some())
                    .then_some(target_index)
                })
                .collect::<Vec<_>>();
            let princesses = crowns
                .iter()
                .copied()
                .filter(|&target_index| {
                    matches!(self.direct_crown_slot(target_index), Some("left" | "right"))
                })
                .collect::<Vec<_>>();
            if princesses.is_empty() {
                candidates = crowns
                    .into_iter()
                    .filter(|&target_index| self.direct_crown_slot(target_index) == Some("king"))
                    .collect();
            } else {
                let actor_x = actor.position_x.as_f64();
                let minimum_x = princesses.iter().fold(f64::INFINITY, |minimum, &index| {
                    minimum.min((self.entities[index].position_x.as_f64() - actor_x).abs())
                });
                candidates = princesses
                    .into_iter()
                    .filter(|&index| {
                        (self.entities[index].position_x.as_f64() - actor_x).abs()
                            <= minimum_x + 1e-8
                    })
                    .collect();
            }
        }
        self.direct_select_first_nearest(actor_index, &candidates)
    }

    fn direct_select_first_nearest(
        &self,
        actor_index: usize,
        candidates: &[usize],
    ) -> Option<usize> {
        let mut selected = *candidates.first()?;
        let mut minimum = self.direct_target_distance(actor_index, selected);
        for &candidate in &candidates[1..] {
            let distance = self.direct_target_distance(actor_index, candidate);
            if distance < minimum {
                selected = candidate;
                minimum = distance;
            }
        }
        if !self.direct_is_native_building_target(selected) {
            return Some(selected);
        }
        let direction = if self.entities[actor_index].player_id == 0 {
            1.0
        } else {
            -1.0
        };
        candidates
            .iter()
            .copied()
            .filter(|&candidate| {
                self.direct_is_native_building_target(candidate)
                    && self.direct_target_distance(actor_index, candidate) <= minimum + 1e-6
            })
            .min_by(|&left, &right| {
                let left_entity = &self.entities[left];
                let right_entity = &self.entities[right];
                let left_key = (
                    direction * (left_entity.position_x.as_f64() - 9.0),
                    direction * (left_entity.position_y.as_f64() - 16.0),
                    left_entity.id,
                );
                let right_key = (
                    direction * (right_entity.position_x.as_f64() - 9.0),
                    direction * (right_entity.position_y.as_f64() - 16.0),
                    right_entity.id,
                );
                left_key
                    .0
                    .total_cmp(&right_key.0)
                    .then(left_key.1.total_cmp(&right_key.1))
                    .then(left_key.2.cmp(&right_key.2))
            })
    }
}

#[pymodule]
fn _clasher_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(noop_ticks, module)?)?;
    module.add_function(wrap_pyfunction!(consume_state_bytes, module)?)?;
    module.add_function(wrap_pyfunction!(standard_grid_route, module)?)?;
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
