# K4S run r1, round r4: receipt erratum

- **Recorded:** 2026-10-12T14:06:14Z (`date -u`).
- **Correction:** `rounds/r4/RECEIPT.json` (`8aec45fa…`) `disclosures[0]` reads "drivers verified dead (0 live members) at 13:48:2xZ". That time is a text-edit slip. The read ran right after the "03/04 quiet" post (13:48:10Z) and its command ended at **2026-10-12T13:48:24Z**, the `date -u` in its output. The read found 03 PGID 2573704 and 04 PGID 1596026 with 0 live members each.
- **Not persisted:** the output of that read was not saved as an evidence file. No other field changes.
- **Timeout basis (coordinator correction, recorded 2026-10-12T14:06:54Z):** the cut-3 GO's `go_utc` is **2026-10-12T14:01:30Z**. It comes from the GO receipt `/mpac/sdicks02/jobs/clasher/v4-b-gap-review/receipts/supplement-go-receipt-cut3.json` (sha256 `b08b77a4…`), not from the commit time 14:01:29Z that the receipt used. The per-host timeout was therefore **2026-10-12T14:31:30Z**. It was not reached, since both releases were received at 14:03:15Z.
