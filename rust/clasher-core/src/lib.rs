use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde_json::Value;
use sha2::{Digest, Sha256};

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
    if schema_version != 1 {
        return Err(PyValueError::new_err(format!(
            "unsupported battle checkpoint schema {schema_version}; expected 1"
        )));
    }
    Ok(schema_version)
}

/// Long-lived native battle allocation.
///
/// Initialization and explicit checkpoint replacement may cross the FFI as a
/// complete canonical payload. Ordinary phase/tick methods mutate the fields
/// below directly and never serialize or reparse that payload.
#[pyclass(module = "_clasher_rust")]
struct ResidentBattle {
    checkpoint: Vec<u8>,
    checkpoint_sha256: String,
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
        triple_elixir_start_time
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
    ) -> PyResult<Self> {
        if !time.is_finite() || !dt.is_finite() || dt < 0.0 {
            return Err(PyValueError::new_err(
                "battle time and non-negative dt must be finite",
            ));
        }
        let schema_version = validate_checkpoint(checkpoint)?;
        Ok(Self {
            checkpoint: checkpoint.to_vec(),
            checkpoint_sha256: sha256_hex(checkpoint),
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
        })
    }

    /// Advance only the resident clock/timer phase of one native logic tick.
    /// Later milestones will append the remaining phases before complete-tick
    /// capability can be enabled.
    fn advance_clock_phase(&mut self) -> bool {
        if self.game_over {
            return false;
        }
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

    fn checkpoint_bytes(&self) -> Vec<u8> {
        self.checkpoint.clone()
    }

    fn checkpoint_sha256(&self) -> &str {
        &self.checkpoint_sha256
    }

    fn checkpoint_size(&self) -> usize {
        self.checkpoint.len()
    }

    fn checkpoint_generation(&self) -> u64 {
        self.checkpoint_generation
    }

    fn schema_version(&self) -> u64 {
        self.schema_version
    }

    fn replace_checkpoint(&mut self, checkpoint: &[u8]) -> PyResult<()> {
        let schema_version = validate_checkpoint(checkpoint)?;
        self.checkpoint.clear();
        self.checkpoint.extend_from_slice(checkpoint);
        self.checkpoint_sha256 = sha256_hex(checkpoint);
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
}
