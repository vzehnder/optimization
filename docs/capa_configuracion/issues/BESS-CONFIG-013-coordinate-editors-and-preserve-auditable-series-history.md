# BESS-CONFIG-013: Coordinate Editors And Preserve Auditable Series History

Status: Todo
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

- [ ] Acquiring a group lease succeeds for every copy touched by the group or for none of them.
- [ ] Lease acquisition returns an opaque token and records holder, heartbeat and expiry without exposing copy ids externally.
- [ ] The holder can heartbeat and release; expiry makes the group acquirable by another user.
- [ ] A non-holder can read values but cannot save or undo and sees the editing user's public identity.
- [ ] An administrator can force-release a stuck lease from the internal console surface.
- [ ] `If-Match` rejects an outdated values snapshot even when the caller currently holds the lease, preventing last-write-wins.
- [ ] The operator can undo only their latest accepted save and only while that revision remains current.
- [ ] Undo creates new revisions for every affected copy and refreshes dependencies atomically.
- [ ] Internal restore can choose an older revision and materializes it as a new auditable revision rather than rewriting history.
- [ ] Reduced operator history shows actor, date, range, cell count, note and comparison without hashes or technical ids.
- [ ] Concurrent-user and transaction tests cover lease contention, partial acquisition failure, heartbeat, expiry, stale ETag, undo eligibility and restore.

## Blocked by

- [BESS-CONFIG-011: Paste And Save Multi-Set Groups Atomically](BESS-CONFIG-011-paste-and-save-multi-set-groups-atomically.md)
