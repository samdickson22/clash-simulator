# Imitation design: open questions the repo cannot answer

1. **Live account's deck and arena.** S122 v2 weights all corpus cards equally. The cards that matter most live are
   the ones the throwaway account actually holds, and nobody knows them until L3 runs. Default until then: no
   re-weighting; per-arena slices in gate (a) make the early-arena cards visible.
2. **Placement precision of the official client.** Every IL_Replay placement is a tile centre (or a Tesla corner).
   The repo can't tell whether the game or the dataset quantizes positions. This matters only if L3 shows real
   placements off the tile lattice. If it does, a finer head needs a different data source; IL_Replay can't supply
   it. Check from official-client screen captures during L3.
3. **GPU split with live-loop v4 T6/T7.** The design takes 127x04 and 127x08 for imitation and leaves 127x01's GPU
   for perception once T1 Phase A data is ready. The coordinator owns that schedule.
