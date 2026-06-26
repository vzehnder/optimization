# BESS-REACT-006: Migrate Manual Run Lifecycle

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

53 through 56

## What to build

Migrate manual execution and run monitoring to React. An analyst can launch a
run from an immutable scenario version, navigate immediately to its run view,
observe queued and running transitions, and inspect terminal success or failure
context without refreshing manually.

The slice must preserve asynchronous Julia execution, immutable run lineage,
captured logs, and existing run state semantics.

## Acceptance criteria

- [x] An analyst can launch one manual run from an eligible scenario version.
- [x] Launch returns promptly and navigates to the created run without waiting
      for Julia completion.
- [x] Duplicate-click protection avoids accidental duplicate runs.
- [x] The run view displays lineage, creation/start/finish timestamps, duration,
      process exit status when available, and current state.
- [x] Queued and running runs poll at a bounded interval.
- [x] Polling stops after `succeeded` or `failed`, on navigation away, and when
      the browser request is cancelled.
- [x] Temporary polling failures use bounded retry and visible recovery behavior.
- [x] Failed runs expose structured error, stdout, and stderr safely.
- [x] Refreshing or directly opening a run restores the correct state.
- [x] A run remains bound to the exact immutable version that launched it.
- [x] Client users cannot launch or inspect internal runs.
- [x] Browser acceptance covers a run progressing to success and a run
      progressing to failure.
- [x] Existing manual run, queue, persistence, and authorization tests remain
      green.

## Blocked by

- BESS-REACT-005
