"""Each validator check must fire on exactly the graph it is meant to catch.

A validator nobody tests is a validator that quietly stops working, and then the
graph's guarantees are worth nothing.
"""

from __future__ import annotations

from conftest import axiom, theorem
from proofgraph.validate import validate


def codes(report) -> set[str]:
    return {f.code for f in report.findings}


def test_dangling_reference_is_an_error(make_graph):
    root = make_graph({
        "A1": axiom(),
        "T1": theorem("t", [{"n": 1, "claim": "c", "by": ["A1", "A99"]}]),
    })
    _, report = validate(root)
    assert "ref.dangling" in codes(report)
    assert not report.ok()


def test_forward_step_reference_is_an_error(make_graph):
    root = make_graph({
        "A1": axiom(),
        "T1": theorem("t", [
            {"n": 1, "claim": "c", "by": ["s2"]},
            {"n": 2, "claim": "d", "by": ["A1"]},
        ]),
    })
    _, report = validate(root)
    assert "step.forward-reference" in codes(report)


def test_step_may_not_cite_itself(make_graph):
    root = make_graph({
        "A1": axiom(),
        "T1": theorem("t", [{"n": 1, "claim": "c", "by": ["A1", "s1"]}]),
    })
    _, report = validate(root)
    assert "step.forward-reference" in codes(report)


def test_step_numbering_must_be_contiguous(make_graph):
    root = make_graph({
        "A1": axiom(),
        "T1": theorem("t", [
            {"n": 1, "claim": "c", "by": ["A1"]},
            {"n": 3, "claim": "d", "by": ["A1"]},
        ]),
    })
    _, report = validate(root)
    assert "step.numbering" in codes(report)


def test_cycle_between_theorems_is_an_error(make_graph):
    root = make_graph({
        "T1": theorem("t1", [{"n": 1, "claim": "c", "by": ["T2"]}]),
        "T2": theorem("t2", [{"n": 1, "claim": "c", "by": ["T1"]}]),
    })
    _, report = validate(root)
    assert "graph.cycle" in codes(report)


def test_undeclared_hypothesis_is_an_error(make_graph):
    root = make_graph({
        "A1": axiom(),
        "T1": theorem("t", [{"n": 1, "claim": "c", "by": ["A1", "hyp:nope"]}]),
    })
    _, report = validate(root)
    assert "hyp.undeclared" in codes(report)


def test_bare_hyp_is_ambiguous_when_several_are_declared(make_graph):
    node = theorem("t", [{"n": 1, "claim": "c", "by": ["A1", "hyp"]}])
    node["proof"]["hypotheses"] = ["one: x", "two: y"]
    root = make_graph({"A1": axiom(), "T1": node})
    _, report = validate(root)
    assert "hyp.ambiguous" in codes(report)


def test_unused_hypothesis_is_a_warning_not_an_error(make_graph):
    node = theorem("t", [{"n": 1, "claim": "c", "by": ["A1"]}])
    node["proof"]["hypotheses"] = ["spare: unused"]
    root = make_graph({"A1": axiom(), "T1": node})
    _, report = validate(root)
    assert "hyp.unused" in codes(report)
    assert report.ok()          # coherent, just suspicious
    assert not report.ok(strict=True)


def test_axiom_carrying_a_proof_is_rejected(make_graph):
    bad = axiom()
    bad["proof"] = {"steps": [{"n": 1, "claim": "c", "by": ["A2"]}]}
    root = make_graph({"A1": bad, "A2": axiom()})
    _, report = validate(root)
    assert "kind.unexpected-proof" in codes(report) or "schema.invalid" in codes(report)


def test_verified_status_needs_a_formalization(make_graph):
    node = theorem("t", [{"n": 1, "claim": "c", "by": ["A1"]}], status="verified")
    root = make_graph({"A1": axiom(), "T1": node})
    _, report = validate(root)
    assert "status.unbacked" in codes(report)
    assert not report.ok()


def test_verified_status_with_a_formalization_passes(make_graph):
    node = theorem("t", [{"n": 1, "claim": "c", "by": ["A1"]}],
                   status="verified", formalization={"lean": "mul_assoc"})
    root = make_graph({"A1": axiom(), "T1": node})
    _, report = validate(root)
    assert "status.unbacked" not in codes(report)


def test_citing_another_module_without_importing_it_is_an_error(make_graph):
    root = make_graph(
        {"T1": theorem("t", [{"n": 1, "claim": "c", "by": ["B1"]}])},
        module="alpha",
        imports=[],
        extra_modules={"beta": {"B1": axiom()}},
    )
    _, report = validate(root)
    assert "module.undeclared-import" in codes(report)


def test_declaring_the_import_makes_the_cross_module_citation_legal(make_graph):
    root = make_graph(
        {"T1": theorem("t", [{"n": 1, "claim": "c", "by": ["B1"]}])},
        module="alpha",
        imports=["beta"],
        extra_modules={"beta": {"B1": axiom()}},
    )
    _, report = validate(root)
    assert "module.undeclared-import" not in codes(report)


def test_unused_axiom_is_flagged(make_graph):
    root = make_graph({
        "A1": axiom("used"),
        "A2": axiom("never cited"),
        "T1": theorem("t", [{"n": 1, "claim": "c", "by": ["A1"]}]),
    })
    _, report = validate(root)
    unused = [f for f in report.findings if f.code == "graph.unused-assumption"]
    assert [f.node for f in unused] == ["A2"]


def test_theorem_citing_nothing_is_flagged_as_disconnected(make_graph):
    node = theorem("t", [{"n": 1, "claim": "c", "by": ["hyp:h"]}])
    node["proof"]["hypotheses"] = ["h: something"]
    root = make_graph({"T1": node})
    _, report = validate(root)
    assert "kind.self-contained" in codes(report)


def test_malformed_yaml_is_reported_not_raised(make_graph):
    root = make_graph({"A1": axiom()})
    (root / "test" / "broken.yml").write_text("id: X\nkind: [unclosed\n", encoding="utf-8")
    _, report = validate(root)
    assert "load.failed" in codes(report)
