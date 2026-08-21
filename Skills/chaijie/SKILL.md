---
name: chaijie
description: 将大型跨模块目标拆成有依赖关系、可审查、可交接的小任务。
---

# Chaijie

Turn a large objective into an execution system that another agent can resume without hidden context. Derive names, locations, tools, and conventions from the target repository; never copy identifiers from prior projects.

## Core workflow

1. Ground in evidence.
   - Read repository guidance, architecture, current plans, source boundaries, tests, CI, Git state, and existing ownership conventions.
   - Separate discoverable facts from product decisions. Ask only for decisions that materially change scope, cost, data, or architecture.

2. Define the outcome before the tasks.
   - State the user-visible goal, acceptance evidence, non-goals, safety constraints, and review authority.
   - Identify the end-to-end path and every missing connection. Do not equate component existence with working connectivity.

3. Map change fronts and owners.
   - Group work by contract, data ownership, runtime boundary, user workflow, infrastructure, and verification.
   - Give each task one implementation owner. Add supporting roles only when a distinct specialty must review or contribute.
   - Discover owners from repository rules or an available role catalog. If none exists, state the required capability and mark assignment unresolved; never invent a role or agent as if it exists.
   - Keep contract publication ahead of consumers; keep release evidence after all production behavior.

4. Build a dependency graph.
   - Split at stable interfaces and independently verifiable outcomes.
   - Express gates explicitly. Parallelize only tasks that do not depend on unmerged behavior or edit the same source of truth.
   - Move uncertain or irreversible decisions into earlier discovery/contract tasks.
   - Prefer the smallest task set that preserves single ownership and independent verification. Do not create tasks merely to mirror folders, phases, or document headings.

5. Create the document system.
   - Produce a master plan, task navigation index, execution/Git runbook, responsibility matrix, restart-safe handoff, and one self-contained brief per task.
   - Keep each fact in one authoritative artifact and link to it elsewhere. See [document-system.md](references/document-system.md).
   - Use [templates.md](references/templates.md) when generating a new artifact set.

6. Make every task reviewable.
   - Specify prerequisites, allowed paths, forbidden actions, contracts, behavior, verification, stop conditions, handoff fields, and commit/merge policy.
   - Require narrow checks first, then broader checks proportional to blast radius.
   - Never allow skipped required tests, contract drift, secret leakage, or missing evidence to count as success.

7. Preserve the human gate.
   - Default to implement -> verify -> record -> user review -> commit -> synchronize -> merge -> post-merge verify.
   - Do not commit, merge, publish, use paid services, access secrets, or perform destructive actions before the applicable authorization.

8. Audit the plan as a system.
   - Check that every goal maps to at least one task and every task maps to an acceptance criterion.
   - Check dependency completeness, single ownership, path non-overlap, contract ordering, failure recovery, and new-conversation resumability.
   - Resolve contradictions across artifacts before presenting the plan.

For task-sizing heuristics, agent selection, and gate design, read [decomposition-playbook.md](references/decomposition-playbook.md).

## Output behavior

- Adapt the artifact names and placement to the repository's existing conventions.
- Prefer behavior-level task scopes over file inventories; name files only to prevent boundary mistakes.
- Keep the master plan compact and put implementation detail in task briefs.
- Record assumptions and unresolved decisions explicitly. Do not invent APIs, schemas, commands, or agent names.
- If the user asks only for analysis or a plan, do not begin implementation.
- If no repository exists, propose a minimal artifact layout and mark it as a new convention requiring approval.
