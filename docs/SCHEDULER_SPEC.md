# Scheduler spec

Deterministic and stateless except for skips. Implemented in Swift (app + widget). A Python reference implementation drives the dashboard's schedule preview. Parity tests run in CI.

## Slots and plan
- Slots: 07:00, 10:00, 13:00, 16:00, 19:00, 21:30. The "calm" pace uses 3 of them.
- `day` = calendar days since 2024-01-01, computed with `Calendar.current.startOfDay`. Test DST and time-zone changes.
- Kind for a slot = `plan[slotIndex][day % 3]`. The plan matches the time of day: actions and intentions in the morning, facts and models during the day, gratitude and review in the evening.

## Item selection
- Do NOT index by `globalSlot mod n`. That only reaches n / gcd(step, n) items.
- Let `k` = the number of times this kind has occurred before this slot. The plan is periodic, so `k` has a closed form.
- `cycle = k / n`, `idx = k % n`.
- `item = shuffle(pool(kind), seed(kind, cycle))[idx]`.
- The seed uses kind and cycle only, never phase.
- Boundary rule: if the first item of cycle c+1 equals the last item of cycle c, swap it with the next one.
- PRNG: mulberry32. Seed hash: FNV-1a 32-bit. Shuffle: Fisher–Yates. Use identical integer math in every language.

## State
- Skip is the only state: `slotId → skipOffset`, capped at 2, stored in the App Group.
- Resurfacing: the 19:00 slot shows a saved favorite every 2nd day.

## Open questions (decide in Phase 4, before coding)
1. **The plan table.** Which kind goes in which slot for each value of day % 3? This is a product decision, and I design it.
2. **Calm pace.** Which 3 slots does it use? k counts occurrences over the active slot set, so switching pace shifts the sequence. Is that acceptable?
3. **Kinds filter.** If a user disables a kind in the widget config, what fills that kind's slot?
4. **Skip target.** Which item does a skip show? It must not pull an item that's scheduled later in the same cycle.
5. **Resurfacing pick.** Which favorite resurfaces? It must be deterministic, e.g. favorites sorted by saved date, indexed by resurfacing occurrence. With zero favorites, show a normal item.
6. **Content pack updates.** When a new pack changes a pool size n, the shuffle changes. Proposal: stable item IDs, and a pool change only takes effect at the next cycle boundary. Favorites store an item snapshot, so they survive item removal.

## Property tests
- Every item appears exactly once per cycle.
- Output is deterministic for the same inputs.
- No repeat across a cycle boundary.
- Python and Swift produce identical output.
