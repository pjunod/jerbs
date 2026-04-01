# Jerbs Improvement Backlog

Architecture and efficiency improvements identified in expert review (2026-03-31).
Ordered by impact. Mark items with `[x]` when complete.

---

## High Impact

- [x] **Prompt caching** — Add `cache_control: ephemeral` to system prompt in `screener.py`. Cuts 75%+ of input token cost on multi-email runs. 2-line change. _(pjunod/jerbs#30)_

- [x] **Tool use for output** — Replace `json.loads()` string parsing in `screener.py` with Claude's native tool use / function calling. Eliminates all parse failures; lets you remove the JSON spec block from the system prompt (~15 lines saved per call). _(pjunod/jerbs#30)_

- [x] **SKILL.md bloat cleanup** — Remove duplicate schema sections (criteria + correspondence log each appear twice), merge duplicate scheduler/widget docs, condense setup wizard Q&A from scripted dialogue to a compact field list. ~175 lines removed (~15-20% of file). _(pjunod/jerbs#31)_

- [x] **Model tiering** — Haiku fast-path for clear fails; Sonnet + extended thinking for pass/maybe. `_call_api()` helper added. _(pjunod/jerbs#35)_

- [x] **Extended thinking for ambiguous verdicts** — Sonnet escalation call always uses `thinking: {type: enabled, budget_tokens: 5000}` for reliable judgment on edge cases. _(pjunod/jerbs#35)_

---

## Medium Impact

- [x] **Fix Gmail query construction** — Replaced fragile string surgery with programmatic query builder in `screener.py`. Extra keywords now correctly inserted inside `subject:()` clause. _(pjunod/jerbs#33)_

- [x] **Fix `screened_message_ids` format in daemon mode** — Daemon now writes `{"id": ..., "screened_at": ...}` objects. Legacy strings migrated on first save. 60-day pruning active. _(pjunod/jerbs#34)_

- [x] **Batch API for daemon runs** — Daemon mode uses Anthropic Batch API for >3 emails (50% cost reduction). Interactive `--once` runs use real-time API. `_screen_batch()` added; `run()` accepts `use_batch` + `on_result` params. _(pjunod/jerbs#TBD)_

- [x] **Streaming output for interactive runs** — `--once` mode streams results via `on_result` callback as each email is screened. Daemon/batch mode logs summary at end. _(pjunod/jerbs#TBD)_

- [x] **Symlink skill files** — `~/.claude/commands/jerbs.md` is now a symlink to root `SKILL.md`. `claude-web/assets/scheduler.html` is a symlink to `assets/scheduler.html`. CI check added in `lint.yml`. Stale export path (`scripts/` → `shared/scripts/`) fixed in both SKILL.md files. _(pjunod/jerbs#TBD)_

---

## Low Impact / Hygiene

- [x] **Criteria hash cache on Screener instance** — Cache the built prompt string keyed to a criteria hash. Avoids rebuilding an identical string across repeated `screener.run()` calls in a session. _(pjunod/jerbs#33)_

- [x] **Correspondence log pruning in daemon mode** — `_prune_correspondence_log()` added: prunes closed threads (replied_at set AND >90 days old) on each daemon save. _(pjunod/jerbs#34)_
