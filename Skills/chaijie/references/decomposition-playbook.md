# Decomposition Playbook

## 1. Find the real work

Trace the desired user journey or system event from entry to terminal evidence. At each hop, classify the state as implemented, synthetic-only, disconnected, contract-mismatched, operationally blocked, or unverified. Convert gaps into change fronts.

Do not create tasks directly from UI labels or component folders. A visible failure may require an earlier contract or runtime task; a configured integration may still lack execution connectivity.

## 2. Choose task boundaries

A good task has:

- one primary owner;
- one coherent behavior change;
- a bounded set of owned modules;
- prerequisites already mergeable;
- independent acceptance evidence;
- a useful handoff even if later work stops.

Split a task when it combines two sources of truth, requires unrelated specialties to implement, crosses an irreversible decision, or cannot be verified without unfinished downstream work.

Do not split when two edits must be atomic to preserve one invariant, or when separation would create a temporary public contract with no valid implementation.

## 3. Order by uncertainty and dependency

Use this default sequence, omitting layers that do not apply:

1. Discovery and architecture decisions.
2. Shared contracts and compatibility.
3. Data ownership, migrations, and transactional effects.
4. External adapters and provider semantics.
5. Application workflow consumers.
6. Runtime composition, secrets, and network policy.
7. Cross-service synthetic verification.
8. Explicitly authorized real-world smoke and release gate.

Place costly, secret-bearing, public, or destructive validation behind all synthetic and static gates.

## 4. Select agents by responsibility

Inspect the available agent catalog; do not invent roles. Assign the role whose core responsibility owns the deliverable, not the most senior-sounding role.

If no catalog or ownership map is available, use `required capability: <capability>` and `assignment: unresolved`. Do not turn a capability label into a claimed agent identity.

Add a supporting role only if it contributes a distinct decision or validation surface, such as:

- contract compatibility;
- database migration/recovery;
- security trust boundaries;
- provider/model semantics;
- media correctness;
- user workflow/accessibility;
- infrastructure lifecycle;
- independent test evidence.

Do not add agents for ceremony. Avoid multiple implementation owners. State what each supporting role reviews and prohibit it from silently changing another owner's source of truth.

After drafting the graph, attempt to merge adjacent tasks. Keep them separate only when they have different sources of truth, owners, merge gates, risk approvals, or independently useful verification. The number of tasks is an outcome of the boundaries, not a target.

## 5. Define gates

For each gate, state:

- required merged predecessors;
- entry checks for workspace, branch, and cleanliness;
- required artifacts and tests;
- stop conditions;
- human approvals;
- post-merge verification.

Parallel tasks may proceed only when their dependencies are merged, their write scopes do not collide, and neither publishes a contract consumed by the other.

## 6. Make failure resumable

Require each task to record:

```text
roles_used
scope_completed
files_changed
contracts_changed
verification_and_results
known_risks
next_owner
```

Record failures and skipped checks honestly. Preserve opaque external task references when safe continuation is possible. Never turn a local timeout into an upstream failure without evidence.

## 7. Final audit checklist

- Does the task graph cover the full outcome and all failure recovery?
- Can each task be reviewed and reverted independently?
- Are public contracts ahead of implementations and tests behind them?
- Is any task hiding a broad refactor or cross-owner mutation?
- Are secret, cost, data, deployment, and destructive gates explicit?
- Can a fresh agent locate its task, prerequisites, commands, and next handoff without prior chat?
- Do all artifacts agree on IDs, dependencies, owners, and status?
