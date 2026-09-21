"""Tests for the annas-archive skill."""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "research" / "annas-archive" / "SKILL.md"


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


def test_frontmatter_required_fields():
    fm, _ = _frontmatter_and_body()
    for field in ("name", "description", "version", "author", "license", "platforms"):
        assert field in fm, f"missing frontmatter field: {field}"
    assert fm["name"] == "annas-archive"


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


def test_browser_first_flow():
    _, body = _frontmatter_and_body()
    assert "browser_navigate" in body, "skill must drive the browser for AA pages"
    assert "slow_download" in body, "skill must use free slow downloads"
    assert "curl" in body, "skill must download the file with curl"


def test_no_tor():
    _, body = _frontmatter_and_body()
    assert "Tor" in body, "skill must explain why Tor is not used"
    assert "9050" not in body, "skill must not reference the Tor SOCKS port"


def test_flow_covers_search_to_download():
    _, body = _frontmatter_and_body()
    assert "/search?q=" in body
    assert "/md5/" in body
    assert "Download now" in body


def test_steps_have_completion_criteria():
    _, body = _frontmatter_and_body()
    steps = re.findall(r"^### \d+\..*?(?=^### \d+\.|^## )", body, re.MULTILINE | re.DOTALL)
    assert len(steps) >= 5
    for step in steps:
        assert "Done when" in step, f"step missing completion criterion: {step[:60]!r}"


def test_ddos_guard_pitfall_documented():
    _, body = _frontmatter_and_body()
    assert "DDoS-Guard" in body
    assert "403" in body, "skill must warn that curl on AA pages gets 403"