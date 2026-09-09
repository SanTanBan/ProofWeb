"""Importing a Prove2Me corpus: the edges, the attribution, and the honesty."""

from __future__ import annotations

import json

from proofweb.leanp2m import extract_dir, load_corpus
from proofweb.metamath import nodes_from_json, nodes_to_json
from proofweb.model import Graph


def build(root, **kw) -> tuple[Graph, dict]:
    corpus, nodes, meta = extract_dir(root, root="C_root", **kw)
    assert not corpus.problems, corpus.problems
    return Graph(nodes, meta=meta), meta


def test_corpus_parses_with_no_problems(p2m_repo):
    corpus = load_corpus(p2m_repo)
    assert set(corpus.thms) == {"A_left", "B_useLeft", "C_root", "D_dup", "E_outside"}
    assert set(corpus.sols) == set(corpus.thms)
    assert set(corpus.defs) == {"Foo"}
    assert not corpus.problems


def test_import_edges_are_exactly_the_citation_set(p2m_repo):
    """The invariant: whatever the text does, the edges are the imports."""
    graph, _ = build(p2m_repo)
    pairs = {(e.src, e.dst) for e in graph.edges("proof")}
    assert pairs == {
        ("B_useLeft", "A_left"), ("B_useLeft", "Def_Foo"),
        ("C_root", "A_left"), ("C_root", "B_useLeft"),
        ("C_root", "D_dup"), ("C_root", "Def_Foo"),
        ("E_outside", "A_left"), ("E_outside", "Def_Foo"),
    }
    # Every citation appears once, whether it was found in the text or not.
    assert graph.get("C_root").proof_deps() == {"A_left", "B_useLeft", "D_dup", "Def_Foo"}


def test_statement_parsed_from_multiline_namespaced_thm(p2m_repo):
    graph, _ = build(p2m_repo)
    a = graph.get("A_left")
    assert a.title == "A.left"                       # namespace tracked
    assert a.statement_natural == "(n : ℕ) (h : 0 < n) : n + 0 = n"
    assert a.formalization == {"lean": "A.left"}
    assert ("n: ℕ" in a.hypotheses) and ("h: 0 < n" in a.hypotheses)


def test_usage_lines_report_line_numbers_and_ignore_comments_and_attributes(p2m_repo):
    """A name in a comment or an `attribute` line is not a use of it."""
    graph, _ = build(p2m_repo)
    b = graph.get("B_useLeft")
    line_steps = [s for s in b.steps if s.sid != "imports"]
    assert len(line_steps) == 1, [s.claim for s in line_steps]
    step = line_steps[0]
    assert step.by == ("A_left",)
    assert step.claim == "exact A.left (f.x) hx"
    assert step.sid.startswith("l")
    # The comment and the attribute line both mention A.left and both are ignored.
    assert "A.left would also work" not in " ".join(s.claim for s in b.steps)
    assert "attribute [-simp]" not in " ".join(s.claim for s in b.steps)


def test_bare_name_under_open_is_attributed(p2m_repo):
    """C's proof says `left`, not `A.left`, because it opened the namespace."""
    graph, _ = build(p2m_repo)
    c = graph.get("C_root")
    bare = [s for s in c.steps if s.by == ("A_left",)]
    assert bare and bare[0].claim.startswith("exact left")
    forms = c.provenance["lean"]["hit_forms"]
    assert forms.get("bare-open", 0) >= 1
    assert forms.get("qualified", 0) >= 1               # B.useLeft was qualified


def test_unused_import_lands_on_imports_step(p2m_repo):
    """D_dup is imported by C and never named. The edge stays; the reason is recorded."""
    graph, _ = build(p2m_repo)
    c = graph.get("C_root")
    imports_step = next(s for s in c.steps if s.sid == "imports")
    assert "D_dup" in imports_step.by
    assert c.provenance["lean"]["unused_imports"] == ["D_dup"]
    assert "not attributed to a proof line" in imports_step.claim


def test_definitions_are_vocabulary_and_never_line_attributed(p2m_repo):
    """A Def module exports many names; matching them per line would say nothing."""
    graph, _ = build(p2m_repo)
    d = graph.get("Def_Foo")
    assert d.kind == "definition" and d.status == "draft"
    assert "3 declarations" in d.statement_natural
    for node_id in ("B_useLeft", "C_root", "E_outside"):
        node = graph.get(node_id)
        assert "Def_Foo" in node.context                        # vocabulary edge
        step = next(s for s in node.steps if "Def_Foo" in s.by)
        assert step.sid == "imports"                            # never a line
    assert graph.get("Def_Foo").provenance["derivation"] == "imports"


def test_status_verified_requires_tail_and_no_sorry(p2m_repo, p2m_repo_with_sorry):
    graph, _ = build(p2m_repo)
    assert all(n.status == "verified" for n in graph if n.is_theorem)

    broken, _ = build(p2m_repo_with_sorry)
    d = broken.get("D_dup")
    assert d.status == "draft"
    assert "sorry" in d.provenance["note"]
    assert broken.get("A_left").status == "verified"       # unaffected


def test_trust_none_refuses_to_inherit_someone_elses_check(p2m_repo):
    graph, _ = build(p2m_repo, trust="none")
    assert all(n.status == "draft" for n in graph if n.is_theorem)
    assert "not trusted" in graph.get("A_left").provenance["note"]


def test_provenance_names_derivation_and_checker(p2m_repo):
    """The claim this importer makes must be legible on every node."""
    graph, meta = build(p2m_repo)
    p = graph.get("B_useLeft").provenance
    assert p["derivation"] == "imports"
    assert p["step_attribution"] == "textual"
    assert "not replayed by proofweb" in p["checked_by"]
    assert "no Lean toolchain" in p["contributed_by"]
    assert p["lean"]["thm"].startswith("Theorems/Thm_B_useLeft.lean:")
    assert p["lean"]["sol"].startswith("P2M/Sol/S_B_useLeft.lean:")
    assert len(p["lean"]["sha256_sol"]) == 16
    assert meta["derivation"] == "imports" and meta["style"] == "p2m"


def test_no_usage_lines_mode_gives_the_plain_import_graph(p2m_repo):
    graph, meta = build(p2m_repo, usage_lines=False)
    assert meta["step_attribution"] == "none"
    c = graph.get("C_root")
    assert [s.sid for s in c.steps] == ["imports"]
    # Same edges, less resolution.
    assert c.proof_deps() == {"A_left", "B_useLeft", "D_dup", "Def_Foo"}


def test_landmarks_and_attribution_are_read(p2m_repo):
    graph, meta = build(p2m_repo)
    assert meta["landmarks"][:3] == ["A.left", "B.useLeft", "C.root"]
    assert "landmark" in graph.get("A_left").tags
    assert "landmark" not in graph.get("E_outside").tags


def test_graph_shape_matches_the_corpus(p2m_repo):
    graph, _ = build(p2m_repo)
    assert graph.depths()["C_root"] == 2
    assert not graph.cycles(("proof",))
    assert graph.ancestors("C_root") == {"A_left", "B_useLeft", "D_dup", "Def_Foo"}
    assert "E_outside" not in graph.ancestors("C_root")


def test_extracted_json_round_trips_with_meta(p2m_repo):
    graph, meta = build(p2m_repo)
    payload = nodes_to_json(list(graph), module="m", source="mini", meta=meta)
    text = json.dumps(payload, ensure_ascii=False)
    back = Graph(nodes_from_json(json.loads(text)), meta=json.loads(text).get("meta"))

    assert len(back) == len(graph)
    assert back.meta["derivation"] == "imports"
    a, b = graph.get("C_root"), back.get("C_root")
    assert [(s.sid, s.by, s.claim) for s in a.steps] == [(s.sid, s.by, s.claim) for s in b.steps]
    assert a.tags == b.tags and a.source_path == b.source_path
    assert sorted(str(e) for e in a.edges()) == sorted(str(e) for e in b.edges())


def test_limit_reads_a_prefix_of_the_corpus(p2m_repo):
    corpus, nodes, _ = extract_dir(p2m_repo, limit=2)
    thms = [n for n in nodes if n.is_theorem]
    assert len(thms) == 2
    assert not corpus.problems
