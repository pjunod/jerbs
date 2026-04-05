# jerbs changelog

Versions follow [semver](https://semver.org/): MAJOR.MINOR.PATCH
- **MAJOR** — breaking changes to state schema or screening logic
- **MINOR** — new features or passes (backward-compatible)
- **PATCH** — bug fixes, prompt tweaks, copy changes

---

## 1.0.0 — 2026-04-05

First formally versioned release. All prior iterations are considered pre-1.0.

- Added `version` field to frontmatter
- Added `mode` field to state (`"testing"` | `"production"`, default production)
- Added version banner printed at run start when `mode === "testing"`
- Added mode toggle commands: `switch to testing mode`, `switch to production mode`, `what mode am I in?`
- Added `CHANGELOG.md`
