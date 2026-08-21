# Document System

Use a small set of artifacts with distinct authority. Do not duplicate full instructions across them.

## Artifact roles

| Artifact | Owns | Must not own |
|---|---|---|
| Master plan | Goal, scope, task table, dependency gates, global constraints | Detailed implementation steps for every task |
| Task index | Fast lookup from task to owner, branch/workspace, and brief | Scope decisions or competing dependency rules |
| Execution runbook | Start, review, commit, synchronize, merge, recovery, and stop procedures | Product requirements or subsystem design |
| Responsibility matrix | One owner per deliverable, supporting specialties, responsibility boundaries | Task status or Git commands |
| Handoff snapshot | Current verified state, decisions, blockers, next entry, evidence boundaries | A second master plan or stale investigation instructions |
| Task brief | Self-contained instructions and acceptance criteria for one task | Other tasks' implementation details |

## Relationship model

```text
Architecture and repository facts
        |
        v
Master plan ----> Responsibility matrix
    |                    |
    v                    v
Task index --------> Task briefs
    |                    |
    +------> Execution runbook
                         |
                         v
                  Verified handoff
```

The master plan defines why and in what order. The index answers where to start. The runbook defines how work moves through Git and review. The matrix defines who owns what. A task brief defines one execution unit. The handoff records what is true now.

## Consistency invariants

- Every task ID appears identically in the plan, index, matrix, brief, and runbook mapping.
- Every task has exactly one implementation owner.
- Every dependency points to an earlier merge gate or an explicitly parallel task.
- Every new public contract is published before its consumers implement against it.
- Every task brief can be executed from a fresh conversation after reading only declared prerequisites.
- Status and evidence live in the task brief or handoff, not in the navigation index.
- Historical handoffs are marked archived when their blockers are resolved; they never override current execution records.
- Commit and merge identifiers are recorded only after they exist. Do not prefill them.

## Change propagation

When scope changes:

1. Update the authoritative plan or contract decision.
2. Recompute dependencies and owners.
3. Update affected task briefs.
4. Update index and runbook mappings.
5. Refresh the handoff entry and archive superseded statements.
6. Run a link, identifier, and contradiction audit.
