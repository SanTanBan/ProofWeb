"""Against the real corpus: does this importer read what its authors read?

Skipped unless the corpus has been fetched (see docs/FORMAL-TRACK.md), so CI and
contributors without 700 MB to spare are unaffected.

These are the only tests in the project whose expected values were written by
somebody else. Anthropic published figures about their own Fermat's Last Theorem
corpus, computed by their own text-only generator; reproducing them to the unit
means two independently written parsers agree about 13 million lines of Lean.
Nothing else available would establish that.
"""

from __future__ import annotations

import pytest
from conftest import REPO_ROOT
from proofweb.leanp2m import extract_dir
from proofweb.model import Graph

CORPUS = REPO_ROOT / "corpora" / "fermats-last-theorem"

pytestmark = pytest.mark.skipif(
    not (CORPUS / "Theorems").is_dir(),
    reason="FLT corpus not fetched; see docs/FORMAL-TRACK.md for the clone command")

#: From the corpus's own `html/about.html`.
UPSTREAM = {
    "theorems": 29511,
    "definitions": 1450,
    "citation_edges": 106853,
    "in_closure": 29489,
    "outside": 22,
    "uncited": 19,
    "landmarks": 49,
}


@pytest.fixture(scope="module")
def flt() -> Graph:
    _, nodes, meta = extract_dir(CORPUS, root="fermat_last_theorem")
    return Graph(nodes, meta=meta)


def test_file_counts_match_the_published_figures(flt):
    thms = [n for n in flt if n.is_theorem]
    defs = [n for n in flt if n.kind == "definition"]
    assert len(thms) == UPSTREAM["theorems"]
    assert len(defs) == UPSTREAM["definitions"]
    assert flt.meta["problem_count"] == 0, "every file must parse"


def test_theorem_citation_count_matches(flt):
    """The number upstream publishes counts theorem citations only."""
    def_ids = {n.id for n in flt if n.kind == "definition"}
    pairs = {(e.src, e.dst) for e in flt.edges("proof") if e.dst not in def_ids}
    assert len(pairs) == UPSTREAM["citation_edges"]


def test_closure_of_the_goal_matches(flt):
    root = "fermat_last_theorem"
    assert root in flt
    thm_ids = {n.id for n in flt if n.is_theorem}
    inside = ({root} | flt.ancestors(root, ("proof",))) & thm_ids
    outside = thm_ids - inside
    depended_on = {e.dst for e in flt.edges("proof")}

    assert len(inside) == UPSTREAM["in_closure"]
    assert len(outside) == UPSTREAM["outside"]
    assert len([t for t in outside if t not in depended_on]) == UPSTREAM["uncited"]


def test_the_corpus_is_acyclic_and_bottoms_out(flt):
    assert not flt.cycles(("proof",))
    root = flt.get("fermat_last_theorem")
    assert root.status == "verified"
    # The goal cites exactly one theorem, which is how the corpus is arranged.
    assert root.proof_deps() == {"FLT_fermatLastTheorem"}
    assert flt.depths()["fermat_last_theorem"] > 50, "a real proof has depth"


def test_no_unfinished_proofs_anywhere(flt):
    holes = [n.id for n in flt if (n.provenance.get("lean") or {}).get("sorry")]
    assert holes == []
    assert all(n.status == "verified" for n in flt if n.is_theorem)


def test_landmarks_resolve_and_are_load_bearing(flt):
    assert len(flt.meta["landmarks"]) == UPSTREAM["landmarks"]
    by_title = {n.title: n.id for n in flt}
    closure = {"fermat_last_theorem"} | flt.ancestors("fermat_last_theorem", ("proof",))
    resolved = [by_title[name] for name in flt.meta["landmarks"] if name in by_title]
    assert len(resolved) >= 30, "most landmarks should name a node in the corpus"
    stranded = [r for r in resolved if r not in closure]
    assert not stranded, f"landmarks the goal does not rest on: {stranded}"


def test_attribution_is_overwhelmingly_qualified(flt):
    """If most hits were bare or field-notation, the line attribution would be guesswork."""
    from collections import Counter
    forms: Counter = Counter()
    for n in flt:
        for k, v in ((n.provenance.get("lean") or {}).get("hit_forms") or {}).items():
            forms[k] += v
    total = sum(forms.values())
    assert total > 50_000
    assert forms["qualified"] / total > 0.75


def test_every_node_declares_how_its_edges_were_derived(flt):
    """The claim on 29,511 nodes must be legible and must not overstate."""
    for n in list(flt)[:500]:
        p = n.provenance
        assert p["derivation"] == "imports"
        if n.is_theorem:
            assert "not replayed by proofweb" in p["checked_by"]
            assert p["step_attribution"] == "textual"
