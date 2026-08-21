# Generic Templates

Adapt headings and terminology to the repository. Replace placeholders with discovered facts; never leave examples as asserted truth.

## Master plan

```markdown
# <Wave or objective>

Architecture basis: <link>
Execution entry: <link>
Runbook: <link>
Responsibility matrix: <link>

## Outcome and boundaries
<User-visible outcome, evidence, non-goals, global constraints>

| Task | Deliverable | Owner | Dependencies |
|---|---|---|---|
| ... | ... | ... | ... |

## Gates
1. <Merged prerequisites and parallel rules>

## Global stop conditions
<Secrets, cost, data, production, destructive actions, contract drift>
```

## Task index

```markdown
| Task | Workspace/branch | Owner | Brief | Status source |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

Start message: <minimal prompt that points to the task brief and prerequisites>
```

## Task brief

```markdown
# <Task and deliverable>

Status: <blocked/ready/in progress/reviewed>

## Entry
<Workspace, branch, merged prerequisites, documents to read>

## Ownership
<One primary owner; scoped supporting roles and reasons>

## Scope
<Behavior and interfaces>

Allowed changes: <owned boundaries>
Forbidden: <cross-owner, secret, destructive, or out-of-scope actions>

## Acceptance
<Tests, runtime evidence, negative cases, security and recovery>

## Review and Git
<Record, human review, commit, synchronize, merge, post-merge checks>

## Execution record
<Structured handoff fields>
```

## Execution runbook

```markdown
1. Verify workspace, branch, cleanliness, and merged prerequisites.
2. Read the task brief and required architecture/contract sources.
3. Invoke only assigned roles and record their conclusions.
4. Implement within allowed boundaries; run narrow then broad checks.
5. Append the structured execution record and wait for human review.
6. After approval: commit only task files, synchronize the latest base, resolve or stop on conflicts, rerun checks, merge, and verify the merged branch.
7. Stop on missing gates, destructive actions, secrets, paid calls, production changes, required skips, or unexplained contract drift.
```

## Responsibility matrix

```markdown
| Deliverable | Primary owner | Supporting roles | Boundary |
|---|---|---|---|
| ... | ... | ... | <Who implements; what each reviewer validates> |
```

## Handoff snapshot

```markdown
# <Objective> handoff

Status and verified baseline: <facts only>

## Goal
<End-to-end outcome>

## Decisions
<Locked product and architecture choices>

## Completed and not completed
<Evidence boundaries; synthetic versus real>

## Risks and blockers
<Actionable, current items>

## Next entry
<Exact task brief to open and prerequisites to verify>

## Safety
<Secrets, cost, data, deployment, and destructive restrictions>
```
