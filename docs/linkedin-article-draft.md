# AI Wrote Perfect Code Twice — And That Was the Problem

I've been building a side project almost entirely with AI coding assistants. The app screens job emails across three deployment modes: a browser interface, a CLI tool, and a local daemon. Each mode was built incrementally over weeks of work.

Yesterday I typed this into my AI coding assistant:

> *"ok I want you to put on your application architect cap again. I'd like you to analyze this current application issue to the best of all of your capabilities. The jerbs app has modes to render output on the claude web page, as well as in claude code and via a local daemon. Getting the output rendering to match in all cases has been problematic. For the claude web, it seems that there's an elaborate method to try to render the same as the other methods, but it seems unnecessary. For claude web, all you have to do is render the same output file that you are using for claude code and daemon mode, and just display it as an artifact. This means the actual rendering pipeline is the same for everything, and you're just making it display as an artifact in the web version. Please analyze how it is currently setup with the above and give me some recommendations"*

What it found was a perfect case study of a problem every team using AI for development is about to face.

## The Setup

The app generates interactive HTML report pages from screening results. When I built the browser version, it needed to deliver HTML as an inline artifact — so the AI created a client-side template: a self-contained single-page app that reads embedded JSON data and renders everything at runtime using JavaScript. 1,289 lines. Theme switcher, filter bar, expandable cards, the works.

The CLI and daemon modes had been built earlier using a different approach — a Python script that generates HTML server-side via string concatenation. 1,364 lines. Same themes, same cards, same filters. Built with the same care, same test coverage, same attention to detail.

Two rendering engines. 2,653 lines of code. Producing identical output.

You can see the whole progression in the public commit history. [PR #54](https://github.com/pjunod/jerbs/pull/54) introduced the first HTML output with dual themes, built in Python. [PR #74](https://github.com/pjunod/jerbs/pull/74) expanded it with source grouping, responsive layout, and interactive cards — all server-side string concatenation. Then [PR #86](https://github.com/pjunod/jerbs/pull/86) introduced the JavaScript template as a second rendering engine for the browser mode. Each PR was well-crafted. Each one passed review. And the system quietly doubled in complexity.

## How It Happened

Here's the thing: neither piece of code was *broken*. They both worked.

But "it works" isn't the same as "it's good." The Python generator was a 1,364-line monolith that built HTML through string concatenation, with hundreds of lines of CSS and JavaScript stored as inline Python constants. It was overengineered from the start — the kind of solution an AI produces when you ask it to solve a problem without constraints. It got us past the immediate need and on to other things, which is all it needed to do at the time.

The JavaScript template was the cleaner design — a self-contained SPA that reads JSON and renders client-side. But it was built alongside the Python generator, not as a replacement for it.

The problem is that AI assistants build incrementally, within the context of the current conversation. When the browser mode was built weeks after the CLI mode, the AI didn't "remember" the existing Python renderer. It solved the problem in front of it — using the approach that made sense for the browser delivery mechanism — and produced a second rendering engine without recognizing the first one should have been retired.

Nobody told it to look at the system as a whole. It was never asked "hey, is there already something that does this?"

## The Duplication Was Invisible at the PR Level

Every function in the Python engine had a character-for-character equivalent in the JavaScript template:

- `_e()` in Python, `escapeHtml()` in JavaScript
- `_age_badge_html()` in Python, `ageBadgeHtml()` in JavaScript
- `build_terminal_card()` in Python, `buildTerminalCard()` in JavaScript
- 21 functions total, duplicated across two languages

A bug fix or feature addition to one engine required a manual port to the other. And because they were in different languages, no linter or static analysis tool would catch the drift.

The demo page made it worse. Even though the template already had a runtime theme switcher, the Python generator was producing two separate HTML files — one per theme (95KB and 77KB). Two files to show the same data, with the theme baked in at generation time.

## The Fix Was Embarrassingly Simple

Once I asked the AI to step back and look at the whole rendering pipeline, the answer was obvious: the JavaScript template was already the more capable implementation. It had both themes with runtime switching. It handled everything client-side from a JSON blob.

The Python generator just needed to become a thin wrapper:

1. Read the template
2. Inject the results JSON
3. Write the file

That's it. 1,364 lines of Python became 108. The two demo files collapsed into one. Every output — browser, CLI, daemon, demo — now uses the same rendering pipeline. The only difference is how the file is delivered.

| Metric | Before | After |
|---|---|---|
| Python rendering code | 1,364 lines | 108 lines |
| Rendering engines to maintain | 2 | 1 |
| Cross-language function duplication | 21 functions | 0 |
| Demo data files | 2 (172KB) | 1 (96KB) |
| Places to fix a rendering bug | 2 | 1 |
| Theme support per file | 1 (locked at generation) | 2 (runtime switchable) |

## The Lesson for Teams Adopting AI

This isn't a story about AI writing bad code. It's about what happens when AI writes *good* code without system-level context.

AI assistants are phenomenal at solving the problem in front of them. Give them a well-scoped task with clear requirements and they'll produce clean, tested, production-ready code. But they don't carry architectural awareness between sessions. They don't ask "does something like this already exist?" They don't look at the system diagram before writing a new module.

This is the new version of an old problem. Junior developers do the same thing — they build from scratch instead of discovering existing solutions. The difference is that AI does it faster, with higher confidence, and produces code that looks so polished it sails through review.

**Here's what I think teams need to build into their AI-assisted workflows:**

**1. Schedule periodic architecture reviews.** Not code reviews — architecture reviews. Ask the AI (or a human) to look at the system holistically, across modules, across deployment modes, across languages. The kind of analysis that asks "are we solving the same problem in two places?"

**2. Treat AI output as a first draft, even when it works.** Working code creates a false sense of completeness. A module can pass every test and still be overengineered, or unnecessary, or a duplicate of something that already exists.

**3. Maintain living architecture documentation.** If the AI had access to a diagram showing "here's how rendering works across all modes," it would have recognized the duplication when building the browser version. Context is everything — give it context.

**4. Watch for the copy-paste pattern across languages.** When the same logic exists in Python and JavaScript (or any two languages), that's not "polyglot architecture" — it's duplication wearing a disguise.

**5. Remember that the human's job is changing, not disappearing.** I didn't write any of the rendering code. I also couldn't have caught this problem by reading individual PRs. My value was in stepping back and asking the right question at the right time. That's the emerging shape of human-AI collaboration: the AI builds, the human architects.

## "Wouldn't RAG Have Prevented This?"

This is the first question engineers ask, and the answer is: partially.

A retrieval system that surfaces related files when the AI starts building something new would have flagged the existing Python renderer before the JavaScript template was built from scratch. Basic semantic search — "files related to HTML generation" — would have surfaced it. Living architecture docs in the AI's context would have helped too. If a file had said "rendering is handled by export_html.py," the AI likely would have proposed extending it rather than building a parallel system.

But RAG has real limits here:

**RAG tells you "this exists," not "this is the better pattern."** Even with perfect retrieval, the AI would have known about the Python generator — but might have made the new template call into it, adding a dependency instead of recognizing the template was the superior approach that should replace both. The architectural judgment — that client-side rendering from JSON is strictly better than server-side string concatenation when both produce the same output — requires understanding the system, not just finding related files.

**Cross-language duplication is invisible to retrieval.** RAG over a Python codebase finds Python patterns. Finding that `_age_badge_html()` in Python does the same thing as `ageBadgeHtml()` in JavaScript requires semantic understanding across languages, not keyword matching.

**RAG retrieves context for the task at hand. It doesn't proactively flag concerns about things you aren't working on.** Nobody was "working on the rendering pipeline" when the duplication was introduced. They were building a browser deployment mode. The duplication was a side effect of solving a different problem.

What actually prevents this is harder to build than a vector database:

- **Architecture-aware planning** — before building any new module, an active investigation step: "search the codebase for existing implementations of this concern." Not retrieval. Investigation.
- **Cross-session architectural memory** — not raw file retrieval, but curated summaries of design decisions and system relationships. "The rendering pipeline uses export_html.py for server-side generation" is more useful than finding the file itself.
- **A human who notices friction** — which is exactly what happened here. I noticed that "getting the output rendering to match in all cases has been problematic" and asked why. No amount of RAG replaces that instinct.

The real gap isn't retrieval. It's that AI assistants don't have a persistent concept of "the system." RAG gives them memory of *files*. What they need is memory of *architecture* — the relationships between components, the design decisions behind what exists, the "why" that makes duplication recognizable as duplication. That's a harder problem, and the industry is only starting to work on it.

## The Uncomfortable Truth

This problem will get worse before it gets better. As AI assistants get faster and more capable, teams will ship more code faster. The duplication won't be within a single PR — it'll be across features built weeks apart, by different team members, in different conversations with different AI sessions.

The teams that thrive won't be the ones with the best AI tools. They'll be the ones that put development processes in place that force the bigger picture view — architecture reviews before new modules land, system-level documentation that stays current, checkpoints that ask "does this change fit into what we already have?" before the PR is approved.

The discipline can't live in one person's head. It has to be in the process. Because when AI is generating code faster than any individual can review it holistically, the process is the only thing standing between "well-crafted components" and "a system that makes sense."

---

*The project referenced is open source: [github.com/pjunod/jerbs](https://github.com/pjunod/jerbs). The PR with the full analysis, architecture diagrams, and implementation is [#88](https://github.com/pjunod/jerbs/pull/88).*

*Full transparency: this article was drafted by the same AI that wrote the code and the fix. I directed the process from the start — identifying the problem, guiding the architectural analysis, planning the refactor, and deciding what the article should say. The AI did the writing. I did the editing, the judgment calls, and the "what's the point of all this?" The whole thing was built with the article in mind from the moment the issue was identified. Meta? Sure. But it felt like the honest way to demonstrate the collaboration model I'm describing.*
