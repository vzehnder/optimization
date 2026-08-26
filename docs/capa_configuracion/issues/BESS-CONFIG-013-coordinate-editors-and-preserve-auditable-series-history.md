# BESS-CONFIG-013: Coordinate Editors And Preserve Auditable Series History

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/capa_configuracion/architecture_configuration_layer_final.md`

## What to build

Make collaborative editing safe for every configured group. An operator
acquires all copy leases needed by the group, keeps them alive while editing,
and saves or undoes only while holding them. Other users keep read access and
see who is editing. Optimistic concurrency remains the integrity guard even
when a lease expires or is released, and internal users can restore an older
revision without rewriting history.

## Acceptance criteria

- [x] Acquiring a group lease succeeds for every copy touched by the group or for none of them.
- [x] Lease acquisition returns an opaque token and records holder, heartbeat and expiry without exposing copy ids externally.
- [x] The holder can heartbeat and release; expiry makes the group acquirable by another user.
- [x] A non-holder can read values but cannot save or undo and sees the editing user's public identity.
- [x] An administrator can force-release a stuck lease from the internal console surface.
- [x] `If-Match` rejects an outdated values snapshot even when the caller currently holds the lease, preventing last-write-wins.
- [x] The operator can undo only their latest accepted save and only while that revision remains current.
- [x] Undo creates new revisions for every affected copy and refreshes dependencies atomically.
- [x] Internal restore can choose an older revision and materializes it as a new auditable revision rather than rewriting history.
- [x] Reduced operator history shows actor, date, range, cell count, note and comparison without hashes or technical ids.
- [x] Concurrent-user and transaction tests cover lease contention, partial acquisition failure, heartbeat, expiry, stale ETag, undo eligibility and restore.

## Implementation notes

- Group acquisition uses one opaque token and a conditional database upsert for
  every origin touched by the configured group. SQLite connection contexts and
  explicit PostgreSQL transactions keep acquisition, heartbeat, release, save,
  multi-copy undo and restore atomic.
- Every accepted save, undo and internal restore appends revision metadata with
  an operation id and cell comparisons. The public history groups multi-copy
  revisions into one operator action and omits hashes, copy ids, set ids,
  signals and period indexes; the internal view retains the revision timeline
  needed for recovery.
- The React operator table heartbeats while editing, refreshes its history after
  save or undo and offers undo only for the holder's current latest save. The
  internal console shows live holders, admin-only force release and append-only
  restore actions for older revisions.

## Blocked by

- [BESS-CONFIG-011: Paste And Save Multi-Set Groups Atomically](BESS-CONFIG-011-paste-and-save-multi-set-groups-atomically.md)
