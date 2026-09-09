"""The audit: what it counts, and what it refuses to overstate."""

from __future__ import annotations

from proofweb.audit import audit
from proofweb.leanp2m import extract_dir
from proofweb.model import Graph


def graph_for(root, **kw) -> Graph:
    _, nodes, meta = extract_dir(root, root="C_root", **kw)
    return Graph(nodes, meta=meta)


def sect(report, title):
    return next(s for s in report.sections if s.title == title)


def test_audit_counts_what_was_read(p2m_repo):
    report = audit(graph_for(p2m_repo))
    data = sect(report, "Counts").data
    assert data["theorems"] == 5
    assert data["definitions"] == 1
    assert data["citation_pairs"] == 8
    assert data["theorem_citations"] == 5      # B->A, C->A, C->B, C->D, E->A
    assert data["definition_citations"] == 3   # B, C, E each import Def_Foo
    assert data["problems"] == 0


def test_audit_closure_separates_stranded_from_merely_uncited(p2m_repo):
    """E_outside is not reachable from the goal and nobody cites it."""
    report = audit(graph_for(p2m_repo), root="C_root")
    data = sect(report, "Closure of the goal theorem").data
    assert data["in_closure"] == 4                  # C, B, A, D
    assert data["outside"] == 1 and data["outside_ids"] == ["E_outside"]
    assert data["uncited"] == 1


def test_audit_reports_citations_never_named(p2m_repo):
    report = audit(graph_for(p2m_repo), root="C_root")
    data = sect(report, "Citations never named in the proof script").data
    assert data["unhit"] == 1
    assert data["examples"] == ["C_root -> D_dup"]


def test_audit_grades_attribution_confidence(p2m_repo):
    report = audit(graph_for(p2m_repo))
    forms = sect(report, "Confidence of line attribution").data
    assert forms.get("qualified", 0) >= 2           # A.left in B and E
    assert forms.get("bare-open", 0) >= 1           # bare `left` under `open A`


def test_audit_duplicates_exact_and_near(p2m_repo):
    report = audit(graph_for(p2m_repo), jaccard=0.9)
    data = sect(report, "Duplicate and near-duplicate statements").data
    exact = [sorted(g) for g in data["exact_groups"]]
    assert ["A_left", "D_dup"] in exact             # same theorem, renamed binders
    near = {tuple(sorted((a, b))) for a, b, _ in data["near_pairs"]}
    assert ("C_root", "E_outside") in near          # same tokens, different order


def test_audit_finds_sorry_and_demoted_nodes(p2m_repo, p2m_repo_with_sorry):
    clean = audit(graph_for(p2m_repo))
    assert sect(clean, "sorry / admit / native_decide").data["sorry"] == []

    broken = audit(graph_for(p2m_repo_with_sorry))
    data = sect(broken, "sorry / admit / native_decide").data
    assert data["sorry"] == ["D_dup"]
    assert "D_dup" in data["not_verified"]


def test_audit_reports_shape(p2m_repo):
    report = audit(graph_for(p2m_repo), root="C_root")
    data = sect(report, "Shape").data
    assert data["acyclic"] is True
    assert data["longest_chain"] == 2 and data["deepest"] == "C_root"
    top = dict(data["top_cited"])
    assert top["A_left"] == 3                       # B, C and E all cite it


def test_audit_landmarks_resolve_external_and_unresolved(p2m_repo):
    proof_path = (p2m_repo / "PROOF-PATH.md").read_text(encoding="utf-8")
    report = audit(graph_for(p2m_repo), root="C_root", proof_path_text=proof_path)
    data = sect(report, "Landmark route").data
    assert data["landmarks"] == 6
    assert data["resolved"] == 4                    # A.left, B.useLeft, C.root, Def_Foo
    assert set(data["unresolved"]) == {"Nat.add_zero", "Nope.missing"}
    assert data["outside_closure"] == []            # every landmark is load-bearing


def test_audit_markdown_states_how_edges_were_derived(p2m_repo):
    """The report must never let a reader mistake `verified` for `we checked it`."""
    text = audit(graph_for(p2m_repo), root="C_root").to_markdown()
    assert "derived by `imports`" in text
    assert "not replayed by proofweb" in text
    assert "# Corpus audit" in text


def test_audit_compares_against_published_figures(p2m_repo):
    """Given upstream numbers, every count says match or DIFFERS — no silent pass."""
    report = audit(graph_for(p2m_repo), root="C_root",
                   upstream={"theorems": 5, "definitions": 99})
    text = "\n".join(sect(report, "Counts").lines)
    assert "match" in text
    assert "DIFFERS by -98" in text
