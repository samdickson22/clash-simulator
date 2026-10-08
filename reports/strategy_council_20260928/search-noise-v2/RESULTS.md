# S1 results

All 4,992 preregistered games completed. Primary E4 minus B at N64: -3.9 pp [-9.8, +2.0]. Primary test: FAIL.

Recommended event gate: 95/95 provisional; further decision work required.

95% intervals use 10,000 paired-matchup bootstrap resamples, retaining both seats. All eligible games are included. The 94 original 04 receipts completed at or after the incident cutoff were preserved and replayed under the coordinator-authorized technical recovery; no outcome-based exclusion occurred.

| Script cell | Games | Score and 95% CI |
| --- | ---: | --- |
| A | 256 | 95.7% [92.6, 98.4] |
| B-N64 | 256 | 59.4% [52.0, 66.8] |
| B-N90 | 256 | 62.9% [55.9, 69.9] |
| B-N97 | 256 | 64.5% [57.4, 71.1] |
| E1-N64 | 256 | 51.2% [44.1, 58.6] |
| E1-N90 | 256 | 55.1% [47.7, 62.5] |
| E1-N97 | 256 | 64.8% [57.4, 72.3] |
| E4-N64 | 256 | 55.5% [48.4, 62.5] |
| E4-N90 | 256 | 58.2% [50.8, 65.6] |
| E4-N97 | 256 | 64.1% [57.0, 71.1] |
| E4R-N64 | 256 | 52.3% [45.3, 59.4] |
| E4R-N90 | 256 | 62.5% [55.5, 69.5] |
| E4R-N97 | 256 | 59.4% [52.0, 66.4] |
| E4-N90-old | 256 | 55.5% [48.8, 62.5] |
| E4-N90-l2 | 256 | 54.7% [47.7, 61.7] |
| E4-N90-fail10 | 256 | 62.1% [54.7, 69.9] |
| E4-N90-fail60 | 256 | 54.7% [47.3, 62.1] |
| E4-N90-identity | 256 | 57.4% [50.0, 64.8] |

| Against clean A | Games | Score and 95% CI |
| --- | ---: | --- |
| B-N64 | 128 | 40.6% [34.4, 46.9] |
| E4-N64 | 128 | 25.0% [18.8, 31.2] |
| E4R-N64 | 128 | 25.8% [19.5, 32.0] |

N90 E4 minus clean: -37.5 pp [-44.9, -30.1]. N97: -31.6 pp [-38.3, -25.0].

| Hog 2.6 script cell | Score and descriptive 95% CI |
| --- | --- |
| A | 95.0% [87.5, 100.0] |
| B-N64 | 32.5% [15.0, 50.0] |
| B-N90 | 35.0% [17.5, 55.0] |
| B-N97 | 37.5% [22.5, 52.5] |
| E1-N64 | 17.5% [7.5, 27.5] |
| E1-N90 | 22.5% [10.0, 37.5] |
| E1-N97 | 35.0% [20.0, 50.0] |
| E4-N64 | 32.5% [20.0, 47.5] |
| E4-N90 | 37.5% [22.5, 52.5] |
| E4-N97 | 52.5% [35.0, 72.5] |
| E4R-N64 | 35.0% [22.5, 50.0] |
| E4R-N90 | 35.0% [20.0, 50.0] |
| E4R-N97 | 45.0% [27.5, 65.0] |
| E4-N90-old | 30.0% [15.0, 45.0] |
| E4-N90-l2 | 32.5% [20.0, 47.5] |
| E4-N90-fail10 | 32.5% [15.0, 52.5] |
| E4-N90-fail60 | 27.5% [12.5, 42.5] |
| E4-N90-identity | 30.0% [15.0, 47.5] |

Game compute: 191.20 core-hours. Confirmation elapsed: 2.09 hours. Successful worker CPU including initialization: 168.98 core-hours. Preconfirmation Linux tests and pilots: 0.72 core-hours. Node-supervisor warmup and unmetered Mac calibration are additional.

The qualified r2 build is 13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309, including the Electro Spirit and Inferno Dragon dash-channel fixes. The hub parity qualification is not full Stage 6 admission or live-client certification. See PREREG.md and PREREG-r2b-DEVIATION.md.
The fixed total rollout budget reduces candidate coverage as root count rises. ELT uses the legacy point-identity event adapter, a fixed age estimate and validation-calibrated existence probabilities. Own action verification is an idealized next-tick public HUD cue. See PREREG.md for these predeclared assumptions and the reused target-latency cell.

Manifest: 3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677. Receipt aggregate: eae8f7fae0bd3e5cdb46fd8f4fa02ac8b4a7cc0ff9a34d029829a3bd006264be.
Detailed family, noise, derived-state and compute data are in result.json. Raw receipts remain on the fleet hub.

Operational host migration and quarantine audit: operations/migration-split-r2b.json, operations/migration-proof-r2b.json, operations/quarantine-r2e.json. Original generated report retained in operations/RESULTS-generated-r2e.md.

## Recovery and complete-only audit

All 468 sealed hashes and manifest matched on 01, 04 and 08 (1,404 file checks). Original 04 receipts: 541 admitted before 01:39:00Z, 94 preserved and replayed at or after the cutoff. Original 08 receipts: all identity-valid copies admitted, zero excluded. Each of the 4,992 scheduled games contributes one eligible receipt. All 248 partitions completed successfully. Attempts: 04 originals r2e; migrations on 04/08 r2f; collector r2e. Original 04 r2 failures remain preserved.

Eligible game CPU: 191.19578643 core-hours. Excluded original 04 game CPU: 3.59085004 core-hours (additional to eligible game CPU). Total observed worker CPU across failed and successful attempts: 195.14090850 core-hours, including 26.16090221 in the preserved failed 04 attempt. This total already includes eligible and excluded game work; these quantities must not be added together. The five original/recovery/migration supervisors and their workers together recorded 195.18457222 core-hours; the difference, 0.04366372 core-hours, is supervisor initialization/control overhead. R2 preflight CPU: 0.71883889 core-hours. Unknown 07 work and unmetered Mac work remain additional. Completion/quarantine and per-cell decision-timing summaries: operations/completion-audit-r2e.json.
