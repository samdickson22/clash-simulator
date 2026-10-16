//! Narrow optional lattice kernel, built with rustc (no crates/frameworks).
//! NumPy still supplies capped reductions, preserving its pairwise sum order.
//! Ordinary IEEE operations only: no fast-math or fused multiply-add.

/// # Safety
/// Caller supplies nonoverlapping contiguous f64 source/output of length n,
/// and shifts/weights/caps arrays of length count. All shifts are in [-n,n].
#[no_mangle]
pub unsafe extern "C" fn clasher_lattice_mix_v1(
    source: *const f64, output: *mut f64, n: usize,
    shifts: *const i64, weights: *const f64, caps: *const f64, count: usize,
    left: f64, right: f64, decay: f64, uniform: f64,
) {
    let source = std::slice::from_raw_parts(source, n);
    let output = std::slice::from_raw_parts_mut(output, n);
    let shifts = std::slice::from_raw_parts(shifts, count);
    let weights = std::slice::from_raw_parts(weights, count);
    let caps = std::slice::from_raw_parts(caps, count);
    // Accumulate each shifted component in the original order. Inner contiguous
    // loops vectorize, without changing the per-cell addition sequence.
    output.fill(0.0);
    for j in 0..count {
        let shift = shifts[j];
        let weight = weights[j];
        if shift <= -(n as i64)+1 {
            output[0] += weight*caps[j];
        } else if shift >= n as i64-1 {
            output[n-1] += weight*caps[j];
        } else if shift < 0 {
            let k = (-shift) as usize;
            output[0] += weight*caps[j];
            for i in 1..n-k {
                output[i] += weight*source[i+k];
            }
        } else if shift > 0 {
            let k = shift as usize;
            for i in k..n-1 {
                output[i] += weight*source[i-k];
            }
            output[n-1] += weight*caps[j];
        } else {
            for i in 0..n {
                output[i] += weight*source[i];
            }
        }
    }
    for i in 0..n {
        output[i] = decay*(left*source[i]+right*output[i])+uniform;
    }
}
