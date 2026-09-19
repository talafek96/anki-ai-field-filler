---
description: End-of-session wind-down. Runs reconcile-docs → next-steps decomposition (PLAN-ONLY) → shift-handoff, in that fixed order, so the next session can resume correctly with zero re-derivation. Reconciles the living docs to reality, defines the next session's steps as a persisted plan (without executing anything), then writes the next-agent handoff prompt.
argument-hint: [optional: notes/focus for the next session, e.g. "next: finish the carry-cost model"]
---

You are ending a work session. This command runs the wind-down ritual as a **fixed, ordered sequence** whose single goal is to leave the project in a state where the next session — human or agent — resumes correctly **without re-deriving anything from this conversation** (which will not exist next session).

It answers three questions, in order. Do not reorder them; each step depends on the previous one's output:

1. **Where are we now?** → `reconcile-docs` (make the on-disk docs equal reality)
2. **Where do we go next?** → next-steps decomposition, **plan-only**
3. **How does the next agent pick this up?** → `shift-handoff` (write the resume prompt)

**Optional notes for the next session:** $ARGUMENTS

---

## Preflight — is a wind-down even warranted?

Honestly check: did this session move **durable project state** (decisions made, code/config changed, state advanced, something to reconcile)? If it was trivial or throwaway (a quick question, a one-line fix, nothing a future reader needs), **stop and tell the user the wind-down isn't needed** — running it would write empty ceremony into the docs. Otherwise proceed.

## Step 1 — `reconcile-docs` (capture reality first)

Invoke the **reconcile-docs** skill. Bring `HANDOFF.md`, `PITFALLS.md` (and any `docs/` or `specs/` the session touched or invalidated) into **full agreement with the current system state**. The bar is the skill's read-through contract: an operator reading each document top to bottom, executing as they go, lands in the correct final state having hit **zero contradictions** — so resolve stale/contradicting passages at the source, don't just append.

This runs **first** on purpose: steps 2 and 3 must build on accurate docs, not stale ones.

## Step 2 — Next steps, PLAN-ONLY (define, do NOT execute)

Define the **next** session's work as a persisted plan:

- Slice the remaining / next work into **ordered, independently-verifiable sub-tasks**, each with a named done-check or oracle — a build tree with gating checks, not a vague to-do list.
- Fold in anything from **$ARGUMENTS** above.
- **Persist the plan where the next session will find it.** If the work belongs to an active spec-kit feature, that is the feature's `specs/<feature>/tasks.md`. Otherwise, a clearly-marked **"Next steps"** section in `HANDOFF.md`.

**HARD GUARD — this is session close, not a launch.** Do **NOT** begin execution, do **NOT** dispatch subagents, do **NOT** start any long-horizon/unattended/"keep going overnight" run. You are *writing the plan the next session will execute*, not executing it. The deliverable is the persisted, dependency-ordered next-steps plan, full stop.

## Step 3 — `shift-handoff` (write the resume prompt last)

Invoke the **shift-handoff** skill to produce the warm compaction prompt for the next agent. Because it runs last, it can — and must — point at both prior outputs:

- "The on-disk docs (`HANDOFF.md` / `PITFALLS.md`) are **current as of this session** — read them first."
- "The **next steps** are defined in [`specs/<feature>/tasks.md` / `HANDOFF.md`] — start there."

**Boundary note (intended, not duplication):** `reconcile-docs` makes the *file* `HANDOFF.md` correct for a **human operator**; `shift-handoff` writes a *chat prompt* for the **next agent**. Different artifacts, different consumers — both are wanted.

## Close

End with a tight state-check: what was reconciled (which docs, which contradictions resolved), where the next-steps plan now lives, and confirmation the handoff prompt is ready. Then it's safe to take the break.
