# AI Field Filler — Constitution

The durable engineering principles for this addon. This is the **why**; the mechanics live
in `.claude/rules/python.md` and `.claude/rules/git-conventions.md`, and the enforcement
lives in `pyproject.toml` (ruff/mypy) and CI. On any conflict between a principle here and a
habit, convention, or default, **this document wins** — and a genuinely warranted deviation
must be called out and justified in writing at the point of deviation, never done silently.

## I. Pure-Python, minimal, boring dependencies

An `.ankiaddon` ships source, not wheels — it cannot bundle compiled code. Every dependency
must be pure-Python **and** earn its place. Do not add a library when the standard library or
an existing dependency already covers the need. This is why unified-LLM SDKs were rejected
(see `PITFALLS.md`); the HTTP layer is hand-rolled in `providers/http.py` on purpose.

## II. Python 3.9 is the floor

The addon runs on Anki's bundled interpreter and CI covers 3.9/3.12/3.13. No 3.10+ syntax:
no `match`, no runtime-evaluated `X | Y` unions (use `Optional`/`Union`). Ruff's
`target-version` and the `FA`/`UP` rules enforce this — do not raise the floor to dodge a
lint finding.

## III. Capability is negotiated at runtime, never assumed from a model id

Providers add and retire models faster than any hard-coded list can track. Detect each quirk
from the API's own error, act on it, and cache it per model id for the session
(`_MODEL_QUIRKS`). Treat `/models` endpoints as catalogues, not capability manifests. Every
new quirk found by testing an API is recorded in `PITFALLS.md` in the same change.

## IV. Fail fast, and fail legibly

Raise on broken invariants rather than limping on; catch narrowly, only where you can
genuinely recover. Every provider failure surfaces as a `ProviderError` whose message tells
the user what to do (e.g. "pick a current model") — never a raw JSON body or a bare stack
trace. A plausible-but-wrong result is worse than an honest error.

## V. Tests pin behavior; a failing test is a breached contract

Code ships with unit tests that fix its intended behavior. When a test fails, realign the
code to it — never weaken, rewrite, or delete the test to make it pass without explicit human
sign-off. The suite mocks the network and never requires a real API key. Definition of done
is the full gate green: `ruff format`, `ruff check`, `mypy`, `pytest`.

## VI. One way to do a thing

No second path to the same capability. HTTP goes through `providers/http.py`; field types
come from `FIELD_TYPES`; a provider's base URL is `ProviderConfig.base_url`; shared widgets
come from the `ui/` helpers. Prefer an existing helper or a stdlib primitive over a new one.
Ruff's `TID251` bans `urllib.request` outside the sanctioned HTTP layer so this cannot drift.

## VII. Config has one home per role

`config.json` is the defaults shipped with the addon. The user's live config is Anki-managed
in `meta.json` and never committed. Secrets and API keys live only in `meta.json`, never in
the repo, a header, or a log.

## VIII. The repo is not the addon

Code lives in `src/ai_field_filler/`; the built `.ankiaddon` is its contents, nothing more.
Tests, tooling, docs, and demo assets never ship. Anki loads the package via a symlink into
`addons21/`, so the package is developed like any normal project.
