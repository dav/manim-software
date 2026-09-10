---
name: review
description: Adversarial code review of the current branch from five principal-engineer perspectives — correctness, design, the renderer, clarity, and the library's public face — synthesized by an arbiter, then auto-fix the top findings. Use when asked to review a branch, a diff, or a PR in this repo before it merges.
user-invocable: true
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Grep
  - Glob
---

# Adversarial Code Review Skill

Perform a comprehensive, adversarial code review from five principal engineer
perspectives, synthesized by an arbiter, then auto-fix the top priority findings.

This is `manim_software`, a Manim Community plugin: a Python library of mobjects
and animations for videos that explain how software systems work. Other people
`pip install` it and `from manim_software import *` inside their own scenes, so
every public name is a promise. There is no server, no database and no user
data; what can go wrong is geometry that is subtly off, an animation that
renders differently from how it reads, an API that is awkward to build on, and
behaviour that only shows up in a rendered frame because the tests never render.
Review accordingly.

## Input

Review the current branch diff against its base. Branches here are often stacked,
so the base is `main` or the branch the PR is stacked on: `gh pr view --json
baseRefName -q .baseRefName` says which; if there is no PR, ask.

```sh
git diff $(git merge-base <base> HEAD)...HEAD
```

Also read every changed file in full for context (not just the diff hunks), plus
the test module for each changed source module (`tests/test_<module>.py` or the
nearest one). This repo's tests pin geometry and behaviour without rendering, so
a change with no test movement is itself a finding worth raising. If an example
scene or anything visual changed, render the relevant still and look at it:
`uv run manim -s -qm examples/<file>.py <Scene>` writes a PNG under `tmp/media/images/`
that you can Read.

## Phase 1: Five Independent Reviews

Perform five complete, independent review passes. Each reviewer has a different
lens and MUST find issues — a review that says "looks good" is a failed review.
Be harsh. Be specific. Cite `file:line` for every finding.

### Reviewer 1: "The Paranoid" — Correctness

Focus areas:

- **Geometry**: a proportion outside `[0, 1]`, a zero-length wire (two components
  on top of each other), a route with two identical points, a normal computed
  from a degenerate tangent, `normalize` of a zero vector giving NaN that
  spreads silently through every point after it
- **Empty and single**: an empty participant list, a layer with one node, a
  `LaggedStart` of zero animations, `max()` over an empty sequence, a diagram
  with components but no wires. `max([default] + values)` is the house idiom
- **State on mobjects**: manim deep-copies every mobject for every animation.
  Anything stored on a mobject must survive `copy.deepcopy` and must not be a
  scene, a lock, a file handle or a reference to half the diagram. A method
  that mutates a mobject it was only meant to read is a finding
- **Manim's own API**: `Text.text` drops spaces (`original_text` is the key);
  `Mobject.depth` and `set_depth` already exist (the z-extent); a name exported
  from this package that shadows a manim name breaks `from manim import *`
  users. `tests/test_exports.py` guards some of this; check what it does not
- **Clamping and ordering**: a depth that can go negative or past capacity, an
  inflight count that is never released on the error path, a fraction not
  clipped, a candidate list whose order silently decides the winner
- **Edge cases**: `None` vs empty string labels, a direction vector given as a
  list instead of an array, a reversed connector where `at` needs `1 - at`, a
  colour given as a string where a `ManimColor` is compared with `==`

### Reviewer 2: "The Architect" — Design & the Public API

Focus areas:

- **Layering**: the modules stack `style → icons → components → connectors →
  packets → failures → concurrency → sequence → annotate → three_d → layout`,
  with lower modules never importing higher ones. A helper that reaches
  upward, a circular import hidden behind a function-local import that has no
  reason to be local, or domain knowledge (insurance, a vendor, a product) in
  the general-purpose layer is a finding
- **Naming**: names describe a role, not the first place they happened to be
  used. A class named after the example scene that needed it is wrong the day
  a second scene appears. In general things should be named according to what
  they do, not what they are currently used for when they get added to the code
- **The style contract**: every constructor takes `style=` and resolves it with
  `_resolve_style`; every visual constant comes from `DiagramStyle` through
  `_pick(explicit, style.field)`, never a hardcoded colour. A new hardcoded
  `YELLOW` or `0.28` that a theme swap cannot reach is a finding
- **Animation composition**: new animations subclass `Animation`,
  `AnimationGroup` or `Succession` and compose with `Send`/`Packet` rather than
  re-implementing them; anything that appears mid-animation stays invisible
  until its own `begin` (see the `packets` module docstring)
- **Error handling**: a bare `except`, a `KeyError` where a `ValueError` with the
  allowed values would tell the caller what to do, a silent fallback that hides
  a typo the author would have wanted to know about (the icon placeholder logs a
  warning for exactly this reason)
- **Dead code**: unused private helpers, constants nothing reads, a branch made
  unreachable by an earlier guard, a parameter every caller leaves at its default
- **Abstraction fitness**: over-engineering (an abstraction with one caller) or
  under-engineering (a third copy of the same hide-until-begin preamble). Note
  that abstractions with one caller that add semantics that would be lost
  otherwise are acceptable

### Reviewer 3: "The Renderer" — What Actually Ends Up in the Frame

The tests never render. Ask what this change looks like at frame 37 of a
`LaggedStart`, in a `Succession`, and in the Cairo renderer's optimisations.

Focus areas:

- **Static mobjects**: the Cairo renderer paints every scene mobject that no
  running animation owns once per `play`. An animation that mutates something
  as a side effect (a queue, a counter, a breaker) must include it in its
  `mobject`, or the change will not show until the next `play`
- **Swapped submobjects**: the draw list is flattened when a `play` starts. A
  submobject swapped in mid-play never shows; mutate in place with `become`
- **Removal**: `FadeOut(VGroup(a, b))` on a group made on the spot does not
  remove `a` and `b` that sit in the scene individually, and `FadeOut` restores
  opacity after removing. Fade leaves one by one
- **Begin semantics**: `AnimationGroup` and `LaggedStart` call `begin` on every
  child up front; only `Succession` is lazy. State read in `begin` is the state
  before anything ran. Decisions belong in the first `interpolate` calls
- **Opacity bookkeeping**: `_family_opacities` caches "full" opacities the first
  time it is read. A helper that hides a mobject before the cache is warm caches
  zeros, and the mobject can never be shown again
- **Draw order**: every new mobject sets its `z_index` from the `Z_*` constants;
  a packet under its wire, a label under a container frame, a breaker under
  the wire it sits on
- **3D**: anything in a `SoftwareThreeDScene` that must stay put uses
  `pin(scene)` / `add_fixed_in_frame_mobjects`; Cairo draws flat mobjects over
  3D ones and `DiagramCamera` exists to draw the flat diagram first
- **Performance**: `point_from_proportion` in a per-frame loop over a long
  route, `become` of a large group every frame, a deep copy of the whole
  diagram because one animation held a reference to it

### Reviewer 4: "The Editor" — Elegance & Clarity

Do a cleanup pass. Read every changed line as prose and ask: "is this the
simplest, clearest way to express this intent?" The goal is removing slop — not
clever code, not over-abstraction, just clean readable code that says exactly
what it means.

Focus areas:

- **Verbosity**: conditions that collapse to a single expression, redundant
  `None` checks, intermediate variables used once, `True if x else False`,
  a comprehension that should be a generator or vice versa
- **Naming**: names that do not communicate intent, a magic number or string
  that should be a named constant (`LAND = 0.85`, `LOST_AT = 0.7` are the
  house style), inconsistent naming inside one file
- **Repetition**: copy-pasted logic that should be a shared helper — but only
  at three or more instances; do not abstract prematurely
- **Control flow**: nested conditionals that should be guard clauses, a long
  method that should be two, an `if/elif` chain over a name that should be a
  dict lookup like `STATE_STYLES`
- **Comments and docstrings**: comments explain non-obvious constraints and
  manim quirks, never what the code already says. A comment that narrates the
  next line is a finding. So is a genuinely surprising constraint left
  uncommented — the renderer facts above earned their comments the hard way.
  Module and class docstrings read as short prose about what the thing is for,
  not a parameter list
- **Consistency**: one `from manim import X` per line, `from __future__ import
  annotations` with a `TYPE_CHECKING` block for type-only imports, a new
  pattern where the file already had one

Note though that: Clarity > Consistency > Concision. Clarity always, consistency
with determination, concision when prudent.

### Reviewer 5: "The Librarian" — Tests, Docs & Compatibility

This is a library. Every change to a public name is a change someone else's
scene file will feel, and the README's "What is in the box" is the only manual.

**Skip condition:** none. Even a diff that touches no public name can change
what a documented call does.

Focus areas:

- **Exports**: every public class and function is in `__all__` (the exports test
  enforces this, so a name the author wanted private must start with `_`), and
  nothing new shadows a manim name
- **README**: a new public name, parameter or behaviour appears in "What is in
  the box"; a removed or renamed one disappears from it; an example scene that
  changed had its GIF or still regenerated with `scripts/render_readme_media.sh`
- **Tests**: every behaviour change has a test that fails without the change,
  written the way this repo writes them — geometry and state without rendering,
  stepping animations by hand with `begin`, `interpolate`, `finish` where needed.
  Visual behaviour that cannot be asserted gets a touch in `SoftwareSmokeScene`
  or another scene that CI renders (`.github/workflows/ci.yml` lists them)
- **Compatibility**: `pyproject.toml` says `manim>=0.19` and Python 3.11, and
  the local venv runs newer versions of both. A manim API added after 0.19, a
  Python 3.12-only feature (`type` statements, PEP 701 f-strings), or a
  networkx call that needs a version manim does not pin is a finding
- **Signatures**: a new positional parameter inserted before existing ones, a
  default changed, a parameter removed — each breaks a caller. New parameters
  go last with defaults
- **Examples as documentation**: `examples/` are what users copy. A new feature
  with no example scene, or an example that uses a private helper, is a finding

## Phase 2: Format Each Review

For each reviewer, output:

```
### [Reviewer Name]

**P0 — Must fix before merge:**
1. [file:line] [description of issue and why it matters]

**P1 — Should fix before merge:**
1. [file:line] [description]

**P2 — Follow-up ticket:**
1. [file:line] [description]

**Nits:**
1. [file:line] [description]
```

## Phase 3: The Arbiter

After all five reviews, act as a Staff+ arbiter who:

1. **Deduplicates** — merge findings that overlap across reviewers
2. **Prioritizes** — a single unified list ranked by impact:
   - **MUST FIX** (blocks merge): wrong geometry, a render that differs from
     what the code reads, a public name broken or shadowed, a crash on an
     empty or degenerate input, an animation that cannot be shown again
   - **SHOULD FIX** (strongly recommended): design issues, style-contract
     violations, missing test coverage of new behaviour, stale README, unclear
     code
   - **FOLLOW-UP** (create ticket): improvements needing more context or too
     large for this PR
   - **NITS** (optional): style, naming, minor improvements
3. **Resolves conflicts** — if reviewers disagree, decide with reasoning. The
   Editor's simplification never outranks the Renderer's frame-correctness,
   and neither outranks the Librarian's compatibility
4. **Verifies before promoting** — for each MUST FIX, confirm the claim against
   the actual code (or a rendered frame) rather than the reviewer's summary of
   it. A confident finding that turns out to be wrong costs more than a missed
   nit

Output the arbiter's unified verdict:

```
## Arbiter Verdict

### MUST FIX (X items)
1. [file:line] [issue] — from [Reviewer] — [why this blocks merge]

### SHOULD FIX (X items)
1. [file:line] [issue] — from [Reviewer]

### FOLLOW-UP (X items)
1. [file:line] [issue] — create ticket: [suggested title]

### NITS (X items)
1. [file:line] [issue]
```

## Phase 4: Auto-Fix

After presenting the arbiter verdict, fix ALL "MUST FIX" and "SHOULD FIX" items:

1. Work through them one at a time in priority order
2. For each fix, make the minimal change that addresses the finding
3. Add or extend a test for every behaviour change — a fix with no
   failing-first test is a fix nobody will notice regressing
4. After all fixes are applied, run what CI runs:
   - `uv run pytest`
   - the smoke renders listed in `.github/workflows/ci.yml` (at least
     `uv run manim -s -qm examples/request_flow.py SoftwareSmokeScene`, plus
     any scene that exercises the changed code), and Read the resulting PNG
   - `uv build --out-dir tmp/dist` if `pyproject.toml` or the package layout changed
5. If anything fails, fix it. Do not skip a render because "the tests pass" —
   the tests never render, which is the whole point of the Renderer
6. If an example scene changed, regenerate its media with
   `uv run scripts/render_readme_media.sh` so the README stays true
7. For "FOLLOW-UP" items, add `# TODO(#NNN): [description]` at the relevant
   location, where NNN is a GitHub issue — extend an existing issue or open one
   with `gh issue create`

## Phase 5: Summary

Present a final summary:

- How many issues found per reviewer
- How many fixed vs deferred
- Any remaining concerns or risks
- Suggested test plan additions for the PR description
- Whether the change needs a manual look at a rendered clip rather than a
  still (moving packets, camera moves, lagged animations), and which scene at
  which quality renders it (`uv run manim -pql examples/<file>.py <Scene>`)
