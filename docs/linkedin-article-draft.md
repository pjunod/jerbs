# AI Wrote Perfect Code Twice — And That Was the Problem

I've been building a side project almost entirely with AI coding assistants. The app screens job emails across three deployment modes: a browser interface, a CLI tool, and a local daemon. Each mode was built incrementally over weeks of work.

Yesterday I typed this into my AI coding assistant:

> *"ok I want you to put on your application architect cap again. I'd like you to analyze this current application issue to the best of all of your capabilities. The jerbs app has modes to render output on the claude web page, as well as in claude code and via a local daemon. Getting the output rendering to match in all cases has been problematic. For the claude web, it seems that there's an elaborate method to try to render the same as the other methods, but it seems unnecessary. For claude web, all you have to do is render the same output file that you are using for claude code and daemon mode, and just display it as an artifact. This means the actual rendering pipeline is the same for everything, and you're just making it display as an artifact in the web version. Please analyze how it is currently setup with the above and give me some recommendations"*

What it found was a perfect case study of a problem every team using AI for development is about to face.

## The Setup

The app generates interactive HTML report pages from screening results. When I built the browser version, it needed to deliver HTML as an inline artifact — so the AI created a client-side template: a self-contained single-page app that reads embedded JSON data and renders everything at runtime using JavaScript. 1,289 lines. Theme switcher, filter bar, expandable cards, the works.

The CLI and daemon modes had been built earlier using a different approach — a Python script that generates HTML server-side via string concatenation. 1,364 lines. Same themes, same cards, same filters. Built with the same care, same test coverage, same attention to detail.

Two rendering engines. 2,653 lines of code. Producing identical output.

## How It Happened

Here's the thing that's hard to accept: neither piece of code was wrong.

The Python generator was well-structured and thoroughly tested. The JavaScript template was well-structured and thoroughly tested. If you reviewed either one in isolation, you'd approve the PR.

The problem is that AI assistants build incrementally, within the context of the current conversation. When the browser mode was built weeks after the CLI mode, the AI didn't "remember" the existing Python renderer. It solved the problem in front of it — and solved it well — using the approach that made sense for the browser delivery mechanism.

Nobody told it to look at the system as a whole. It was never asked "hey, is there already something that does this?"

## The Duplication Was Invisible at the PR Level

Every function in the Python engine had a character-for-character equivalent in the JavaScript template:

- `_e()` in Python, `escapeHtml()` in JavaScript
- `_age_badge_html()` in Python, `ageBadgeHtml()` in JavaScript
- `build_terminal_card()` in Python, `buildTerminalCard()` in JavaScript
- 21 functions total, duplicated across two languages

A bug fix or feature addition to one engine required a manual port to the other. And because they were in different languages, no linter or static analysis tool would catch the drift.

The demo page made it worse. Even though the template already had a runtime theme switcher, the Python generator was producing two separate 90KB HTML files — one per theme. Three files to show the same data.

## The Fix Was Embarrassingly Simple

Once I asked the AI to step back and look at the whole rendering pipeline, the answer was obvious: the JavaScript template was already the more capable implementation. It had both themes with runtime switching. It handled everything client-side from a JSON blob.

The Python generator just needed to become a thin wrapper:

1. Read the template
2. Inject the results JSON
3. Write the file

That's it. 1,364 lines of Python became 108. The demo collapsed from three files to one. Every output — browser, CLI, daemon, demo — now uses the same rendering pipeline. The only difference is how the file is delivered.

| Metric | Before | After |
|---|---|---|
| Python rendering code | 1,364 lines | 108 lines |
| Rendering engines to maintain | 2 | 1 |
| Cross-language function duplication | 21 functions | 0 |
| Demo files | 2 (166KB) | 1 (93KB) |
| Places to fix a rendering bug | 2 | 1 |
| Theme support per file | 1 (locked at generation) | 2 (runtime switchable) |

## The Lesson for Teams Adopting AI

This isn't a story about AI writing bad code. It's about what happens when AI writes *good* code without system-level context.

AI assistants are phenomenal at solving the problem in front of them. Give them a well-scoped task with clear requirements and they'll produce clean, tested, production-ready code. But they don't carry architectural awareness between sessions. They don't ask "does something like this already exist?" They don't look at the system diagram before writing a new module.

This is the new version of an old problem. Junior developers do the same thing — they build from scratch instead of discovering existing solutions. The difference is that AI does it faster, with higher confidence, and produces code that looks so polished it sails through review.

**Here's what I think teams need to build into their AI-assisted workflows:**

**1. Schedule periodic architecture reviews.** Not code reviews — architecture reviews. Ask the AI (or a human) to look at the system holistically, across modules, across deployment modes, across languages. The kind of analysis that asks "are we solving the same problem in two places?"

**2. Treat AI output as a first draft, even when it's good.** The quality of individual outputs creates a false sense of completeness. A function can be well-written and still be unnecessary.

**3. Maintain living architecture documentation.** If the AI had access to a diagram showing "here's how rendering works across all modes," it would have recognized the duplication when building the browser version. Context is everything — give it context.

**4. Watch for the copy-paste pattern across languages.** When the same logic exists in Python and JavaScript (or any two languages), that's not "polyglot architecture" — it's duplication wearing a disguise.

**5. Remember that the human's job is changing, not disappearing.** I didn't write any of the rendering code. I also couldn't have caught this problem by reading individual PRs. My value was in stepping back and asking the right question at the right time. That's the emerging shape of human-AI collaboration: the AI builds, the human architects.

## The Uncomfortable Truth

This problem will get worse before it gets better. As AI assistants get faster and more capable, teams will ship more code faster. The duplication won't be within a single PR — it'll be across features built weeks apart, by different team members, in different conversations with different AI sessions.

The teams that thrive won't be the ones with the best AI tools. They'll be the ones that build the discipline to periodically look up from the code and ask: "what did we build, and does it all fit together?"

That's a fundamentally human question. And it might be the most important skill in AI-assisted development.

---

*The project referenced is open source: [github.com/pjunod/jerbs](https://github.com/pjunod/jerbs). The PR with the full analysis, architecture diagrams, and implementation is [#88](https://github.com/pjunod/jerbs/pull/88).*
