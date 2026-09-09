from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def make_graph(tmp_path: Path):
    """Build a throwaway graph directory from a dict of node id -> node body.

    Every validator test needs a deliberately broken graph, and writing YAML by
    hand in each test buries the point of the test in boilerplate.
    """

    def _make(nodes: dict[str, dict], *, module: str = "test", imports: list[str] | None = None,
              extra_modules: dict[str, dict] | None = None) -> Path:
        root = tmp_path / "graph"

        def write_module(name: str, body: dict[str, dict], imps: list[str]) -> None:
            mdir = root / name
            mdir.mkdir(parents=True, exist_ok=True)
            (mdir / "manifest.yml").write_text(
                yaml.safe_dump({"id": name, "title": name, "imports": imps}),
                encoding="utf-8",
            )
            for node_id, data in body.items():
                payload = {"id": node_id, **data}
                (mdir / f"{node_id}.yml").write_text(
                    yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )

        write_module(module, nodes, imports or [])
        for name, body in (extra_modules or {}).items():
            write_module(name, body, [])
        return root

    return _make


def axiom(title: str = "An axiom") -> dict:
    return {"kind": "axiom", "title": title, "statement": {"natural": title}}


def theorem(title: str, steps: list[dict], **kw) -> dict:
    """A theorem node. Steps get a stable id unless the test supplies one.

    ``id`` is required by the schema, and a test that had to spell it out every
    time would be testing the schema rather than whatever it means to test.
    """
    steps = [{"id": f"s{s['n']}", **s} for s in steps]
    node = {
        "kind": "theorem",
        "title": title,
        "statement": {"natural": title},
        "proof": {"steps": steps},
        "provenance": {"source": "test"},
    }
    node.update(kw)
    return node


@pytest.fixture
def p2m_repo(tmp_path: Path) -> Path:
    """A miniature Prove2Me corpus following the upstream file conventions."""
    from p2m_fixture import write_corpus
    return write_corpus(tmp_path / "mini-corpus")


@pytest.fixture
def p2m_repo_with_sorry(tmp_path: Path) -> Path:
    from p2m_fixture import add_sorry, write_corpus
    root = write_corpus(tmp_path / "mini-corpus-sorry")
    add_sorry(root)
    return root
