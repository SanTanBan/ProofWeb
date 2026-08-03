"""The pilot module is the project's claim about itself. It must stay clean.

If elementary group theory cannot survive the validator, nothing harder will.
"""

from __future__ import annotations

import json

from conftest import REPO_ROOT
from proofweb.render import explain, summarise, to_dot, to_json, to_mermaid
from proofweb.validate import validate

GRAPH = REPO_ROOT / "graph"


def test_the_shipped_graph_validates_with_no_findings_at_all():
    _, report = validate(GRAPH)
    assert report.ok(strict=True), "\n".join(str(f) for f in report.findings)


def test_the_pilot_has_the_expected_shape():
    graph, _ = validate(GRAPH)
    kinds = {}
    for node in graph:
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    assert kinds == {"axiom": 4, "background": 2, "theorem": 8}
    assert graph.layers(("proof",))[0] == ["A1", "A2", "A3", "A4", "L1", "L2"]


def test_every_theorem_rests_only_on_the_module_and_bottoms_out_in_axioms():
    graph, _ = validate(GRAPH)
    assumptions = {n.id for n in graph if not n.is_theorem}
    for node in graph:
        if not node.is_theorem:
            continue
        ancestors = graph.ancestors(node.id, ("proof",))
        assert ancestors, f"{node.id} rests on nothing"
        assert ancestors & assumptions, f"{node.id} never reaches an axiom"
        assert ancestors <= set(graph.nodes), f"{node.id} escapes the module"


def test_uniqueness_of_inverses_is_used_where_it_should_be():
    """T4 is the hinge of the module: three later theorems turn on it.

    This is the assertion the graph exists to make, so it is worth a test — if a
    future edit silently drops the citation, this fails.
    """
    graph, _ = validate(GRAPH)
    assert graph.descendants("T4", ("proof",)) >= {"T5", "T6", "T7"}
    t6 = graph.get("T6")
    steps_using_t4 = [e.step for e in t6.edges() if e.dst == "T4" and e.kind == "proof"]
    assert steps_using_t4 == [12]


def test_every_node_links_to_at_least_one_proof_assistant():
    """The cross-links are what make 'verified' reachable later. Losing them
    quietly would turn the graph back into an unfalsifiable diagram."""
    graph, _ = validate(GRAPH)
    missing = [n.id for n in graph if not n.formalization]
    assert not missing, f"nodes with no formalization link: {missing}"


def test_exporters_produce_something_parseable():
    import json

    graph, _ = validate(GRAPH)

    payload = json.loads(to_json(graph))
    assert len(payload["nodes"]) == len(graph)
    assert any(e["step"] is not None for e in payload["edges"]), \
        "proof edges must carry the step that created them"

    dot = to_dot(graph)
    assert dot.startswith("digraph proofweb {") and dot.rstrip().endswith("}")
    assert 'label="step 12"' in dot

    mermaid = to_mermaid(graph)
    assert mermaid.startswith("graph BT")
    assert "T6 -- step 12 --> T4" in mermaid


def test_html_export_is_self_contained_and_carries_step_numbers():
    """The viewer must open from a file path on a machine with nothing installed."""
    import re

    from proofweb.site import to_html

    graph, _ = validate(GRAPH)
    html = to_html(graph)

    assert html.startswith("<!doctype html>")
    # No network at load time and none at run time. The XML namespace URI that
    # createElementNS needs is an identifier, not a request, so it is exempt.
    for forbidden in ("<script src=", "<link ", "<img ", "@import",
                      "fetch(", "XMLHttpRequest", "WebSocket", "import("):
        assert forbidden not in html, f"viewer must not use {forbidden}"
    stripped = html.replace("http://www.w3.org/2000/svg", "")
    assert "http://" not in stripped and "https://" not in stripped

    payload = json.loads(re.search(r"const DATA = (\{.*?\});\nconst COLOURS", html, re.S).group(1))
    assert len(payload["nodes"]) == len(graph)
    # Step 12 applies T4 to the element a·b (in G by A1) and finishes by transitivity
    # (L1). The two local tokens s1, s10, s11 correctly create no edge.
    step12 = [e for e in payload["edges"]
              if e["src"] == "T6" and e["step"] == 12]
    assert {e["dst"] for e in step12} == {"T4", "L1", "A1"}, \
        "clicking step 12 of T6 must light exactly the edges that step created"


def test_explain_reports_the_step_a_dependency_entered_at():
    graph, _ = validate(GRAPH)
    text = explain(graph, "T6")
    # Stable addresses, not ordinals: an ordinal in a citation goes stale the
    # first time somebody inserts a step.
    assert "T4     Inverses are unique — used at #conclude" in text
    assert "[T6#conclude]" in text
    assert "T2" in text and "indirectly" in text
    assert "No such node" not in text
    assert "No such node: nope" in explain(graph, "nope")


def test_every_step_of_every_proof_has_a_stable_id():
    """The one property that makes an external citation survive an edit."""
    graph, _ = validate(GRAPH)
    missing = [f"{n.id} step {s.n}" for n in graph for s in n.steps if not s.sid]
    assert not missing, f"steps with no stable id: {missing}"

    for node in graph:
        ids = [s.sid for s in node.steps]
        assert len(ids) == len(set(ids)), f"{node.id} reuses a step id"


def test_no_proof_cites_an_earlier_step_by_ordinal():
    """`s3` still resolves after an insertion — pointing at the wrong line."""
    graph, _ = validate(GRAPH)
    offenders = [f"{n.id} step {s.n}" for n in graph for s in n.steps if s.step_refs()]
    assert not offenders, f"ordinal step citations: {offenders}"


def test_summary_reports_formalization_and_review_coverage():
    graph, _ = validate(GRAPH)
    text = summarise(graph)
    assert "formalized       14/14" in text
    # The review counter must always print. Kill criterion 1 is that it is still
    # zero in six months, and a number nobody sees cannot fire a kill criterion.
    assert "reviewed         0/14" in text
    assert "checked by a second person" in text
