# Width-480 allocator ceiling and exact resume

2026-10-09 20:23Z, before any wide-arm dev measurement. Scientific freeze
841c44b0 and all config SHAs remain unchanged. The width-192 quarter result is
already sealed; it does not determine this resource repair.

Width 480's early peak allocated memory was 36,564 MiB, while its cached peak
reserved memory reached 46,082 MiB. That briefly breached the required 8 GiB
GPU reserve between the ten-second guard samples. Boundary empty_cache alone
was insufficient to bound intra-step reservation. The owned trainer434818 was
SIGTERM-checkpointed at step175 / 1,433,600rows and exited0. Its supervisor and
four loader descendants have exited; all artifacts and logs are retained.

Exact resume uses the same own checkpoint, pinned by SHA in
`480-allocator-stop.json`, with unchanged model/EMA/optimizer/scheduler/all RNG
sections, sampler, loss, effective8192batch and microbatch2048. The only GPU
change is torch.cuda.set_per_process_memory_fraction(0.78) for width480: a hard
allocator ceiling that makes PyTorch reclaim unused cached blocks. It leaves
more than8GiB for CUDA context and other permitted GPU use. No new init, recipe,
architecture, hyperparameter or NLL-based decision. Width288/384fits continue.

The lightweight controller and collector now read an active-label pointer and
all per-arm guard segments, so restart accounting includes the original job.
A SHA-pinned operational receipt is committed before the new detached launch.
No extra data transfer or checksum job, no original T11 edit, no scientific kill.
