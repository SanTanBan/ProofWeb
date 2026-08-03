"""Loading rules that are easy to get subtly wrong and hard to notice.

Both cases here were latent bugs found by review, not by failure: nothing in the
single-module pilot exercised either one.
"""

from __future__ import annotations

import yaml
from conftest import axiom, theorem
from proofweb.loader import iter_node_files, load_graph
from proofweb.validate import validate


def test_a_module_nested_inside_another_does_not_double_load(tmp_path):
    """Each file belongs to its nearest manifest, not to every manifest above it."""
    root = tmp_path / "graph"
    outer = root / "outer"
    inner = outer / "sub" / "inner"
    for d, mid in ((outer, "outer"), (inner, "inner")):
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.yml").write_text(
            yaml.safe_dump({"id": mid, "imports": []}), encoding="utf-8")

    (outer / "A1.yml").write_text(
        yaml.safe_dump({"id": "A1", **axiom("outer axiom")}), encoding="utf-8")
    (inner / "B1.yml").write_text(
        yaml.safe_dump({"id": "B1", **axiom("inner axiom")}), encoding="utf-8")

    files = iter_node_files(root)
    assert len(files) == 2, f"each node must load exactly once, got {files}"

    graph, errors = load_graph(root)
    assert not errors and not graph.duplicate_ids
    assert graph.get("B1").module == "inner", "must belong to the nearest manifest"
    assert graph.get("A1").module == "outer"


def test_yaml_suffix_is_loaded_too(tmp_path):
    """A contributor who writes .yaml should get a node, not silence."""
    root = tmp_path / "graph"
    mod = root / "m"
    mod.mkdir(parents=True)
    (mod / "manifest.yml").write_text(yaml.safe_dump({"id": "m", "imports": []}),
                                      encoding="utf-8")
    (mod / "A1.yaml").write_text(yaml.safe_dump({"id": "A1", **axiom()}), encoding="utf-8")
    (mod / "T1.yml").write_text(
        yaml.safe_dump({"id": "T1", **theorem("t", [{"n": 1, "claim": "c", "by": ["A1"]}])}),
        encoding="utf-8")

    graph, report = validate(root)
    assert "A1" in graph, ".yaml files must load"
    assert report.ok(), [str(f) for f in report.findings]


def test_a_graph_directory_outside_the_repo_loads(tmp_path):
    """`--graph DIR` may point anywhere; source paths must not raise."""
    root = tmp_path / "elsewhere"
    mod = root / "m"
    mod.mkdir(parents=True)
    (mod / "manifest.yml").write_text(yaml.safe_dump({"id": "m", "imports": []}),
                                      encoding="utf-8")
    (mod / "A1.yml").write_text(yaml.safe_dump({"id": "A1", **axiom()}), encoding="utf-8")

    graph, errors = load_graph(root)
    assert not errors
    assert graph.get("A1").source_path.endswith("A1.yml")
