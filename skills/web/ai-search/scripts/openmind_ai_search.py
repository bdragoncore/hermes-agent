#!/usr/bin/env python3
"""Drive the OpenMind browser's AI chat/search tabs via its REST API.

The AI sites (Perplexity, Claude, Gemini, ...) are only logged in inside the
OpenMind browser, so every AI-site request goes through its REST API on
``http://127.0.0.1:8790`` (override with ``--api`` or ``$OPENMIND_BROWSER_API``).
This helper covers the fiddly parts: finding/activating the site tab, selecting
a model in the composer picker, typing + submitting a prompt, and reading the
answer back. Stdlib only.

Examples::

    python openmind_ai_search.py tabs
    python openmind_ai_search.py ask perplexity --model "Kimi K3" --prompt "..."
    python openmind_ai_search.py model perplexity "Kimi K3"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

DEFAULT_API = os.environ.get("OPENMIND_BROWSER_API", "http://127.0.0.1:8790")

# site -> url, composer input selector, model-picker button regex, submit mode.
# "enter" submits with the Enter key; "button" clicks the send button.
SITES = {
    "perplexity": {"url": "https://www.perplexity.ai/", "host": "perplexity.ai",
                   "input": "[contenteditable=true]",
                   "picker": r"^(Model|Best|GPT-|Gemini|Claude|Kimi|GLM|Grok|Nemotron)",
                   "submit": "enter"},
    "qwen": {"url": "https://chat.qwen.ai/", "host": "chat.qwen.ai",
             "input": "textarea", "picker": r"^Qwen", "submit": "enter"},
    "claude": {"url": "https://claude.ai/", "host": "claude.ai",
               "input": "[contenteditable=true]", "picker": r"(Opus|Sonnet|Haiku|Fable)",
               "submit": "enter"},
    "gemini": {"url": "https://gemini.google.com/", "host": "gemini.google.com",
               "input": "[contenteditable=true]", "picker": r"^(Pro|Flash|\d)",
               "submit": "button"},
    "grok": {"url": "https://grok.com/", "host": "grok.com",
             "input": "[contenteditable=true]", "picker": r"^(Auto|Fast|Expert|Build|Heavy)",
             "submit": "enter"},
    "zai": {"url": "https://chat.z.ai/", "host": "chat.z.ai",
            "input": "textarea", "picker": r"(Deep Think|GLM)", "submit": "enter"},
    "deepseek": {"url": "https://chat.deepseek.com/", "host": "chat.deepseek.com",
                 "input": "textarea", "picker": None, "submit": "enter"},
    "kimi": {"url": "https://www.kimi.ai/", "host": "kimi", "input": "[contenteditable=true]",
             "picker": None, "submit": "button"},
}


def _req(method: str, url: str, payload: dict | None = None, timeout: int = 60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data, {"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body) if body else {}


class Browser:
    def __init__(self, api: str = DEFAULT_API):
        self.api = api.rstrip("/")

    def _post(self, path: str, payload: dict, timeout: int = 60):
        return _req("POST", self.api + path, payload, timeout)

    def _get(self, path: str):
        return _req("GET", self.api + path)

    def tabs(self) -> list[dict]:
        return self._get("/api/browser/tabs").get("tabs", [])

    def eval(self, tab_id: int, code: str):
        return self._post("/api/browser/eval", {"tab_id": tab_id, "code": code}).get("result")

    def activate(self, tab_id: int):
        return self._post("/api/browser/activate_tab", {"tab_id": tab_id})

    def click(self, tab_id: int, x: int, y: int):
        return self._post("/api/browser/click", {"tab_id": tab_id, "x": x, "y": y})

    def type(self, tab_id: int, text: str, selector: str):
        return self._post("/api/browser/type", {"tab_id": tab_id, "text": text, "selector": selector})

    def key(self, tab_id: int, key: str):
        return self._post("/api/browser/key", {"tab_id": tab_id, "key": key})


def find_tab(browser: Browser, host: str) -> dict | None:
    for tab in browser.tabs():
        if host in (tab.get("url") or ""):
            return tab
    return None


def ensure_tab(browser: Browser, site: str) -> int:
    """Return an *activated* tab id for ``site``, opening it if needed."""
    preset = SITES[site]
    tab = find_tab(browser, preset["host"])
    if tab is None:
        browser._post("/api/browser/new_tab", {"url": preset["url"]})
        for _ in range(30):
            time.sleep(1)
            tab = find_tab(browser, preset["host"])
            if tab:
                break
    if tab is None:
        raise RuntimeError(f"could not open a tab for {site}")
    tab_id = tab["id"]
    browser.activate(tab_id)
    for _ in range(30):
        tabs = {t["id"]: t for t in browser.tabs()}
        if not tabs.get(tab_id, {}).get("loading", False):
            break
        time.sleep(1)
    time.sleep(1)
    return tab_id


def _center_js(match_js: str) -> str:
    return (
        "(()=>{const e=" + match_js + ";if(!e)return 'none';"
        "const r=e.getBoundingClientRect();"
        "return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});})()"
    )


def select_model(browser: Browser, site: str, model: str, picker_label: str | None = None) -> str:
    """Open the composer's model picker and click the option starting with ``model``."""
    preset = SITES[site]
    tab_id = ensure_tab(browser, site)
    label_re = picker_label or preset.get("picker")
    if not label_re:
        raise RuntimeError(f"{site} has no known model picker; pass --picker-label")

    picker_js = (
        "Array.from(document.querySelectorAll('button,[role=button],[role=combobox]'))"
        f".find(e=>/{label_re}/i.test((e.innerText||'').trim()))"
    )
    pos = browser.eval(tab_id, _center_js(picker_js))
    if pos == "none":
        raise RuntimeError(f"{site}: model picker button not found (label /{label_re}/)")
    x, y = json.loads(pos).values()
    browser.click(tab_id, x, y)
    time.sleep(2)

    want = json.dumps(model)
    opt_js = (
        "Array.from(document.querySelectorAll('[role=menuitem],[role=option],"
        "[role=menuitemradio],[role=menuitemcheckbox]'))"
        f".find(e=>(e.innerText||'').trim().toLowerCase().startsWith(({want}).toLowerCase()))"
    )
    pos = browser.eval(tab_id, _center_js(opt_js))
    if pos == "none":
        options = browser.eval(
            tab_id,
            "JSON.stringify(Array.from(document.querySelectorAll('[role=menuitem],"
            "[role=option],[role=menuitemradio]')).map(e=>e.innerText.trim()))",
        )
        raise RuntimeError(f"{site}: no option starting with {model!r}. Options: {options}")
    x, y = json.loads(pos).values()
    browser.click(tab_id, x, y)
    time.sleep(1)
    current = browser.eval(
        tab_id,
        "(()=>{const e=Array.from(document.querySelectorAll('button'))"
        f".find(e=>/{label_re}/i.test((e.innerText||'').trim()));"
        "return e?(e.innerText||'').replace(/\\s+/g,' ').trim():'(unknown)';})()",
    )
    return current


def _submit(browser: Browser, site: str, tab_id: int):
    if SITES[site]["submit"] == "button":
        send_js = (
            "Array.from(document.querySelectorAll('button')).find(e=>"
            "/send/i.test(e.getAttribute('aria-label')||e.getAttribute('data-testid')||''))"
        )
        pos = browser.eval(tab_id, _center_js(send_js))
        if pos != "none":
            x, y = json.loads(pos).values()
            browser.click(tab_id, x, y)
            return
    browser.key(tab_id, "Enter")


def ask(browser: Browser, site: str, prompt: str, model: str | None = None,
        picker_label: str | None = None, timeout: int = 120) -> str:
    tab_id = ensure_tab(browser, site)
    if model:
        select_model(browser, site, model, picker_label)
    browser.type(tab_id, prompt, SITES[site]["input"])
    time.sleep(1)
    baseline = len(browser.eval(tab_id, "document.body.innerText") or "")
    _submit(browser, site, tab_id)

    deadline = time.time() + timeout
    last, stable = None, 0
    while time.time() < deadline:
        time.sleep(3)
        text = browser.eval(tab_id, "document.body.innerText") or ""
        if len(text) > baseline and text == last:
            stable += 1
            if stable >= 2:
                return text
        else:
            stable = 0
        last = text
    return last or ""


def _cmd_tabs(browser: Browser, args):
    for tab in browser.tabs():
        print(f"{tab['id']}\t{tab.get('url')}\t{tab.get('title')}")
    return 0


def _cmd_model(browser: Browser, args):
    print(select_model(browser, args.site, args.model, args.picker_label))
    return 0


def _cmd_ask(browser: Browser, args):
    answer = ask(browser, args.site, args.prompt, args.model, args.picker_label, args.timeout)
    print(answer)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default=DEFAULT_API)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("tabs").set_defaults(func=_cmd_tabs)

    p_model = sub.add_parser("model")
    p_model.add_argument("site", choices=sorted(SITES))
    p_model.add_argument("model")
    p_model.add_argument("--picker-label", default=None)
    p_model.set_defaults(func=_cmd_model)

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("site", choices=sorted(SITES))
    p_ask.add_argument("--prompt", required=True)
    p_ask.add_argument("--model", default=None)
    p_ask.add_argument("--picker-label", default=None)
    p_ask.add_argument("--timeout", type=int, default=120)
    p_ask.set_defaults(func=_cmd_ask)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    browser = Browser(args.api)
    try:
        return args.func(browser, args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
