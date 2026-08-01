"""The Metamath engine, tested against a hand-verified micro-database.

Every proof in the fixture was replayed by hand on paper before it was typed,
so the verifier and the fixture check each other: if either is wrong, these
tests fail. The negative cases matter more than the positive ones — a verifier
that accepts everything extracts a graph worth nothing.
"""

from __future__ import annotations

import pytest
from proofgraph.metamath import (
    Database,
    MMError,
    extract,
    nodes_from_json,
    nodes_to_json,
)
from proofgraph.model import Graph

# A minimal propositional system: implication, ax-1, ax-2, modus ponens.
# Deliberately tiny and deliberately standard — it is the opening of set.mm
# in miniature, so what passes here should carry over to the real thing.
FIXTURE = """
$c ( ) -> wff |- $.
$v p q r $.
wp $f wff p $.
wq $f wff q $.
wr $f wff r $.
wi $a wff ( p -> q ) $.
ax-1 $a |- ( p -> ( q -> p ) ) $.
ax-2 $a |- ( ( p -> ( q -> r ) ) -> ( ( p -> q ) -> ( p -> r ) ) ) $.
${
  maj $e |- ( p -> q ) $.
  min $e |- p $.
  ax-mp $a |- q $.
$}
${
  a1i.1 $e |- p $.
  a1i $p |- ( q -> p ) $= wp wq wp wi wp wq ax-1 a1i.1 ax-mp $.
$}
${
  a1ic.1 $e |- p $.
  a1ic $p |- ( q -> p ) $= ( wi ax-1 ax-mp ) ABADABECF $.
$}
${
  a1iz.1 $e |- p $.
  a1iz $p |- ( q -> p ) $= ( wi ax-1 ax-mp ) AZBGDGBECF $.
$}
id $p |- ( p -> p ) $=
  wp wp wp wi wi  wp wp wi
  wp wp wp wi wp wi wi
  wp wp wp wi wi wp wp wi wi
  wp wp wp wi wp ax-2
  wp wp wp wi ax-1
  ax-mp
  wp wp ax-1
  ax-mp $.
"""
# History worth keeping: the first draft of the proof above ended with
# `wp wp wp wi ax-1` — the wrong ax-1 instance (q := (p->p) instead of q := p).
# The verifier refused it. The first hand-written formal proof in this
# repository was wrong, and the machine caught it. That is the pitch.

DV_FIXTURE = FIXTURE + """
${
  $d p q $.
  ax-dv $a |- ( p -> q ) $.
$}
${
  $d p q $.
  dvok $p |- ( p -> q ) $= wp wq ax-dv $.
$}
"""


@pytest.fixture(scope="module")
def db() -> Database:
    d = Database()
    d.parse(FIXTURE)
    return d


def test_every_fixture_proof_verifies(db):
    assert set(db.proofs) == {"a1i", "a1ic", "a1iz", "id"}
    assert not db.failures


def test_uncompressed_and_compressed_replays_are_identical(db):
    """Same theorem, three encodings — normal, compressed, compressed with a
    Z-tagged reused step. The replay must not care how the proof was spelled."""
    plain = [(s.kind, s.label, s.expr) for s in db.proofs["a1i"].steps]
    compressed = [(s.kind, s.label, s.expr) for s in db.proofs["a1ic"].steps]
    fix = lambda rows: [(k, l.replace("a1ic", "a1i").replace("a1iz", "a1i"), e)
                        for k, l, e in rows]
    assert fix(compressed) == fix(plain)

    # The Z variant tags 'wff p' once and references it twice instead of
    # re-deriving it, so it has two fewer step records — a reused step is a
    # reference back to the original, not a new step.
    assert len(db.proofs["a1iz"].steps) == len(plain) - 2
    assert db.proofs["a1iz"].conclusion == db.proofs["a1i"].conclusion


def test_id_is_proved_from_ax1_ax2_mp_alone(db):
    labels = {s.label for s in db.proofs["id"].steps if s.kind == "apply"}
    assert labels == {"wi", "ax-1", "ax-2", "ax-mp"}
    assert db.proofs["id"].conclusion == ("|-", "(", "p", "->", "p", ")")


def test_step_provenance_points_at_the_consumed_logical_steps(db):
    """The heart of the extraction: an application step records WHICH earlier
    steps supplied its logical premises, in mandatory-hypothesis order."""
    steps = db.proofs["a1i"].steps
    final = steps[-1]
    assert final.label == "ax-mp"
    maj, mnr = final.args
    assert steps[maj].label == "ax-1"        # major premise: |- ( p -> ( q -> p ) )
    assert steps[mnr].label == "a1i.1"       # minor premise: the hypothesis


def test_dv_conditions_accept_the_legal_and_reject_the_illegal():
    d = Database()
    d.parse(DV_FIXTURE)
    assert "dvok" in d.proofs                # $d p q in scope, distinct vars: fine

    # Same variable substituted for both sides of a $d pair: must be refused.
    with pytest.raises(MMError, match=r"\$d"):
        Database().parse(DV_FIXTURE + """
dvbad $p |- ( r -> r ) $= wr wr ax-dv $.
""")

    # Distinct variables, but no $d for them in the theorem's own scope.
    with pytest.raises(MMError, match="not in scope"):
        Database().parse(DV_FIXTURE + """
dvbad2 $p |- ( q -> r ) $= wq wr ax-dv $.
""")


@pytest.mark.parametrize("bad,why", [
    ("broken1 $p |- ( p -> p ) $= wp ax-1 $.", "stack underflow"),
    ("broken2 $p |- ( p -> p ) $= wp wp ax-1 $.", "concludes"),
    ("broken3 $p |- ( p -> p ) $= wp wp wp ax-1 $.", "2 entries"),
    ("broken4 $p |- ( p -> p ) $= wp nosuch $.", "unknown label"),
], ids=["underflow", "wrong-conclusion", "leftover-stack", "unknown-label"])
def test_broken_proofs_are_refused(bad, why):
    with pytest.raises(MMError, match=why):
        Database().parse(FIXTURE + bad)


def test_wrong_essential_hypothesis_is_refused():
    # ax-mp whose major premise does not match ( p -> q ) under the
    # substitution: the $e unification must catch it.
    with pytest.raises(MMError, match="hypothesis maj"):
        Database().parse(FIXTURE + """
${
  bad.1 $e |- p $.
  bad $p |- ( q -> p ) $= wp wq wq wp ax-1 bad.1 ax-mp $.
$}
""")


def test_incomplete_proofs_become_failures_not_crashes():
    d = Database()
    d.parse(FIXTURE + """
todo $p |- ( p -> p ) $= ? $.
""")
    assert "todo" in d.failures
    assert "todo" not in d.proofs


def test_file_inclusion_is_rejected_not_ignored():
    with pytest.raises(MMError, match="inclusion"):
        Database().parse("$[ other.mm $]")


def test_mandatory_hypotheses_interleave_in_declaration_order():
    """The spec orders mandatory hypotheses by declaration, and $e may precede
    an $f it does not use. set.mm never does this, which is exactly why a
    verifier that assumes 'all $f first' passes set.mm and silently
    mis-verifies a database that interleaves. Both encodings are exercised:
    the uncompressed proof supplies hypotheses in the true declaration order
    (wp, prem, wq), and the compressed numbering must map 1->wp, 2->prem,
    3->wq the same way."""
    interleaved = """
$c ( ) -> wff |- $.
$v p q $.
wp $f wff p $.
wq $f wff q $.
wi $a wff ( p -> q ) $.
${
  prem $e |- p $.
  $v r $.
  wr $f wff r $.
  axi $a |- ( r -> p ) $.
$}
${
  use.1 $e |- p $.
  use $p |- ( ( p -> p ) -> p ) $= wp use.1 wp wp wi axi $.
$}
${
  usec.1 $e |- p $.
  usec $p |- ( ( p -> p ) -> p ) $= ( wi axi ) ABAACD $.
$}
"""
    d = Database()
    d.parse(interleaved)
    assert [h[0] for h in d.assertions["axi"].mandatory] == ["f", "e", "f"], \
        "mandatory order must be declaration order, not f-then-e"
    assert set(d.proofs) == {"use", "usec"}
    assert d.proofs["use"].conclusion == d.proofs["usec"].conclusion


def test_verification_pass_without_step_retention():
    """keep_steps=False verifies everything and retains no replay logs —
    the mode a whole-set.mm scale test runs in. Extraction must refuse it
    rather than silently emit stepless 'verified' theorems."""
    d = Database(keep_steps=False)
    d.parse(FIXTURE)
    assert set(d.proofs) == {"a1i", "a1ic", "a1iz", "id"}
    assert all(p.steps == () for p in d.proofs.values())
    with pytest.raises(MMError, match="keep_steps"):
        extract(d, module="m", source="s")


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def graph(db) -> Graph:
    return Graph(extract(db, module="metamath-test", source="fixture.mm"))


def test_extraction_maps_kinds_and_marks_verified(graph):
    assert graph.get("ax-1").kind == "axiom"
    assert graph.get("wi").kind == "background"      # grammar, not mathematics
    assert graph.get("a1i").kind == "theorem"
    assert graph.get("a1i").status == "verified"
    assert graph.get("a1i").formalization == {"metamath": "a1i"}


def test_extracted_steps_are_logical_only_with_machine_derived_by(graph):
    """a1i replay has seven pushes; only three are |- statements. The step
    list keeps exactly those, and their `by` lists are the machine's answer
    to 'which earlier steps and which theorem justify this line'."""
    a1i = graph.get("a1i")
    assert [s.claim for s in a1i.steps] == [
        "|- ( p -> ( q -> p ) )",
        "|- p",
        "|- ( q -> p )",
    ]
    assert a1i.steps[0].by == ("ax-1",)
    assert a1i.steps[1].by == ("hyp:a1i.1",)
    assert a1i.steps[2].by == ("s:1", "s:2", "ax-mp")

    # Grammar surfaces as vocabulary, not as proof dependencies.
    assert a1i.context == ("wi",)
    assert {e.dst for e in a1i.edges() if e.kind == "proof"} == {"ax-1", "ax-mp"}
    assert {e.dst for e in a1i.edges() if e.kind == "vocabulary"} == {"wi"}


def test_extracted_graph_answers_the_flagship_queries(graph):
    assert graph.ancestors("id", ("proof",)) == {"ax-1", "ax-2", "ax-mp"}
    assert graph.descendants("ax-1", ("proof",)) >= {"a1i", "id"}
    assert graph.depth("id") == 1
    assert not graph.cycles(("proof",))


def test_extracted_json_round_trips(graph):
    data = nodes_to_json(list(graph), module="metamath-test", source="fixture.mm")
    back = Graph(nodes_from_json(data))
    assert len(back) == len(graph)
    a, b = graph.get("a1i"), back.get("a1i")
    assert [s.claim for s in a.steps] == [s.claim for s in b.steps]
    assert [s.by for s in a.steps] == [s.by for s in b.steps]
    assert sorted(str(e) for e in a.edges()) == sorted(str(e) for e in b.edges())
