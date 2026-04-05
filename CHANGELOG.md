# jerbs changelog

Versions follow [semver](https://semver.org/): MAJOR.MINOR.PATCH
- **MAJOR** — breaking changes to state schema or screening logic
- **MINOR** — new features or passes (backward-compatible)
- **PATCH** — bug fixes, prompt tweaks, copy changes

---

## 1.1.0-pr111 — 2026-04-05

- Restructured SKILL.md around 6-stage pipeline (LOAD → SEARCH → CLASSIFY → ANALYZE → MERGE → RENDER)
- Unified Gmail search: single query replaces two separate passes
- Pipeline overview diagram at top of SKILL.md gives Claude the full flow before starting

---

## 1.0.0 — 2026-04-05

First formally versioned release. All prior iterations are considered pre-1.0.

- Added `version` field to frontmatter
- Added `mode` field to state (`"testing"` | `"production"`, default production)
- Added version banner printed at run start when `mode === "testing"`
- Added mode toggle commands: `switch to testing mode`, `switch to production mode`, `what mode am I in?`
- Added `CHANGELOG.md`
