---
description: Generate a warm, complete compaction prompt for the next agent taking over this session — covers project state, decisions locked, pitfalls, open work, and attitude. Use at the end of a productive session before taking a break.
argument-hint: [optional: specific area to emphasize, e.g. "focus on the auth refactor" or "we stopped mid-migration"]
---

# Compaction Prompt

We've had a great session together and we're wrapping up for now. Your job is to write a **compaction prompt** — a warm, self-contained briefing that the next agent (a fresh session with no memory of today) can paste as their very first message to pick up exactly where we left off.

**Optional emphasis:** $ARGUMENTS

---

## What to gather before writing

Read every one of these before producing a single word of the briefing. Do not skip any that exist:

1. `HANDOFF.md` — handoff notes and in-progress context
2. `PITFALLS.md` — hard-won lessons and known traps
3. `git log --oneline -20` — the last 20 commits (what actually shipped today)
4. Any open TODO/FIXME markers in recently touched files if you can identify them quickly

If none of these files exist, synthesize from the current conversation context instead and note that the memory files are absent.

---

## Required sections in the compaction prompt

Write the compaction prompt as a single cohesive message the next agent pastes verbatim. Structure it with these sections, in order:

### 1. Welcome & project identity (2–4 sentences)

Greet the incoming agent warmly. Name the project, its purpose, and why it matters. Set the tone: collaborative, no tribal knowledge, every assumption explained.

### 2. What we accomplished this session (bullet list)

Concrete, specific. Reference file names, function names, commit messages. Not vague like "made progress on auth" — specific like "extracted `useAuthToken` hook in `src/hooks/auth.ts` and wired it into the login form".

### 3. Current state of the codebase (2–5 sentences + key file map)

Where does the code stand right now? What's working, what's partial, what's intentionally left rough? List the 3–7 most important files/directories the incoming agent will need to touch or understand.

### 4. The open work — next tasks in priority order (numbered list)

What remains? Number them by priority. For each: one sentence of what, one sentence of why it matters, one sentence of where to start (file + line if possible).

### 5. Decisions already locked — do not re-litigate (bullet list)

Choices that were weighed and made. The incoming agent must not re-open these without the human's explicit instruction. For each: the decision + the reason it was made.

### 6. Pitfalls and gotchas (bullet list)

Everything in `PITFALLS.md` plus anything that burned us today. Format: **"The trap:"** what it looks like vs. **"The rule:"** what to do instead.

### 7. Project conventions and attitude (short paragraph)

How does this project work? Key naming conventions, file layout, commit style, push-back policy from `CLAUDE.md`. What attitude does the human want from their agent partner — when to push back vs. when to just execute?

### 8. First action for the incoming agent

One concrete instruction: the exact first thing they should do when they arrive. Not "get oriented" — something like "Run `npm test` to verify the baseline, then open `src/api/auth.ts:142` where the incomplete token refresh logic lives."

---

## Tone requirements

- Warm and collegial — you are briefing a capable colleague, not writing documentation.
- No tribal knowledge withheld. Explain every abbreviation, every convention, every "we always do X because…"
- Honest about what is incomplete or uncertain — false confidence is a trap.
- Concise within each section. Dense, not padded. The incoming agent is smart; they need facts and pointers, not re-explanations of basics.
- End the compaction prompt with a short motivational note: acknowledge the work done, express confidence in the incoming agent, and wish them a productive shift.

---

## Output format

Produce exactly two things:

**First:** A brief note to the human (2–3 sentences) saying what you drew from and any gaps you noticed (e.g. "HANDOFF.md is missing — I synthesized from conversation context").

**Second:** The full compaction prompt, fenced in a markdown code block so it can be copied cleanly. Label it clearly: `# Compaction Prompt — paste this as your first message in the new session`.
