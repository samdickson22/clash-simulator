# K4S run r1, round r4: receipt erratum

- **Recorded:** 2026-10-12T14:06:14Z (`date -u`).
- **Correction:** `rounds/r4/RECEIPT.json` (`8aec45fa…`) `disclosures[0]` reads "drivers verified dead (0 live members) at 13:48:2xZ". That time is a text-edit slip. The read ran right after the "03/04 quiet" post (13:48:10Z) and its command ended at **2026-10-12T13:48:24Z**, the `date -u` in its output. The read found 03 PGID 2573704 and 04 PGID 1596026 with 0 live members each.
- **Not persisted:** the output of that read was not saved as an evidence file. No other field changes.
