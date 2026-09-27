---
name: ai-search
description: "Search the web and drive AI chat sites with model choice."
version: 2.0.0
author: Bryan Perris (bperris), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Web, Search, Browser, AI Chat, Model Selection, Research]
    category: web
    related_skills: [blocked-page-recovery, grounded-citations]
---

# AI Search Skill

Two ways to run a search. Ordinary web search/fetch uses Hermes' native tools
(`web_search`, `web_extract`, `browser_navigate`). When the human names an **AI
chat/search site** (Perplexity, Claude, Grok, Gemini, Qwen, Z.ai, DeepSeek,
Kimi) or a **model one of those sites offers** ("Kimi K3 via Perplexity"), drive
the real site through the OpenMind browser and select the model in the site's
own picker. Never substitute a gateway or provider model for the site the human
asked for.

## When to Use

- The human explicitly invokes "ai-search" / "ai-browser".
- The human names an AI chat/search site, or a model that one of those sites
  offers, and wants an answer or search from it.
- A delegated task asks for web search, page research, or multi-step browsing.

Do NOT trigger on ordinary web requests — those go straight to the native
tools. But when a site or a site's model is named, this skill IS the right
path; do not route around it.

## Prerequisites

- `terminal` — to run `scripts/openmind_ai_search.py` against the OpenMind
  browser REST API (default `http://127.0.0.1:8790`; override with `--api` or
  `$OPENMIND_BROWSER_API`). This is the only browser where the AI sites are
  logged in, so every AI-site request goes through it.
- Native `web_search`, `web_extract`, `browser_navigate` for ordinary pages.
- For blocked/paywalled/bot-walled pages, load `blocked-page-recovery` and
  follow its ladder.

## How to Run

Use the helper (stdlib only, skill-relative):

```sh
python skills/web/ai-search/scripts/openmind_ai_search.py ask perplexity \
  --model "Kimi K3" --prompt "your question"
```

`ask` runs the whole flow (find/activate tab → optional model select → type →
submit → read answer); `model` selects a model only; `tabs` lists AI tabs.

## Quick Reference

| Goal | Command (through `terminal`) |
|------|------------------------------|
| List AI tabs | `python .../openmind_ai_search.py tabs` |
| Ask a site | `python .../openmind_ai_search.py ask perplexity --prompt "..."` |
| Ask with a model | `... ask perplexity --model "Kimi K3" --prompt "..."` |
| Select a model only | `... model perplexity "Kimi K3"` |
| Ordinary web page | native `web_extract` (static) / `browser_navigate` (JS) |
| Blocked page | `blocked-page-recovery` ladder |

## AI chat sites and their models

The picker is a pill/button in the composer; the helper opens it and clicks
the option whose label **starts with** the requested name (labels carry status
suffixes like "Thinking"/"New"/"Max").

| Site | Model picker? | Options (observed 2026-09-26) |
|------|---------------|-------------------------------|
| Perplexity | yes — composer "Model" button (shows the current model once set) | Best *(default)*, GPT-6 Sol, Gemini 3.8 Flash, Claude Sonnet 5, Claude Opus 5.5, Kimi K3, GLM 5.3, Grok 4.7, Nemotron 3 Ultra |
| Qwen | yes — model pill | Qwen3.7-Plus *(default)*, Qwen3.8-Max, Qwen3.8-Omni-Flash |
| Claude | yes — model pill | Fable 5.1, Opus 5.5, Sonnet 5, Haiku 4.5 (+ Effort selector) |
| Gemini | yes — model pill | 3.5 Flash-Lite, 3.8 Flash, 3.1 Pro (+ Extended thinking) |
| Grok | yes — "Auto" pill | Auto, Fast, Expert, Build, Heavy |
| Z.ai | yes — model/mode pill | Deep Think Max / GLM series (custom popover) |
| DeepSeek | no list — mode toggles | DeepThink + Search |
| Kimi | no model selector | — |

**Gating:** Perplexity Max-only models (e.g. Claude Opus 5.5) are listed but
unavailable on a Pro account. If a requested model is gated or missing, say so
— never silently substitute another model.

## Procedure

### 1. Classify the request

Decide native vs AI-site: if the human named a site or one of its models, it
is an AI-site request (use the helper); otherwise use the native tools. Done when the path (native vs site)
and the target site are fixed.

### 2. Choose the model

If the human named a model, pass it as `--model`. If they named a site but no
model, omit `--model` (the site's default is used). If the named model is not
offered by that site, say so and ask which to use instead — do not swap in a
gateway model. Done when the site + model (or "site default") are decided.

### 3. Run the ask

`python skills/web/ai-search/scripts/openmind_ai_search.py ask <site>
[--model "<name>"] --prompt "<question>"`. For a model change on its own, run
the `model` subcommand. Done when the command returns without an `error:`.

### 4. Read the answer

The helper polls until the reply text stops growing, then prints it. If the
output looks like a login page or a marketing landing (site not on a chat
view), `browser_navigate` the site's home and retry once. Done when the answer
text contains a real reply, not boilerplate.

### 5. Report

Answer the human with the site, the model actually selected, and the reply. If
a site failed, name the site and the error. Done when the human knows which
site/model answered and any failures.

## Pitfalls

- **Never substitute the OpenMind gateway** (`http://pibox:5000/v1/chat/completions`,
  Synthetic/OpenRouter/Kilo model ids) or a provider model for a site the human
  named. "Kimi K3 through Perplexity" means Perplexity's own Kimi K3, not the
  gateway's Kimi.
- **Input events reach only the active tab.** The helper activates the tab; if
  driving the API by hand, `activate_tab` first.
- **Labels carry suffixes.** Match options by prefix (`startsWith`), not
  equality — "Kimi K3" is "Kimi K3 Thinking" in the DOM.
- **Kimi and Gemini submit with a send button**, not Enter; Perplexity/Qwen/
  Claude/Grok/Z.ai/DeepSeek accept Enter. The helper handles both.
- **Max-only models are gated** on a Pro account; report, don't substitute.
- **Don't navigate a tab to `*/api/auth/session`** — it poisons/clears the
  site session.

## Verification

- After a model select, the composer pill shows the requested name (the helper
  prints it, e.g. "Kimi K3 Thinking").
- The reply text is non-empty and contains the answer, not a login/landing page.
- No gateway call was made for a site/model the human named.
