"""Graph queries at the scale of an imported corpus, not the pilot.

The pilot has 14 nodes, so every complexity mistake in `model.py` is invisible
there. An imported Lean corpus has ~30,000 nodes and ~100,000 edges, chains
thousands deep, and turns two of them fatal: rebuilding the adjacency map inside
`depth()` (quadratic — measured at hours for one `stats` call) and computing
depth by recursion (RecursionError past ~1,000).

These tests fix both behaviours in place so they cannot regress.
"""

from __future__ import annotations

import time

import pytest
from proofweb.model import Graph, Node, Step


def chain(length: int, *, prefix: str = "n") -> Graph:
    """A linear dependency chain: n0 <- n1 <- ... <- n{length-1}."""
    nodes = [Node(id=f"{prefix}0", kind="axiom", title="base", statement_natural="")]
    for i in range(1, length):
        nodes.append(Node(
            id=f"{prefix}{i}", kind="theorem", title=f"t{i}", statement_natural="",
            steps=(Step(n=1, sid="only", claim="", by=(f"{prefix}{i - 1}",)),),
        ))
    return Graph(nodes)


def test_deep_chain_does_not_recurse():
    """3,000 deep: the recursive implementation raised RecursionError here."""
    g = chain(3000)
    assert g.depth("n2999") == 2999
    assert g.depth("n0") == 0
    assert len(g.topological_order()) == 3000


def test_depths_agree_with_ancestors_on_a_diamond():
    """Depth is the LONGEST path, not the shortest — a diamond proves it."""
    g = Graph([
        Node(id="A", kind="axiom", title="", statement_natural=""),
        Node(id="B", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, sid="a", claim="", by=("A",)),)),
        Node(id="C", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, sid="a", claim="", by=("B",)),)),
        # D depends on both the short arm (A) and the long arm (C).
        Node(id="D", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, sid="a", claim="", by=("A", "C")),)),
    ])
    assert g.depths() == {"A": 0, "B": 1, "C": 2, "D": 3}
    assert g.ancestors("D") == {"A", "B", "C"}
    assert g.closure_sizes()["D"] == 3


def test_nodes_on_a_cycle_report_depth_minus_one():
    g = Graph([
        Node(id="X", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, sid="a", claim="", by=("Y",)),)),
        Node(id="Y", kind="theorem", title="", statement_natural="",
             steps=(Step(n=1, sid="a", claim="", by=("X",)),)),
        Node(id="Z", kind="axiom", title="", statement_natural=""),
    ])
    assert g.depth("X") == -1 and g.depth("Y") == -1
    assert g.depth("Z") == 0
    assert "X" not in g.topological_order()
    # Falls back to ancestors(), which on a cycle includes X itself: X -> Y -> X.
    assert g.closure_sizes()["X"] == 2
    assert g.closure_sizes()["Z"] == 0


def test_cached_adjacency_is_not_shared_mutable():
    """`adjacency()` hands out a copy; mutating it must not corrupt the graph."""
    g = chain(5)
    adj = g.adjacency()
    adj["n1"].add("bogus")
    adj["n0"].add("also-bogus")
    assert g.ancestors("n1") == {"n0"}
    assert g.adjacency()["n1"] == {"n0"}


def test_shortest_path_and_no_path():
    g = chain(6)
    assert g.shortest_path("n5", "n0") == ["n5", "n4", "n3", "n2", "n1", "n0"]
    assert g.shortest_path("n0", "n5") is None      # edges point at dependencies
    assert g.shortest_path("n3", "n3") == ["n3"]
    assert g.shortest_path("n3", "nope") is None


def test_neighbourhood_radius_direction_and_truncation():
    g = chain(10)
    ids, truncated = g.neighbourhood("n5", radius=2)
    assert ids == {"n3", "n4", "n5", "n6", "n7"} and not truncated

    down, _ = g.neighbourhood("n5", radius=2, direction="down")
    assert down == {"n3", "n4", "n5"}

    up, _ = g.neighbourhood("n5", radius=2, direction="up")
    assert up == {"n5", "n6", "n7"}

    small, truncated = g.neighbourhood("n5", radius=9, max_nodes=4)
    assert truncated and len(small) == 4


def test_subgraph_keeps_out_of_view_citations():
    """A citation leaving the view stays in `by` — hiding it would lie about the proof."""
    g = chain(5)
    sub = g.subgraph(["n2", "n3", "n4"])
    assert len(sub) == 3
    assert sub.get("n2").steps[0].by == ("n1",)     # n1 is outside the view
    assert sub.ancestors("n4") == {"n3", "n2"}      # but induces no edge
    assert sub.depths()["n2"] == 0                  # depth is recomputed in-view


def test_meta_is_carried_and_defaults_empty():
    assert Graph([]).meta == {}
    g = Graph([], meta={"corpus": "flt", "commit": "abc"})
    assert g.meta["corpus"] == "flt"
    assert g.subgraph([]).meta == g.meta


@pytest.mark.parametrize("n_nodes,fanout", [(6000, 3)])
def test_full_report_over_a_large_graph_is_fast(n_nodes, fanout):
    """The regression guard: `depths` once, not once per node.

    Before caching, `layers()` on this graph rebuilt adjacency 6,000 times. The
    threshold is deliberately loose (CI machines vary); the old code missed it by
    two orders of magnitude, not by a few percent.
    """
    nodes = [Node(id="n0", kind="axiom", title="", statement_natural="")]
    for i in range(1, n_nodes):
        deps = tuple(f"n{max(0, i - 1 - k)}" for k in range(min(fanout, i)))
        nodes.append(Node(
            id=f"n{i}", kind="theorem", title="", statement_natural="",
            steps=(Step(n=1, sid="only", claim="", by=deps),),
        ))
    g = Graph(nodes)

    start = time.perf_counter()
    layers = g.layers()
    sizes = g.closure_sizes()
    elapsed = time.perf_counter() - start

    assert sum(len(v) for v in layers.values()) == n_nodes
    assert sizes[f"n{n_nodes - 1}"] == n_nodes - 1
    assert elapsed < 10.0, f"layers+closure_sizes took {elapsed:.1f}s"


def test_stats_stays_readable_at_corpus_scale():
    """A layer of a real corpus holds thousands of names; `stats` printed all of
    them, 1.1 MB for the FLT corpus. Each list is now capped and counted."""
    from proofweb.render import summarise
    from proofweb.model import Graph, Node
    leaves = [Node(id=f"L{i}", kind="axiom", title=f"L{i}", statement_natural="x")
              for i in range(500)]
    text = summarise(Graph(leaves))
    assert "(+492 more)" in text
    assert len(text) < 2000


def test_stats_summarises_the_middle_of_a_deep_graph():
    from proofweb.render import summarise
    text = summarise(chain(40))
    assert "30 more layers (depths 5-34)" in text
    assert "depth 39" in text and "depth 20 " not in text
