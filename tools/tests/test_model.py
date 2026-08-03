"""The data model: what counts as an edge, and what the graph queries mean."""

from __future__ import annotations

from proofweb.model import Graph, Node, Step, classify_token


def test_local_tokens_do_not_become_edges():
    assert classify_token("A1") == ("node", "A1")
    assert classify_token("s3") == ("step", "3")
    assert classify_token("hyp") == ("hyp", None)
    assert classify_token("hyp:comm") == ("hyp", "comm")
    assert classify_token("assumption") == ("assumption", None)


def test_edges_are_derived_from_steps_and_remember_the_step():
    node = Node(
        id="T1", kind="theorem", title="t", statement_natural="s",
        context=("A1",),
        steps=(
            Step(n=1, claim="c1", by=("A1", "hyp")),
            Step(n=2, claim="c2", by=("A2", "s1")),
            Step(n=3, claim="c3", by=("A2",)),
        ),
    )
    proof = sorted((e.dst, e.step) for e in node.edges() if e.kind == "proof")
    assert proof == [("A1", 1), ("A2", 2), ("A2", 3)]

    vocab = [(e.dst, e.step) for e in node.edges() if e.kind == "vocabulary"]
    assert vocab == [("A1", None)]

    # The same dependency used at two steps yields two edges but one dependency.
    assert node.proof_deps() == {"A1", "A2"}


def _chain() -> Graph:
    """A1 <- T1 <- T2, plus an unused axiom A2."""
    return Graph([
        Node(id="A1", kind="axiom", title="a1", statement_natural=""),
        Node(id="A2", kind="axiom", title="a2", statement_natural=""),
        Node(id="T1", kind="theorem", title="t1", statement_natural="",
             steps=(Step(n=1, claim="", by=("A1",)),)),
        Node(id="T2", kind="theorem", title="t2", statement_natural="",
             steps=(Step(n=1, claim="", by=("T1",)),)),
    ])


def test_ancestors_descendants_and_depth():
    g = _chain()
    assert g.ancestors("T2") == {"T1", "A1"}
    assert g.descendants("A1") == {"T1", "T2"}
    assert g.depth("A1") == 0
    assert g.depth("T1") == 1
    assert g.depth("T2") == 2
    assert g.layers() == {0: ["A1", "A2"], 1: ["T1"], 2: ["T2"]}


def test_roots_are_the_frontier_and_leaves_are_the_assumptions():
    g = _chain()
    assert g.roots() == ["A2", "T2"]
    assert g.leaves() == ["A1", "A2"]


def test_cycles_are_found_and_depth_reports_minus_one_on_them():
    g = Graph([
        Node(id="T1", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, claim="", by=("T2",)),)),
        Node(id="T2", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, claim="", by=("T1",)),)),
    ])
    cycles = g.cycles()
    assert cycles, "a two-node cycle must be reported"
    assert set(cycles[0]) == {"T1", "T2"}
    assert g.depth("T1") == -1


def test_ancestors_terminate_on_a_cycle():
    g = Graph([
        Node(id="T1", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, claim="", by=("T2",)),)),
        Node(id="T2", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, claim="", by=("T1",)),)),
    ])
    assert g.ancestors("T1") == {"T1", "T2"}


def test_duplicate_ids_are_recorded_not_silently_dropped():
    a = Node(id="X", kind="axiom", title="", statement_natural="", source_path="one.yml")
    b = Node(id="X", kind="axiom", title="", statement_natural="", source_path="two.yml")
    g = Graph([a, b])
    assert len(g) == 1
    assert g.duplicate_ids == [("X", "one.yml", "two.yml")]


def test_hypothesis_names_are_parsed_off_the_declaration():
    node = Node(id="T", kind="theorem", title="", statement_natural="",
                hypotheses=("comm: a·b = b·a", "bare"))
    assert node.hypothesis_names == ["comm", "bare"]
