# Frozen student screen: loader6 operational amendment

Recorded 2026-10-09T20:09:24.994949+00:00 before any reporting outcome. Coordinator directed a five-minute throughput measurement followed by loader6 repair for arms below about6k rows/s.

Six actual CPU loader workers, prefetch4, one scientific loader; no mmap_random_advice. The original frozen trainer, sampler, complete effective batches, human/teacher mixing order, optimizer, schedule, seed, cursor, row count and final EMA selection remain unchanged. Each prefetched step is checked against both original complete index vectors. Loader workers construct CPU batches only. A private DataLoader generator preserves parent training RNG.

Resume only from an exact checkpoint after serial/parallel train-only GPU replay matches the model, EMA, optimizer, scheduler, cursor and all RNG states bit for bit. Reporting seeds remain embargoed. PSS is measured across parent plus loaders; guard46GB, leased cap48GB, process declaration12 (below16), MemAvailable floor24GiB, nice10, unchanged live-lease supervisor. Parent core126; six distinct loader cores120–125. All prior fit and qualification resource segments count in the final report. The binding hashes are in `receipts/student-loader6-amendment.json`.
