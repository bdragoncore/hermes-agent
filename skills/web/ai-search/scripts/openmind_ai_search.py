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
                   "submit": "enter", "answer": ".prose"},
    "qwen": {"url": "https://chat.qwen.ai/", "host": "chat.qwen.ai",
             "input": "textarea.message-input-textarea", "picker": r"^Qwen", "submit": "enter",
             "send": ".message-input-right-button-send"},
    "claude": {"url": "https://claude.ai/", "host": "claude.ai",
               "input": "[contenteditable=true]", "picker": r"(Opus|Sonnet|Haiku|Fable)",
               "submit": "enter", "send": "[data-testid=chat-input-send]",
               "answer": "[data-testid=assistant-message]"},
    "gemini": {"url": "https://gemini.google.com/", "host": "gemini.google.com",
               "input": ".ql-editor", "picker": r"^(Pro|Flash|\d)",
               "submit": "button", "send": 'button[aria-label="Send message"]',
               "answer": ".model-response-text"},
    "grok": {"url": "https://grok.com/", "host": "grok.com",
             "input": "[contenteditable=true]", "picker": r"^(Auto|Fast|Expert|Build|Heavy)",
             "submit": "enter", "answer": "[data-testid=assistant-message]"},
    "zai": {"url": "https://chat.z.ai/", "host": "chat.z.ai",
            "input": "#chat-input", "picker": r"(Deep Think|GLM)", "submit": "enter",
            "send": "button.sendMessageButton", "answer": ".chat-assistant .markdown-prose"},
    "deepseek": {"url": "https://chat.deepseek.com/", "host": "chat.deepseek.com",
                 "input": "textarea", "picker": None, "submit": "enter",
                 "answer": ".ds-assistant-message-main-content"},
    "kimi": {"url": "https://www.kimi.ai/", "host": "kimi", "input": "[contenteditable=true]",
             "picker": None, "submit": "button", "send": ".send-button-container",
             # the last markdown block that isn't the "thinking" tool-call pane
             "answer": ".markdown-container:not(.toolcall-content-text)"},
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

    def eval(self, tab_id: int, code: str, timeout: int = 60):
        return self._post("/api/browser/eval", {"tab_id": tab_id, "code": code}, timeout).get("result")

    def activate(self, tab_id: int):
        return self._post("/api/browser/activate_tab", {"tab_id": tab_id})

    def click(self, tab_id: int, x: int, y: int):
        return self._post("/api/browser/click", {"tab_id": tab_id, "x": x, "y": y})

    def type(self, tab_id: int, text: str, selector: str):
        return self._post("/api/browser/type", {"tab_id": tab_id, "text": text, "selector": selector})

    def key(self, tab_id: int, key: str, modifiers: int = 0):
        return self._post("/api/browser/key", {"tab_id": tab_id, "key": key, "modifiers": modifiers})


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
    send = SITES[site].get("send")
    if send:
        # Click the site's own send control. Some editors (Claude's ProseMirror)
        # turn the API's Enter key into a newline instead of submitting.
        js = ("Array.from(document.querySelectorAll(" + json.dumps(send) + "))"
              ".filter(e=>e.offsetParent&&!e.disabled&&e.getAttribute('aria-disabled')!=='true').pop()")
        for _ in range(10):  # the button may enable only after input lands
            pos = browser.eval(tab_id, _center_js(js))
            if pos != "none":
                x, y = json.loads(pos).values()
                browser.click(tab_id, x, y)
                return
            time.sleep(0.5)
        raise RuntimeError(f"{site}: send control {send!r} not found or disabled")
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


# Prompts longer than this are pasted in one step. The browser's type
# endpoint sends one trusted key event per character, so a multi-KB prompt
# blocks the tab for minutes (and the helper's 60s HTTP calls time out).
PASTE_THRESHOLD = 400
CTRL = 2  # /api/browser/key modifier bitmask: Shift=1, Ctrl=2, Alt=4, Meta=8


def _composer_len(browser: Browser, site: str, tab_id: int) -> int:
    sel = json.dumps(SITES[site]["input"])
    n = browser.eval(tab_id, "(()=>{const e=document.querySelector(" + sel + ");"
                     "return e?String((e.value!==undefined?e.value:e.innerText||'').trim().length):'-1';})()")
    return int(n or -1)


CHALLENGE_RE = (r"slide to verify|drag the slider|verify you are human|are you a robot|"
                r"complete the verification|captcha|checking your browser|cf-challenge")
VNC_URL = "http://pibox:6080/vnc.html"


def _check_challenge(browser: Browser, site: str, tab_id: int, timeout: int = 60):
    """Stop (never solve) when the site shows a human-verification challenge."""
    hit = browser.eval(tab_id, "(()=>{const m=(document.body.innerText||'').match(/" + CHALLENGE_RE +
                       "/i);return m?m[0]:'';})()", timeout)
    if hit:
        raise RuntimeError(f"{site}: the site is showing a human-verification challenge ({hit!r}). "
                           f"A person must solve it in the browser ({VNC_URL}); then retry.")


def _dismiss_popups(browser: Browser, site: str, tab_id: int):
    """Close announcement pop-ups that cover the composer (e.g. Z.ai "New model").
    Acts only when the composer is actually covered, and only clicks a visible,
    on-top element labelled close/dismiss."""
    sel = json.dumps(SITES[site]["input"])
    covered_js = ("(()=>{const e=document.querySelector(" + sel + ");if(!e)return 'n';const r=e.getBoundingClientRect();"
                  "const t=document.elementFromPoint(r.left+Math.min(20,r.width/2),r.top+r.height/2);"
                  "return t&&!e.contains(t)&&!t.contains(e)?'y':'n';})()")
    close_js = ("Array.from(document.querySelectorAll('button,[role=button]')).find(e=>{"
                "const l=((e.getAttribute('aria-label')||'')+' '+(typeof e.className==='string'?e.className:'')).toLowerCase();"
                "if(!/\\bclose\\b|dismiss/.test(l))return false;const r=e.getBoundingClientRect();if(r.width<8)return false;"
                "const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return t&&(e===t||e.contains(t));})")
    for _ in range(3):
        if browser.eval(tab_id, covered_js) != "y":
            return
        pos = browser.eval(tab_id, _center_js(close_js))
        if pos == "none":
            return
        x, y = json.loads(pos).values()
        browser.click(tab_id, x, y)
        time.sleep(1)


def _set_js(selector: str, text: str) -> str:
    """Put ``text`` into the composer: native value setter + input event for
    <textarea>/<input> (keystrokes may not reach them), a paste event for
    contenteditable editors (Lexical/ProseMirror/Quill handle paste)."""
    return ("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");if(!e)return 'none';e.focus();"
            "if(e.tagName==='TEXTAREA'||e.tagName==='INPUT'){"
            "const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;"
            "Object.getOwnPropertyDescriptor(proto,'value').set.call(e," + json.dumps(text) + ");"
            "e.dispatchEvent(new Event('input',{bubbles:true}));return 'set';}"
            "const dt=new DataTransfer();dt.setData('text/plain'," + json.dumps(text) + ");"
            "e.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));"
            "return 'paste';})()")


def _clear_composer(browser: Browser, site: str, tab_id: int):
    """Empty the composer with trusted Ctrl+A / Backspace (editors like Lexical
    ignore execCommand('delete'))."""
    sel = json.dumps(SITES[site]["input"])
    browser.eval(tab_id, "(()=>{const e=document.querySelector(" + sel + ");if(e)e.focus();return 'ok';})()")
    if _composer_len(browser, site, tab_id) > 0:
        is_field = browser.eval(tab_id, "(()=>{const e=document.querySelector(" + sel + ");"
                                "return e&&(e.tagName==='TEXTAREA'||e.tagName==='INPUT')?'y':'n';})()")
        if is_field == "y":
            browser.eval(tab_id, _set_js(SITES[site]["input"], ""))
        else:
            browser.key(tab_id, "a", CTRL)
            browser.key(tab_id, "Backspace")
        time.sleep(0.5)


def _insert(browser: Browser, site: str, tab_id: int, text: str):
    """Type short prompts (trusted key events); paste long ones in one step."""
    selector = SITES[site]["input"]
    if len(text) <= PASTE_THRESHOLD:
        browser.type(tab_id, text, selector)
        time.sleep(0.5)
        if _composer_len(browser, site, tab_id) >= len(text.strip()) * 0.9:
            return
        # Keystrokes went elsewhere (focus stayed on a button, e.g. Z.ai): set the
        # text directly instead.
    js = _set_js(selector, text)
    browser.eval(tab_id, js)
    time.sleep(1)
    got, want = _composer_len(browser, site, tab_id), len(text.strip())
    if got < want * 0.9:
        # Some editors (Gemini's Quill) ignore synthetic paste; insertText works.
        browser.eval(tab_id, "(()=>{const e=document.querySelector(" + json.dumps(selector) + ");e.focus();"
                     "document.execCommand('selectAll');document.execCommand('insertText',false," +
                     json.dumps(text) + ");return 'ok';})()")
        time.sleep(1)
        got = _composer_len(browser, site, tab_id)
    if got < want * 0.9:
        raise RuntimeError(f"{site}: paste landed {got} of {want} chars in the composer; not submitting")


def _answer_js(selector: str) -> str:
    """JSON {count, text} for the last answer element; <pre> blocks come back as
    fenced markdown (```lang) so code survives extraction."""
    sel = json.dumps(selector)
    return ("(()=>{const all=document.querySelectorAll(" + sel + ");const a=all[all.length-1];"
            "if(!a)return JSON.stringify({count:0,text:''});let t=a.innerText;"
            "for(const pre of a.querySelectorAll('pre')){const c=pre.querySelector('code')||pre;"
            "const m=/language-([\\w+-]+)/.exec(c.className||'');"
            "t=t.replace(pre.innerText,'\\n```'+(m?m[1]:'')+'\\n'+c.innerText.replace(/\\n$/,'')+'\\n```\\n');}"
            "return JSON.stringify({count:all.length,text:t});})()")


def _wait_answer(browser: Browser, tab_id: int, selector: str, before: int, timeout: int,
                 min_chars: int = 0) -> str:
    """Poll until a new answer element exists and its text is stable for 4 polls.

    min_chars guards against a short INTERIM message being mistaken for the answer:
    Perplexity emits "I'll research the primary sources first..." as a complete-looking
    paragraph that then sits unchanged for many seconds while it works, which satisfies
    the stability check and returns a stub. Requiring a minimum length lets the poll ride
    that out instead.
    """
    deadline = time.time() + timeout
    last, stable = None, 0
    while time.time() < deadline:
        time.sleep(3)
        try:  # a busy page (long streaming answer) can stall one eval; keep polling
            _check_challenge(browser, "site", tab_id, timeout=20)
            st = json.loads(browser.eval(tab_id, _answer_js(selector), timeout=20) or '{"count":0,"text":""}')
        except OSError:
            continue
        text = st["text"].strip()
        if st["count"] > before and text and text == last and len(text) >= min_chars:
            stable += 1
            if stable >= 4:
                return text
        else:
            stable = 0
        last = text
    return last or ""


def ask(browser: Browser, site: str, prompt: str, model: str | None = None,
        picker_label: str | None = None, timeout: int = 120, new: bool = False) -> str:
    tab_id = ensure_tab(browser, site)
    if new:
        browser._post("/api/browser/navigate", {"tab_id": tab_id, "url": SITES[site]["url"]})
        sel = json.dumps(SITES[site]["input"])
        # Wait for the load to finish first: evaluating JS mid-navigation can
        # block the browser API until the HTTP timeout (seen on Qwen).
        for _ in range(30):
            time.sleep(1)
            if not {t["id"]: t for t in browser.tabs()}.get(tab_id, {}).get("loading", False):
                break
        for _ in range(30):  # then wait for the fresh composer
            try:
                if browser.eval(tab_id, "document.querySelector(" + sel + ")?'y':'n'", timeout=10) == "y":
                    break
            except OSError:  # includes socket timeouts: page still settling
                pass
            time.sleep(1)
        time.sleep(2)  # let the composer toolbar (model picker) render
    _check_challenge(browser, site, tab_id)
    _dismiss_popups(browser, site, tab_id)
    if model:
        select_model(browser, site, model, picker_label)
    _clear_composer(browser, site, tab_id)
    _insert(browser, site, tab_id, prompt)
    time.sleep(1)
    answer_sel = SITES[site].get("answer")
    if answer_sel:
        before = json.loads(browser.eval(tab_id, _answer_js(answer_sel)) or '{"count":0}')["count"]
        _submit(browser, site, tab_id)
        # A long prompt invites a multi-thousand-character answer; don't return a stub
        # just because it is under this floor. Never a reason to return early.
        return _wait_answer(browser, tab_id, answer_sel, before, timeout, min_chars=300)
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
    prompt = args.prompt
    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            prompt = f.read()
    if not prompt:
        raise RuntimeError("pass --prompt or --prompt-file")
    answer = ask(browser, args.site, prompt, args.model, args.picker_label, args.timeout, args.new)
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
    p_ask.add_argument("--prompt", default=None)
    p_ask.add_argument("--prompt-file", default=None,
                       help="read the prompt from a file (long prompts are pasted, not typed)")
    p_ask.add_argument("--new", action="store_true",
                       help="start a fresh thread on the site before asking")
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
