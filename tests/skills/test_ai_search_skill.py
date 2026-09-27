"""Tests for the ai-search skill (AI chat sites + model selection)."""
import importlib.util
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "web" / "ai-search"
SKILL_PATH = SKILL_DIR / "SKILL.md"
SCRIPT_PATH = SKILL_DIR / "scripts" / "openmind_ai_search.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("openmind_ai_search", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frontmatter_and_body():
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert content.startswith("---")
    m = re.search(r"\n---\s*\n", content[3:])
    assert m, "frontmatter must close with ---"
    fm = yaml.safe_load(content[3 : m.start() + 3])
    body = content[m.end() + 3 :]
    return fm, body


def test_skill_file_exists():
    assert SKILL_PATH.is_file()


def test_script_file_exists():
    assert SCRIPT_PATH.is_file()


def test_frontmatter_required_fields():
    fm, _ = _frontmatter_and_body()
    for field in ("name", "description", "version", "author", "license", "platforms"):
        assert field in fm, f"missing frontmatter field: {field}"
    assert fm["name"] == "ai-search"


def test_description_hardline():
    fm, _ = _frontmatter_and_body()
    desc = fm["description"]
    assert len(desc) <= 60, f"description is {len(desc)} chars; hardline is 60"
    assert desc.endswith(".")


def test_author_credits_human_first():
    fm, _ = _frontmatter_and_body()
    assert not fm["author"].startswith("Hermes Agent")
    assert "bperris" in fm["author"]


def test_related_skills_resolve_in_repo():
    fm, _ = _frontmatter_and_body()
    for name in fm["metadata"]["hermes"]["related_skills"]:
        hits = (
            list(REPO_ROOT.glob(f"skills/*/{name}/SKILL.md"))
            + list(REPO_ROOT.glob(f"optional-skills/*/{name}/SKILL.md"))
            + list(REPO_ROOT.glob(f"skills/*/*/{name}/SKILL.md"))
        )
        assert hits, f"related_skills entry does not resolve in-repo: {name}"


def test_no_machine_local_paths():
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert "/home/" not in content


def test_documents_model_selection():
    _, body = _frontmatter_and_body()
    assert "model" in body.lower()
    for site in ("Perplexity", "Kimi", "Grok", "Gemini"):
        assert site in body, f"skill must list {site}"
    assert "picker" in body.lower()


def test_forbids_gateway_substitution():
    _, body = _frontmatter_and_body()
    assert "gateway" in body.lower()
    assert "substitute" in body.lower()


def test_uses_native_tools_and_helper():
    _, body = _frontmatter_and_body()
    for tool in ("web_search", "web_extract", "browser_navigate", "terminal"):
        assert tool in body, f"skill must reference native tool {tool}"
    assert "openmind_ai_search.py" in body


def test_procedure_steps_have_completion_criteria():
    _, body = _frontmatter_and_body()
    steps = re.findall(r"^### \d+\..*?(?=^### \d+\.|^## )", body, re.MULTILINE | re.DOTALL)
    assert len(steps) >= 4
    for step in steps:
        assert "Done when" in step, f"step missing completion criterion: {step[:60]!r}"


def test_script_exposes_known_sites():
    script = _load_script()
    for site in ("perplexity", "qwen", "claude", "gemini", "grok", "deepseek", "kimi"):
        assert site in script.SITES
    assert script.SITES["perplexity"]["url"].startswith("https://")
    assert "Kimi K3" not in script.SITES  # sites, not models, are hardcoded


def test_find_tab_matches_by_host():
    script = _load_script()

    class _Stub:
        def tabs(self):
            return [
                {"id": 3, "url": "https://chat.deepseek.com/"},
                {"id": 7, "url": "https://www.perplexity.ai/search?q=x"},
            ]

    assert script.find_tab(_Stub(), "perplexity.ai")["id"] == 7
    assert script.find_tab(_Stub(), "gemini.google.com") is None


def test_parser_ask_subcommand():
    script = _load_script()
    args = script.build_parser().parse_args(["ask", "perplexity", "--prompt", "hi"])
    assert args.cmd == "ask"
    assert args.site == "perplexity"
    assert args.prompt == "hi"
    assert args.model is None


def test_center_js_returns_coordinates_expression():
    script = _load_script()
    js = script._center_js("document.querySelector('button')")
    assert "getBoundingClientRect" in js
    assert "'none'" in js


def test_default_api_is_local_not_gateway():
    script = _load_script()
    assert "8790" in script.DEFAULT_API
    assert ":5000" not in script.DEFAULT_API
