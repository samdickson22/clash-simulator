use pyo3::prelude::*;

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

#[pymodule]
fn _clasher_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(noop_ticks, module)?)?;
    module.add_function(wrap_pyfunction!(consume_state_bytes, module)?)?;
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
}
