"""The prose is part of the artefact, so its internal links are checked too.

A repository whose README promises docs/RISKS.md and does not ship it has told
its first prospective contributor exactly how much care to expect.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import REPO_ROOT

# [text](target) — capture the target, ignoring images and reference-style links.
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")

SKIP_PREFIXES = ("http://", "https://", "mailto:", "#", "<")


def markdown_files() -> list[Path]:
    return [
        p for p in REPO_ROOT.rglob("*.md")
        if ".git" not in p.parts and "build" not in p.parts and "node_modules" not in p.parts
    ]


def test_there_are_markdown_files_to_check():
    assert markdown_files(), "expected documentation in the repository"


def test_every_relative_link_in_the_docs_resolves():
    broken: list[str] = []
    for md in markdown_files():
        text = md.read_text(encoding="utf-8")
        for target in LINK.findall(text):
            target = target.strip()
            if target.startswith(SKIP_PREFIXES):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:            # pure anchor
                continue
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                rel = md.relative_to(REPO_ROOT)
                broken.append(f"{rel} -> {target}")
    assert not broken, "broken relative links:\n  " + "\n  ".join(broken)


def test_readme_promises_only_documents_that_exist():
    """The README is the front door; every doc it names must be shipped."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("docs/SPEC.md", "docs/PRIOR-ART.md", "docs/RISKS.md",
                 "CONTRIBUTING.md", "LICENSE", "LICENSE-CONTENT"):
        assert name in readme, f"README should point at {name}"
        assert (REPO_ROOT / name).exists(), f"README promises {name}, which does not exist"


def test_anchors_referenced_across_documents_exist():
    """Cross-document anchors like RISKS.md#overclaiming must have a heading.

    GitHub derives an anchor from each heading; this checks the ones we link to
    are actually derivable, so a rename does not silently produce a dead link.
    """
    def anchors_of(path: Path) -> set[str]:
        found = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                slug = re.sub(r"[^a-z0-9\s-]", "", title.lower()).strip()
                found.add(re.sub(r"\s+", "-", slug))
            # explicit <a id="..."> targets count too
            found |= set(re.findall(r'<a id="([^"]+)"', line))
        return found

    broken: list[str] = []
    for md in markdown_files():
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            target = target.strip()
            if target.startswith(SKIP_PREFIXES) or "#" not in target:
                continue
            path_part, anchor = target.split("#", 1)
            if not path_part or not anchor:
                continue
            resolved = (md.parent / path_part).resolve()
            if resolved.exists() and resolved.suffix == ".md":
                if anchor not in anchors_of(resolved):
                    broken.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "links to headings that do not exist:\n  " + "\n  ".join(broken)
