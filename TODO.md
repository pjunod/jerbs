# Jerbs Improvement Backlog

Architecture and efficiency improvements identified in expert review (2026-03-31).
Ordered by impact. Mark items with `[x]` when complete.

---

## High Impact

- [x] **Prompt caching** — Add `cache_control: ephemeral` to system prompt in `screener.py`. Cuts 75%+ of input token cost on multi-email runs. 2-line change. _(pjunod/jerbs#30)_

- [x] **Tool use for output** — Replace `json.loads()` string parsing in `screener.py` with Claude's native tool use / function calling. Eliminates all parse failures; lets you remove the JSON spec block from the system prompt (~15 lines saved per call). _(pjunod/jerbs#30)_

- [x] **SKILL.md bloat cleanup** — Remove duplicate schema sections (criteria + correspondence log each appear twice), merge duplicate scheduler/widget docs, condense setup wizard Q&A from scripted dialogue to a compact field list. ~175 lines removed (~15-20% of file). _(pjunod/jerbs#31)_

- [ ] **Model tiering** — Use Haiku for clear-fail fast-path screening, Sonnet only for pass/maybe verdicts requiring real judgment. Most Pass 2 spam can be rejected by Haiku in milliseconds for pennies.

---

## Medium Impact

- [ ] **Fix Gmail query construction** — Replace fragile `str.replace()` surgery for `extra_keywords` injection in `screener.py` with a programmatic query builder. Current approach inserts keywords in the wrong position.

- [ ] **Fix `screened_message_ids` format in daemon mode** — Daemon writes raw string IDs instead of `{"id": ..., "screened_at": ...}` objects. The 60-day pruning logic in the skill never fires for daemon-screened IDs. Fix the save step in `jerbs.py`.

- [ ] **Batch API for daemon runs** — Use Anthropic Message Batches API for runs with >3 emails (50% cost reduction). Keep real-time API for interactive Claude Code sessions. Already architecturally clean — `_screen_one()` is a pure function.

- [ ] **Extended thinking for ambiguous verdicts** — Trigger extended thinking on "maybe" results with uncertain comp ranges or partial whitelist/blacklist matches to improve accuracy on edge cases.

- [ ] **Streaming output for interactive runs** — Show results as each email is screened in Claude Code interactive sessions rather than waiting for the full batch. Improves perceived responsiveness significantly.

- [ ] **Symlink skill files** — `~/.claude/commands/jerbs.md`, `claude-ai/SKILL.md`, and root `SKILL.md` can drift. Make the commands file a symlink to the canonical repo file and add a CI check.

---

## Low Impact / Hygiene

- [ ] **Criteria hash cache on Screener instance** — Cache the built prompt string keyed to a criteria hash. Avoids rebuilding an identical string across repeated `screener.run()` calls in a session.

- [ ] **Correspondence log pruning in daemon mode** — No pruning logic for the correspondence log (unlike `screened_message_ids`). Add pruning of closed threads (replied_at set AND >90 days old) on save.
