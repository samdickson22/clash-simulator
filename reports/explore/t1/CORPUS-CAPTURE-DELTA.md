# Corpus capture B-B1 / B-C1 response

Isolated candidate; not admitted to the reporting freeze. The reporting runner remains the reviewed frozen bytes.

B-B1: the excluded-game capture previously called `cached.propose()` after `WINDOW` closed, which raised its live inference guard for K0c/S. The capture now calls `corpus_capture.capture_row()`, whose cache accessor checks same D1 object and exact mask and copies the already-populated proposals. It performs no forward, does not increment proposal counters and retains `CachedPolicy.propose()` and its live inference guard unchanged. Uncached K2/K4 keep an empty proposal list. The capture construction remains after the honest timer, reconstructs all eligible states including timed-out roots from independent pre-decision RNG/posterior copies, and retains physical info separately from the reserved packet.

B-C1: a capture-path test drives the function invoked by run.py for all four tiers using the real WINDOW and CachedPolicy with synthetic public core/root inputs. Every emitted row passes unmodified E4 corpus_contract.validate_row. It confirms physical/reserved separation, suspended-work disclosure, unchanged capture RNG snapshots and zero cache counters. CachedPolicy.propose outside WINDOW still raises. A builder test selects1200 synthetic test rows, verifies all1200 calls to E4 validation and verifies the published capture receipt against the selected sets. Synthetic test fixtures are never production corpora.

corpus.main now validates every selected row before writing that tier's state file and validates corpora.json against the selected own-tier IDs and rows. The published E4 validator is reused unmodified.

Validation: six corpus tests pass on01 in a separate unit-only namespace using nice19/physicalcore63, with no game or timing run. No04/03/08/Mac access. Qualification/reporting0/SEALED remained intact while the08 source extension awaited independent review. Existing quotas, bins and committed-posterior replay tests remain covered. Production capture and state construction still require review admission and an exclusive non-reporting window.

## FROZEN reporting isolation after merge

Admit reviewed a51ea64c/ee9c603b to main only after the sealed replacement dispatch launch7e0a172c. Existing reporting jobs retain the immutable aeeb3003 source/manifest and are never refreshed from main. These merged files are for corpus preparation and future release tooling. The32 qualification-class03 games were captured with a51ea64c in a separate nice19 runtime; all1200 selected rows passed the strict committed E4 contract. Their receipts record capture-code SHAs and the metadata-only loader-bootstrap SHA. Corpus bytes stay on05/03 disk; public Git contains inventories and small receipts only.
